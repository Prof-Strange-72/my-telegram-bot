import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from helpers import build_public_stream_url, is_youtube_url

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

MODE_YOUTUBE = "youtube"
MODE_STREAM = "stream"
MODE_STORAGE = "storage"

BTN_YOUTUBE = "YouTube downloader"
BTN_STREAM = "Video streaming link"
BTN_THIRD = "Storage"

CB_YOUTUBE = "menu_youtube"
CB_STREAM = "menu_stream"
CB_STORAGE = "menu_storage"


def get_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(BTN_YOUTUBE, callback_data=CB_YOUTUBE)],
            [InlineKeyboardButton(BTN_STREAM, callback_data=CB_STREAM)],
            [InlineKeyboardButton(BTN_THIRD, callback_data=CB_STORAGE)],
        ]
    )


def get_drive_service():
    credentials_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not credentials_path:
        return None

    scopes = ["https://www.googleapis.com/auth/drive.file"]
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload_file_to_drive(local_file: Path) -> Optional[str]:
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    drive_service = get_drive_service()
    if drive_service is None:
        return None

    metadata = {"name": local_file.name}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(str(local_file), resumable=False)
    created = drive_service.files().create(body=metadata, media_body=media).execute()
    return created.get("id")


def build_youtube_ydl_options(output_template: str) -> dict:
    ydl_opts = {
        "outtmpl": output_template,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
    }

    cookies_file = os.getenv("YOUTUBE_COOKIES_FILE")
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    cookies_from_browser = os.getenv("YOUTUBE_COOKIES_FROM_BROWSER")
    if cookies_from_browser:
        browser_parts = [part.strip() for part in cookies_from_browser.split(":") if part.strip()]
        if browser_parts:
            ydl_opts["cookiesfrombrowser"] = tuple(browser_parts)

    return ydl_opts


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Choose one feature:",
        reply_markup=get_menu_markup(),
    )


async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    choice = query.data

    if choice == CB_YOUTUBE:
        context.user_data["mode"] = MODE_YOUTUBE
        await query.message.reply_text(
            "Send a YouTube link and I will download it, send it back, and upload a copy to Google Drive (if configured)."
        )
        return

    if choice == CB_STREAM:
        context.user_data["mode"] = MODE_STREAM
        await query.message.reply_text(
            "Send a Telegram video file. I will return a public VLC-friendly link."
        )
        return

    if choice == CB_STORAGE:
        context.user_data["mode"] = MODE_STORAGE
        await query.message.reply_text(
            "Storage mode selected.\n"
            "Commands:\n"
            "- Send 'list' to view local and Drive files.\n"
            "- Send a filename to download it from the bot's storage.\n"
            "- Or simply send a file to upload it to storage (and Drive if configured)."
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = context.user_data.get("mode")
    text = (update.message.text or "").strip()
    if mode is None:
        await update.message.reply_text("Please choose a menu option first with /start.")
        return

    if mode == MODE_YOUTUBE:
        if not is_youtube_url(text):
            await update.message.reply_text("Please send a valid YouTube URL.")
            return

        await update.message.reply_text("Downloading YouTube video...")
        with TemporaryDirectory() as tmp_dir:
            output_template = os.path.join(tmp_dir, "%(title)s.%(ext)s")
            ydl_opts = build_youtube_ydl_options(output_template)
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(text, download=True)
                    downloaded_path = Path(ydl.prepare_filename(info))
                    if downloaded_path.suffix.lower() != ".mp4":
                        mp4_candidate = downloaded_path.with_suffix(".mp4")
                        if mp4_candidate.exists():
                            downloaded_path = mp4_candidate

                with downloaded_path.open("rb") as video_stream:
                    await update.message.reply_video(video=video_stream)

                saved_dir = Path(os.getenv("YOUTUBE_ARCHIVE_DIR", "data/youtube_downloads"))
                saved_dir.mkdir(parents=True, exist_ok=True)
                saved_copy = saved_dir / downloaded_path.name
                saved_copy.write_bytes(downloaded_path.read_bytes())

                drive_file_id = upload_file_to_drive(saved_copy)
                if drive_file_id:
                    await update.message.reply_text(
                        f"Saved locally and uploaded to Google Drive (file id: {drive_file_id})."
                    )
                else:
                    await update.message.reply_text(
                        "Saved locally. Google Drive upload skipped (not configured)."
                    )
            except DownloadError as exc:
                await update.message.reply_text(
                    "YouTube download failed. This usually means YouTube requires cookies or is blocking automated access.\n"
                    "If you own the account, export cookies to a Netscape cookies file and set YOUTUBE_COOKIES_FILE,\n"
                    "or set YOUTUBE_COOKIES_FROM_BROWSER to something like chrome or firefox."
                )
                logger.warning("YouTube download failed: %s", exc)
            except Exception as exc:
                await update.message.reply_text(
                    "Unexpected error while downloading YouTube video. Please try another link or check the server logs."
                )
                logger.exception("Unexpected YouTube download error: %s", exc)

    elif mode == MODE_STORAGE:
        cmd = text.lower()
        storage_dir = Path(os.getenv("STORAGE_DIR", "data/storage"))
        storage_dir.mkdir(parents=True, exist_ok=True)

        if cmd == "list":
            local_files = list(storage_dir.iterdir())
            lines = []
            if local_files:
                lines.append("Local files:")
                for p in local_files:
                    if p.is_file():
                        lines.append(f"- {p.name} ({p.stat().st_size} bytes)")
            else:
                lines.append("No local files found.")

            drive_service = get_drive_service()
            folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
            if drive_service:
                try:
                    q = f"'{folder_id}' in parents" if folder_id else None
                    resp = (
                        drive_service.files()
                        .list(pageSize=50, fields="files(id,name)", q=q)
                        .execute()
                    )
                    files = resp.get("files", [])
                    if files:
                        lines.append("\nDrive files:")
                        for f in files:
                            lines.append(f"- {f['name']} (id: {f['id']})")
                    else:
                        lines.append("\nNo Drive files found or Drive not configured.")
                except Exception:
                    lines.append("\nCould not list Drive files (check configuration).")

            await update.message.reply_text("\n".join(lines))
            return

        # attempt to send a local file matching the text
        candidate = storage_dir / text
        if candidate.exists() and candidate.is_file():
            with candidate.open("rb") as fh:
                await update.message.reply_document(document=fh)
            return

        await update.message.reply_text(
            "Unknown command or file. Send 'list' or upload a file to store it."
        )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = context.user_data.get("mode")
    if mode is None:
        await update.message.reply_text(
            "Choose an option from the menu before sending files. Use /start."
        )
        return

    # STREAM mode: generate a public URL for VLC
    if mode == MODE_STREAM:
        public_base_url = os.getenv("PUBLIC_BASE_URL")
        if not public_base_url:
            await update.message.reply_text(
                "PUBLIC_BASE_URL is not configured on server. Cannot generate public link."
            )
            return

        stream_dir = Path(os.getenv("PUBLIC_VIDEO_DIR", "public/videos"))
        stream_dir.mkdir(parents=True, exist_ok=True)

        media = update.message.video or update.message.document
        if not media:
            await update.message.reply_text("Please send a valid video file.")
            return

        telegram_file = await media.get_file()
        file_ext = Path(telegram_file.file_path or "video.mp4").suffix or ".mp4"
        file_name = f"{update.effective_user.id}_{telegram_file.file_unique_id}{file_ext}"
        local_path = stream_dir / file_name
        await telegram_file.download_to_drive(custom_path=str(local_path))

        stream_url = build_public_stream_url(file_name, public_base_url)
        await update.message.reply_text(
            f"Public streaming link:\n{stream_url}\nOpen this URL in VLC."
        )
    # STORAGE mode: save any incoming document/video to storage and optionally upload to Drive
    elif mode == MODE_STORAGE:
        storage_dir = Path(os.getenv("STORAGE_DIR", "data/storage"))
        storage_dir.mkdir(parents=True, exist_ok=True)

        media = update.message.video or update.message.document
        if not media:
            await update.message.reply_text("Please send a valid file to store.")
            return

        telegram_file = await media.get_file()
        file_ext = Path(telegram_file.file_path or "file.bin").suffix or ""
        file_name = f"{update.effective_user.id}_{telegram_file.file_unique_id}{file_ext}"
        local_path = storage_dir / file_name
        await telegram_file.download_to_drive(custom_path=str(local_path))

        drive_file_id = upload_file_to_drive(local_path)
        if drive_file_id:
            await update.message.reply_text(
                f"Stored locally as {file_name} and uploaded to Drive (id: {drive_file_id})."
            )
        else:
            await update.message.reply_text(f"Stored locally as {file_name}. Drive upload skipped.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_menu_choice))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()


if __name__ == "__main__":
    main()
