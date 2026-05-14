import unittest

from helpers import build_public_stream_url, is_youtube_url


class BotHelpersTestCase(unittest.TestCase):
    def test_is_youtube_url_accepts_watch_and_short_urls(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))

    def test_is_youtube_url_rejects_non_youtube_urls(self):
        self.assertFalse(is_youtube_url("https://example.com/video.mp4"))
        self.assertFalse(is_youtube_url("not-a-url"))

    def test_build_public_stream_url_removes_duplicate_slash(self):
        self.assertEqual(
            build_public_stream_url("sample.mp4", "https://cdn.example.com/videos/"),
            "https://cdn.example.com/videos/sample.mp4",
        )


if __name__ == "__main__":
    unittest.main()
