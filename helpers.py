import re

YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]{6,}"
)


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_URL_PATTERN.search(text))


def build_public_stream_url(file_name: str, public_base_url: str) -> str:
    return f"{public_base_url.rstrip('/')}/{file_name}"
