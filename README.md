# `cron_config.json` Reference Guide

This document explains the configuration fields available in `cron_config.json` for customizing the rendering of your date card generator.

## General Rendering and Size

*   `aspect_ratio` (string): The aspect ratio of the generated image. Options: `"1:1"`, `"4:5"`, `"16:9"`, `"9:16"`. (Defaults to "1:1").
*   `width_px` (integer): The base width of the output image in pixels. (Defaults to 1200).
*   `pixel_ratio` (number): The device scale factor (resolution multiplier) for the Playwright render capture. **Increase this to produce higher resolution images.** For example, using `width_px`: 1200 with `pixel_ratio`: 2 gives a 2400x2400 output.

## Typography & Colors

*   `font_family` (string): The main font for the calendar. Uses Google Fonts. E.g. `"Inter"`, `"Playfair Display"`, `"JetBrains Mono"`, `"Bebas Neue"`, `"Montserrat"`.
*   `month_year_color` (string): Hex color code for the Month/Year text (e.g. `"#ffffff"`).
*   `date_color` (string): Hex color code for the large date number text.
*   `day_color` (string): Hex color code for the day of the week text.
*   `month_year_size` (number): A scaling multiplier for the Month/Year font size.
*   `date_num_size` (number): A scaling multiplier for the large date font size.
*   `day_name_size` (number): A scaling multiplier for the day of the week font size.

## Glassmorphism/Card Container Setup

*   `card_bg` (string): Hex color for the card's background.
*   `card_opacity` (number): Opacity of the card background (0.0 to 1.0). When `< 1.0`, a backdrop-blur is applied for a "glass" effect.
*   `border_radius` (number): Border radius of the card (in pixels).
*   `shadow_intensity` (number): Opacity multiplier for the card's drop shadow.
*   `card_padding` (number): Inner padding of the card (in pixels).
*   `card_gap` (number): Spacing between the text elements inside the card (in pixels).
*   `card_width_pct` (number): The width of the card relative to the canvas (percentage, e.g. `70`).
*   `card_height_pct` (number): The height of the card relative to the canvas (percentage, e.g. `70`).
*   `card_border_width` (number): Outline border thickness around the card (in pixels).
*   `card_border_color` (string): Hex color for the card border.
*   `card_border_opacity` (number): Opacity multiplier for the card border color.

## Background Configuration

*   `bg_type` (string): Sets the type of background. Options: `"flat"`, `"gradient"`, `"image"`.
*   `flat_bg` (string): The hex color to use when `bg_type` is `"flat"`.
*   `gradient_start` (string): The start hex color when `bg_type` is `"gradient"`.
*   `gradient_end` (string): The end hex color when `bg_type` is `"gradient"`.
*   `gradient_angle` (number): The angle (in degrees) of the linear background gradient.
*   `bg_image_paths` (array of strings): A list of local file paths (e.g., `["assets/bg.jpg", "assets/bg1.jpg"]`). Used when `bg_type` is `"image"`. The scripts automatically cycles through these paths week by week.
*   `bg_index` (integer): An internal state index corresponding with `bg_image_paths`. The cron script increments this automaticallly to rotate the image.
*   `bg_image_path` (string): Optional static single string parameter (fallback if paths array is not provided).
*   `bg_image_scale` (number): Scaling multiplier for the image. E.g. `1.2` renders at 120%.
*   `bg_image_fit` (string): Defines how the image fits. Corresponds to `background-size` in CSS. Options: `"cover"`, `"contain"`, `"scale"`.
*   `bg_image_x` (number): The horizontal focal positioning (percentage, 0-100).
*   `bg_image_y` (number): The vertical focal positioning (percentage, 0-100).
*   `bg_blur_px` (number): Amount of gaussian blur applied to the background image. If > 0, the image is scaled up slightly automatically to prevent transparent edges bleeding in.
*   `bg_brightness` (number): Multiplier applied to the image brightness. `1.0` is original, `0.85` makes it slightly darker.

## Additional Effects

*   `vignette` (boolean): Whether to overlay a dark corner vignette effect over the background (`true` or `false`).
*   `vignette_color` (string): The color of the vignette overlay (typically `"#000000"`).
*   `vignette_intensity` (number): How intense the vignette fade operates.
*   `show_shapes` (boolean): Whether to introduce blurred, abstract blobs into the layout (`true` or `false`).
*   `shape_opacity` (number): Opacity of the abstract shape blobs.

## Auth, Output, & Google Drive Configuration

*   `auth_mode` (string): Method of authentication. `"service_account"` or `"oauth_user"`.
*   `drive_folder_id` (string): The Google Drive Folder ID used as the target root to upload the final PNG.
*   `service_account_json` (string): Local path to the service account credential file.
*   `oauth_client_secrets` (string): Local path to the base downloaded OAuth Client credentials.
*   `oauth_token_json` (string): Local path that will be used to store/cache your OAuth auth tokens context.
*   `output_name_template` (string): Pattern used to generate valid PNG filename saves. Use `{date}` for formatting injection. (e.g. `"calendar-{date}.png"`).

## Webhooks (Optional triggers)

*   `webhook_env` (string): Either `"development"` or `"production"`.
*   `webhook_dev_url` (string): Dev URL context destination (commonly a testing node).
*   `webhook_prod_url` (string): Production URL context destination.
*   `webhook_enabled` (boolean): `true` to fire an HTTP post request webhook after drive upload.
