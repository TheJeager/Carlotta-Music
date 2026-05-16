from os import getenv
from dotenv import load_dotenv

load_dotenv()


class Config:
    REQUIRED_FIELDS = (
        "API_ID",
        "API_HASH",
        "BOT_TOKEN",
        "MONGO_URL",
        "LOGGER_ID",
        "OWNER_ID",
        "SESSION1",
    )

    def __init__(self):
        self.API_ID = self._to_int(getenv("API_ID"), default=None)
        self.API_HASH = getenv("API_HASH")
        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")

        self.LOGGER_ID = self._to_int(getenv("LOGGER_ID"), default=None)
        self.OWNER_ID = self._to_int(getenv("OWNER_ID"), default=None)

        self.DURATION_LIMIT = self._to_int(getenv("DURATION_LIMIT"), default=60000) * 60000
        self.QUEUE_LIMIT = self._to_int(getenv("QUEUE_LIMIT"), default=20)
        self.PLAYLIST_LIMIT = self._to_int(getenv("PLAYLIST_LIMIT"), default=20)

        self.SESSION1 = getenv("SESSION1")
        self.SESSION2 = getenv("SESSION2")
        self.SESSION3 = getenv("SESSION3")

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/ErenBots")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/AnimeSprt")

        self.AUTO_LEAVE = self._to_bool(getenv("AUTO_LEAVE"), default=False)
        self.AUTO_END = self._to_bool(getenv("AUTO_END"), default=False)
        self.THUMB_GEN = self._to_bool(getenv("THUMB_GEN"), default=True)
        self.VIDEO_PLAY = self._to_bool(getenv("VIDEO_PLAY"), default=True)

        self.LANG_CODE = getenv("LANG_CODE", "en")

        self.COOKIES_URL = self._parse_cookies_url(getenv("COOKIES_URL", "https://batbin.me/qfn2"))
        self.DEFAULT_THUMB = getenv("DEFAULT_THUMB", "https://i.ibb.co/fVymn3T2/photo-2026-04-17-20-43-52.jpg")
        self.PING_IMG = getenv("PING_IMG", "https://i.ibb.co/bMX0hDSk/photo-2026-04-17-20-43-55.jpg")
        self.START_IMG = getenv("START_IMG", "https://i.ibb.co/SXwDGxNJ/image.jpg")

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _to_int(value, default=0):
        if value is None:
            return default
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Expected integer value, got: {value}") from exc

    @staticmethod
    def _parse_cookies_url(value):
        return [url for url in str(value).split() if "batbin.me" in url]

    def check(self):
        missing = [var for var in self.REQUIRED_FIELDS if not getattr(self, var)]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
