FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

COPY for_cron/requirements.txt for_cron/requirements.txt
RUN pip install --no-cache-dir -r for_cron/requirements.txt

COPY . .

# Ensure Chromium is available (already in base image, but keep this for safety)
RUN playwright install chromium

# Default command: render & upload for today using cron_config.json in /app
CMD ["python", "for_cron/render_and_upload.py"]

