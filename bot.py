import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp import YoutubeDL

from helpers import build_public_stream_url, is_youtube_url

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

MODE_YOUTUBE = "youtube"
MODE_STREAM = "stream"

BTN_YOUTUBE = "YouTube downloader"
BTN_STREAM = "Video streaming link"
BTN_THIRD = "Coming soon"


def get_menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_YOUTUBE], [BTN_STREAM], [BTN_THIRD]], resize_keyboard=True
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Choose one feature:",
        reply_markup=get_menu_markup(),
    )


async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == BTN_YOUTUBE:
        context.user_data["mode"] = MODE_YOUTUBE
        await update.message.reply_text(
            "Send a YouTube link and I will download it, send it back, and upload a copy to Google Drive (if configured)."
        )
        return

    if text == BTN_STREAM:
        context.user_data["mode"] = MODE_STREAM
        await update.message.reply_text(
            "Send a Telegram video file. I will return a public VLC-friendly link."
        )
        return

    if text == BTN_THIRD:
        await update.message.reply_text("Third feature is reserved for future upgrades.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = context.user_data.get("mode")
    text = (update.message.text or "").strip()
    if mode != MODE_YOUTUBE:
        await update.message.reply_text("Please choose a menu option first with /start.")
        return

    if not is_youtube_url(text):
        await update.message.reply_text("Please send a valid YouTube URL.")
        return

    await update.message.reply_text("Downloading YouTube video...")

    with TemporaryDirectory() as tmp_dir:
        output_template = os.path.join(tmp_dir, "%(title)s.%(ext)s")
        ydl_opts = {
            "outtmpl": output_template,
            "format": "mp4/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
        }
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


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = context.user_data.get("mode")
    if mode != MODE_STREAM:
        await update.message.reply_text(
            "Choose 'Video streaming link' from the menu before sending video."
        )
        return

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


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.Regex(f"^({BTN_YOUTUBE}|{BTN_STREAM}|{BTN_THIRD})$"), set_mode)
    )
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()


if __name__ == "__main__":
    main()
