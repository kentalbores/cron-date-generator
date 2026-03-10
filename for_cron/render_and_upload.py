import argparse
import asyncio
import base64
import datetime as dt
import json
import mimetypes
import os
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account, credentials as google_credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from playwright.async_api import async_playwright


BgType = Literal["flat", "gradient", "image"]
AspectRatio = Literal["1:1", "4:5", "16:9", "9:16"]


NOISE_SVG_DATA_URL = (
    "data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E"
    "%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' "
    "numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' "
    "filter='url(%23noiseFilter)'/%3E%3C/svg%3E"
)


def _parse_date(date_str: Optional[str]) -> dt.date:
    if not date_str:
        return dt.date.today()
    return dt.date.fromisoformat(date_str)


def _aspect_to_size(aspect: AspectRatio, width: int) -> Tuple[int, int]:
    if aspect == "1:1":
        return width, width
    if aspect == "4:5":
        return width, round(width * 5 / 4)
    if aspect == "16:9":
        return width, round(width * 9 / 16)
    if aspect == "9:16":
        return width, round(width * 16 / 9)
    raise ValueError(f"Unknown aspect ratio: {aspect}")


def _hex_to_rgba(hex_color: str, opacity: float) -> str:
    s = hex_color.strip()
    if not re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", s):
        raise ValueError(f"Invalid hex color: {hex_color}")
    if len(s) == 4:
        r = int(s[1] * 2, 16)
        g = int(s[2] * 2, 16)
        b = int(s[3] * 2, 16)
    else:
        r = int(s[1:3], 16)
        g = int(s[3:5], 16)
        b = int(s[5:7], 16)
    return f"rgba({r}, {g}, {b}, {opacity})"


def _bg_size_css(config: "CronConfig") -> str:
    if config.bg_image_fit == "cover":
        return "cover"
    if config.bg_image_fit == "contain":
        return "contain"
    return f"{config.bg_image_scale * 100}%"


def _file_to_data_url(path: pathlib.Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "application/octet-stream"
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class CronConfig:
    # Rendering
    aspect_ratio: AspectRatio
    width_px: int
    pixel_ratio: float
    font_family: str
    month_year_color: str
    date_color: str
    day_color: str
    month_year_size: float
    date_num_size: float
    day_name_size: float

    # Card
    card_bg: str
    card_opacity: float
    border_radius: float
    shadow_intensity: float
    card_padding: float
    card_gap: float
    card_width_pct: float
    card_height_pct: float
    card_border_width: float
    card_border_color: str
    card_border_opacity: float

    # Background
    bg_type: BgType
    flat_bg: str
    gradient_start: str
    gradient_end: str
    gradient_angle: float
    bg_image_path: Optional[str]
    bg_image_scale: float
    bg_image_fit: Literal["cover", "contain", "scale"]
    bg_image_x: float
    bg_image_y: float
    bg_blur_px: float
    bg_brightness: float

    # Effects
    vignette: bool
    vignette_color: str
    vignette_intensity: float
    show_shapes: bool
    shape_opacity: float

    # Upload
    auth_mode: Literal["service_account", "oauth_user"]
    drive_folder_id: str
    service_account_json: str
    oauth_client_secrets: str
    oauth_token_json: str
    output_name_template: str
    webhook_env: Literal["development", "production"]
    webhook_dev_url: Optional[str]
    webhook_prod_url: Optional[str]
    webhook_enabled: bool


def load_config(path: pathlib.Path) -> CronConfig:
    raw = _read_json(path)

    def req(key: str) -> Any:
        if key not in raw:
            raise KeyError(f"Missing config key: {key}")
        return raw[key]

    def opt(key: str, default: Any) -> Any:
        return raw.get(key, default)

    bg_image_paths = opt("bg_image_paths", [])
    if bg_image_paths:
        bg_index = int(opt("bg_index", 0))
        bg_image_path = bg_image_paths[bg_index % len(bg_image_paths)]
    else:
        bg_image_path = opt("bg_image_path", None)

    return CronConfig(
        aspect_ratio=req("aspect_ratio"),
        width_px=int(opt("width_px", 1200)),
        pixel_ratio=float(opt("pixel_ratio", 2)),
        font_family=str(opt("font_family", "Inter")),
        month_year_color=str(opt("month_year_color", "#18181b")),
        date_color=str(opt("date_color", "#18181b")),
        day_color=str(opt("day_color", "#71717a")),
        month_year_size=float(opt("month_year_size", 1.0)),
        date_num_size=float(opt("date_num_size", 1.0)),
        day_name_size=float(opt("day_name_size", 1.0)),
        card_bg=str(opt("card_bg", "#ffffff")),
        card_opacity=float(opt("card_opacity", 1.0)),
        border_radius=float(opt("border_radius", 24)),
        shadow_intensity=float(opt("shadow_intensity", 0.1)),
        card_padding=float(opt("card_padding", 40)),
        card_gap=float(opt("card_gap", 32)),
        card_width_pct=float(opt("card_width_pct", 75)),
        card_height_pct=float(opt("card_height_pct", 75)),
        card_border_width=float(opt("card_border_width", 1)),
        card_border_color=str(opt("card_border_color", "#ffffff")),
        card_border_opacity=float(opt("card_border_opacity", 0.2)),
        bg_type=req("bg_type"),
        flat_bg=str(opt("flat_bg", "#f4f4f5")),
        gradient_start=str(opt("gradient_start", "#e2e8f0")),
        gradient_end=str(opt("gradient_end", "#94a3b8")),
        gradient_angle=float(opt("gradient_angle", 135)),
        bg_image_path=bg_image_path,
        bg_image_scale=float(opt("bg_image_scale", 1.0)),
        bg_image_fit=str(opt("bg_image_fit", "scale")),
        bg_image_x=float(opt("bg_image_x", 50)),
        bg_image_y=float(opt("bg_image_y", 50)),
        bg_blur_px=float(opt("bg_blur_px", 0)),
        bg_brightness=float(opt("bg_brightness", 1.0)),
        vignette=bool(opt("vignette", False)),
        vignette_color=str(opt("vignette_color", "#000000")),
        vignette_intensity=float(opt("vignette_intensity", 0.3)),
        show_shapes=bool(opt("show_shapes", False)),
        shape_opacity=float(opt("shape_opacity", 0.1)),
        auth_mode=str(opt("auth_mode", "service_account")),
        drive_folder_id=req("drive_folder_id"),
        service_account_json=req("service_account_json"),
        oauth_client_secrets=str(opt("oauth_client_secrets", "secrets/oauth-client.json")),
        oauth_token_json=str(opt("oauth_token_json", "secrets/oauth-token.json")),
        output_name_template=str(opt("output_name_template", "calendar-{date}.png")),
        webhook_env=str(opt("webhook_env", "production")),
        webhook_dev_url=opt("webhook_dev_url", None),
        webhook_prod_url=opt("webhook_prod_url", None),
        webhook_enabled=bool(opt("webhook_enabled", True)),
    )


def build_html(config: CronConfig, date: dt.date) -> str:
    month = date.strftime("%b")
    year = date.year
    day_num = date.day
    day_name = date.strftime("%a")

    if config.bg_type == "image" and config.bg_image_path:
        img_path = pathlib.Path(config.bg_image_path).expanduser().resolve()
        bg_image_url = _file_to_data_url(img_path)
    else:
        bg_image_url = ""

    card_bg_rgba = _hex_to_rgba(config.card_bg, config.card_opacity)
    card_border_rgba = _hex_to_rgba(config.card_border_color, config.card_border_opacity)

    # Match the app's sizing logic.
    month_base = "1.25rem" if config.aspect_ratio == "16:9" else "1.875rem"
    date_base = "80px" if config.aspect_ratio == "16:9" else ("100px" if config.aspect_ratio == "9:16" else "120px")
    day_base = month_base

    bg_filter = ""
    bg_transform = "scale(1)"
    if config.bg_blur_px > 0 or abs(config.bg_brightness - 1.0) > 1e-6:
        bg_filter = f"blur({config.bg_blur_px}px) brightness({config.bg_brightness})"
    if config.bg_blur_px > 0:
        bg_transform = "scale(1.1)"

    bg_flat_display = "none" if config.bg_type == "image" else "block"
    bg_image_display = "block" if (config.bg_type == "image" and bg_image_url) else "none"

    # Font: we use Google Fonts (same families as the project).
    # This is server-friendly and avoids bundling font files.
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,400..900;1,400..900&family=JetBrains+Mono:wght@400;700&family=Bebas+Neue&family=Montserrat:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
      :root {{
        --font-inter: "Inter", ui-sans-serif, system-ui, sans-serif;
        --font-playfair: "Playfair Display", serif;
        --font-jetbrains: "JetBrains Mono", monospace;
        --font-bebas: "Bebas Neue", sans-serif;
        --font-montserrat: "Montserrat", sans-serif;
      }}
      html, body {{
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: transparent;
      }}
      body {{
        display: block;
      }}
      .canvas {{
        position: relative;
        overflow: hidden;
        background: white;
        width: 100vw;
        height: 100vh;
        font-family: {css_font_family(config.font_family)};
      }}
      .layer {{
        position: absolute;
        inset: 0;
      }}
      .bg-flat {{
        display: {bg_flat_display};
        background-color: {config.flat_bg if config.bg_type == "flat" else "transparent"};
        background-image: {"linear-gradient(" + str(config.gradient_angle) + "deg, " + config.gradient_start + ", " + config.gradient_end + ")" if config.bg_type == "gradient" else "none"};
        filter: {bg_filter if bg_filter else "none"};
        transform: {bg_transform};
        z-index: 1;
      }}
      .bg-image {{
        display: {bg_image_display};
        background-image: url("{bg_image_url}");
        background-size: {_bg_size_css(config)};
        background-position: {config.bg_image_x}% {config.bg_image_y}%;
        background-repeat: no-repeat;
        filter: {bg_filter if bg_filter else "none"};
        transform: {bg_transform};
        z-index: 2;
      }}
      .shapes {{
        display: {"block" if config.show_shapes else "none"};
        opacity: {config.shape_opacity};
        z-index: 3;
        pointer-events: none;
      }}
      .shapes .s1 {{
        position: absolute;
        top: -80px;
        left: -80px;
        width: 256px;
        height: 256px;
        border-radius: 9999px;
        background: rgba(255,255,255,0.8);
        filter: blur(48px);
        opacity: 0.5;
      }}
      .shapes .s2 {{
        position: absolute;
        top: 50%;
        right: -80px;
        width: 320px;
        height: 320px;
        border-radius: 9999px;
        background: rgba(0,0,0,0.35);
        filter: blur(48px);
        opacity: 0.2;
        transform: translateY(-50%);
      }}
      .shapes .s3 {{
        position: absolute;
        bottom: -80px;
        left: 25%;
        width: 384px;
        height: 384px;
        background: rgba(161,161,170,0.6);
        filter: blur(48px);
        opacity: 0.3;
        transform: rotate(45deg);
      }}
      .vignette {{
        display: {"block" if config.vignette else "none"};
        z-index: 4;
        pointer-events: none;
        background: radial-gradient(circle, transparent 40%, {config.vignette_color} 140%);
        opacity: {config.vignette_intensity * 1.5};
        mix-blend-mode: multiply;
      }}
      .noise {{
        z-index: 5;
        pointer-events: none;
        background-image: url("{NOISE_SVG_DATA_URL}");
        opacity: 0.05;
      }}
      .content {{
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        z-index: 10;
      }}
      .card {{
        width: {config.card_width_pct}%;
        height: {config.card_height_pct}%;
        padding: {config.card_padding}px;
        gap: {max(0, config.card_gap)}px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        background-color: {card_bg_rgba};
        border-radius: {config.border_radius}px;
        box-shadow: 0 20px 50px rgba(0,0,0,{config.shadow_intensity});
        backdrop-filter: {"blur(12px)" if config.card_opacity < 1 else "none"};
        border: {config.card_border_width}px solid {card_border_rgba};
      }}
      .month {{
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        line-height: 1;
        color: {config.month_year_color};
        font-size: calc({month_base} * {config.month_year_size});
      }}
      .date {{
        font-weight: 900;
        letter-spacing: -0.04em;
        line-height: 1;
        color: {config.date_color};
        font-size: calc({date_base} * {config.date_num_size});
        margin-top: {config.card_gap if config.card_gap < 0 else 0}px;
      }}
      .day {{
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        line-height: 1;
        color: {config.day_color};
        font-size: calc({day_base} * {config.day_name_size});
        margin-top: {config.card_gap if config.card_gap < 0 else 0}px;
      }}
    </style>
  </head>
  <body>
    <div id="calendar" class="canvas">
      <div class="layer bg-flat"></div>
      <div class="layer bg-image"></div>
      <div class="layer shapes">
        <div class="s1"></div>
        <div class="s2"></div>
        <div class="s3"></div>
      </div>
      <div class="layer vignette"></div>
      <div class="layer noise"></div>
      <div class="content">
        <div class="card">
          <div class="month">{month} {year}</div>
          <div class="date">{day_num}</div>
          <div class="day">{day_name}</div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def css_font_family(name: str) -> str:
    n = name.strip().lower()
    if n in {"inter", "sans", "font-sans"}:
        return "var(--font-inter)"
    if n in {"playfair display", "playfair", "serif", "font-serif"}:
        return "var(--font-playfair)"
    if n in {"jetbrains mono", "jetbrains", "mono", "font-mono"}:
        return "var(--font-jetbrains)"
    if n in {"bebas neue", "bebas", "display", "font-display"}:
        return "var(--font-bebas)"
    if n in {"montserrat", "font-montserrat"}:
        return "var(--font-montserrat)"
    # Allow custom CSS family strings in config.
    return name


async def render_png(config: CronConfig, date: dt.date, out_path: pathlib.Path) -> None:
    width, height = _aspect_to_size(config.aspect_ratio, config.width_px)
    html = build_html(config, date)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=config.pixel_ratio,
        )
        page = await context.new_page()
        await page.set_content(html, wait_until="load")
        # Ensure fonts are ready to avoid fallback text metrics.
        await page.evaluate("() => document.fonts && document.fonts.ready")
        calendar = page.locator("#calendar")
        await calendar.screenshot(path=str(out_path), omit_background=True)
        await context.close()
        await browser.close()


def build_drive_service(config: CronConfig, repo_root: pathlib.Path):
    scopes = ["https://www.googleapis.com/auth/drive.file"]

    if config.auth_mode == "service_account":
        sa_path = pathlib.Path(config.service_account_json).expanduser()
        if not sa_path.is_absolute():
            sa_path = (repo_root / sa_path).resolve()

        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=scopes,
        )
        return build("drive", "v3", credentials=creds)

    # OAuth user mode
    client_path = pathlib.Path(config.oauth_client_secrets).expanduser()
    if not client_path.is_absolute():
        client_path = (repo_root / client_path).resolve()

    token_path = pathlib.Path(config.oauth_token_json).expanduser()
    if not token_path.is_absolute():
        token_path = (repo_root / token_path).resolve()

    creds: Optional[google_credentials.Credentials] = None
    if token_path.exists():
        creds = google_credentials.Credentials.from_authorized_user_file(
            str(token_path),
            scopes=scopes,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_path),
                scopes=scopes,
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


def upload_to_drive(
    *,
    service,
    drive_folder_id: str,
    file_path: pathlib.Path,
    mime_type: str = "image/png",
    file_name: Optional[str] = None,
) -> str:

    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=False)
    body = {
        "name": file_name or file_path.name,
        "parents": [drive_folder_id],
    }
    created = service.files().create(body=body, media_body=media, fields="id,webViewLink").execute()
    return created.get("webViewLink") or created["id"]


def trigger_webhook(config: CronConfig, *, date: dt.date, file_name: str, link: str) -> None:
    if not config.webhook_enabled:
        return

    if config.webhook_env == "development":
        url = config.webhook_dev_url
    else:
        url = config.webhook_prod_url

    if not url:
        return

    payload = {
        "date": date.isoformat(),
        "environment": config.webhook_env,
        "file_name": file_name,
        "drive_link": link,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        # Log to stdout/stderr but do not fail the whole job.
        print(f"Webhook call to {url} failed: {exc}", file=sys.stderr)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render flip calendar PNG and upload to Google Drive.")
    parser.add_argument("--config", default="cron_config.json", help="Path to config JSON in repo root.")
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD (default: today).")
    parser.add_argument("--no-upload", action="store_true", help="Render only; do not upload to Drive.")
    parser.add_argument("--out", default=None, help="Output PNG path (default: ./out/<templated name>).")
    args = parser.parse_args(argv)

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve() if not os.path.isabs(args.config) else pathlib.Path(args.config)
    date = _parse_date(args.date)

    with config_path.open("r", encoding="utf-8") as f:
        raw_config = json.load(f)
    
    if "bg_image_paths" in raw_config and raw_config["bg_image_paths"]:
        paths = raw_config["bg_image_paths"]
        last_week = raw_config.get("bg_last_week")
        current_week = date.isocalendar()[1]
        
        if last_week != current_week:
            if last_week is not None:
                raw_config["bg_index"] = (raw_config.get("bg_index", 0) + 1) % len(paths)
            raw_config["bg_last_week"] = current_week
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(raw_config, f, indent=2)

    config = load_config(config_path)

    file_name = config.output_name_template.format(date=date.isoformat())
    out_path = pathlib.Path(args.out).resolve() if args.out else (repo_root / "out" / file_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(render_png(config, date, out_path))
    print(f"Rendered: {out_path}")

    if args.no_upload:
        return 0

    service = build_drive_service(config, repo_root)
    link_or_id = upload_to_drive(
        service=service,
        drive_folder_id=config.drive_folder_id,
        file_path=out_path,
        file_name=file_name,
    )
    print(f"Uploaded: {link_or_id}")

    # Fire n8n webhook (non-fatal if it fails)
    trigger_webhook(config, date=date, file_name=file_name, link=link_or_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
