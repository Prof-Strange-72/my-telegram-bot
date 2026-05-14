# my-telegram-bot

Telegram bot with a menu and starter features:

1. **YouTube downloader**
   - Send a YouTube link after selecting this menu item.
   - Bot downloads the video, sends it back in Telegram, stores a local archive copy, and uploads a copy to Google Drive (if configured).
2. **Video streaming link**
   - Send a Telegram video after selecting this menu item.
   - Bot stores the file in a public directory and returns a public URL you can open in VLC.
3. **Coming soon**
   - Placeholder third feature for future upgrades.

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:

- `TELEGRAM_BOT_TOKEN` (required)
- `PUBLIC_BASE_URL` (required for streaming links, for example `https://mydomain.com/videos`)
- `PUBLIC_VIDEO_DIR` (optional, default `public/videos`)
- `YOUTUBE_ARCHIVE_DIR` (optional, default `data/youtube_downloads`)
- `GOOGLE_SERVICE_ACCOUNT_FILE` (optional, path to service account JSON for Drive upload)
- `GOOGLE_DRIVE_FOLDER_ID` (optional, Drive folder id)

Then run:

```bash
python bot.py
```
