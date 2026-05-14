# my-telegram-bot

Telegram bot with a menu and starter features. The menu now uses Telegram inline buttons, so you tap the option directly in the message.

1. **YouTube downloader**
   - Send a YouTube link after selecting this menu item.
   - Bot downloads the video, sends it back in Telegram, stores a local archive copy, and uploads a copy to Google Drive (if configured).
2. **Video streaming link**
   - Send a Telegram video after selecting this menu item.
   - Bot stores the file in a public directory and returns a public URL you can open in VLC.
3. **Storage**
   - Upload a file to store it locally and optionally in Google Drive.
   - Send `list` to view stored files.
   - Send a filename to download a stored file back to Telegram.

## Telegram docs

- Inline keyboard: https://core.telegram.org/bots/api#inlinekeyboardmarkup
- Reply keyboard: https://core.telegram.org/bots/api#replykeyboardmarkup

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:

- `TELEGRAM_BOT_TOKEN` (required)
- `PUBLIC_BASE_URL` (required for streaming links, for example `https://mydomain.com/videos`)
- `PUBLIC_VIDEO_DIR` (optional, default `public/videos`)
- `YOUTUBE_ARCHIVE_DIR` (optional, default `data/youtube_downloads`)
- `YOUTUBE_COOKIES_FILE` (optional, path to a Netscape-format cookies file for yt-dlp if YouTube blocks downloads)
- `YOUTUBE_COOKIES_FROM_BROWSER` (optional, browser name or browser path for yt-dlp, for example `chrome` or `firefox`)
- `GOOGLE_SERVICE_ACCOUNT_FILE` (optional, path to service account JSON for Drive upload)
- `GOOGLE_DRIVE_FOLDER_ID` (optional, Drive folder id)

If YouTube asks for sign-in or says it is blocking automated access, export cookies from a browser session you control and set `YOUTUBE_COOKIES_FILE` to that file path.
You can also try `YOUTUBE_COOKIES_FROM_BROWSER=chrome` or `YOUTUBE_COOKIES_FROM_BROWSER=firefox` if yt-dlp can read cookies from a local browser profile.

Then run:

```bash
python bot.py
```
