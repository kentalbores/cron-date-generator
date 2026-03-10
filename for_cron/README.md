# for_cron

This folder contains a cron-friendly Python renderer/uploader that generates the same “flip calendar” image (month/year, day number, weekday) as the React app, then uploads it into a Google Drive folder.

## Setup

1) Create a Python venv and install deps:

```bash
python -m venv .venv
./.venv/Scripts/pip install -r for_cron/requirements.txt
./.venv/Scripts/python -m playwright install chromium
```

2) Create a **Google Drive service account** key JSON and save it at:

- `secrets/drive-service-account.json` (matches `cron_config.json`)

3) In Google Drive, open your target folder and **share it with the service account email** (Editor).

Even if the folder is “public”, uploading still requires an authenticated account that has write permission.

## Run

Render today’s image and upload:

```bash
./.venv/Scripts/python for_cron/render_and_upload.py
```

Render a specific date without uploading:

```bash
./.venv/Scripts/python for_cron/render_and_upload.py --date 2026-03-10 --no-upload
```

Outputs go to `./out/` by default.

## Config

Edit `cron_config.json` in the repo root.

- For background photos, set:
  - `"bg_type": "image"`
  - `"bg_image_path": "/absolute/or/relative/path/to/photo.jpg"`

## Cron

On Linux (crontab), at midnight:

```bash
0 0 * * * /path/to/repo/.venv/bin/python /path/to/repo/for_cron/render_and_upload.py >> /path/to/repo/cron.log 2>&1
```

