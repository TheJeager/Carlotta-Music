import time
import asyncio
import logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


__version__ = "3.0.3"

from config import Config

config = Config()
config.check()
tasks = []
boot = time.time()

from carlotta.core.bot import Bot

app = Bot()

from carlotta.core.dir import ensure_dirs

ensure_dirs()

from carlotta.core.userbot import Userbot

userbot = Userbot()

from carlotta.core.mongo import MongoDB

db = MongoDB()

from carlotta.core.lang import Language

lang = Language()

from carlotta.core.telegram import Telegram
from carlotta.core.youtube import YouTube

tg = Telegram()
yt = YouTube()

from carlotta.helpers import Cleaner, Queue, Thumbnail

queue = Queue()
thumb = Thumbnail()
clean = Cleaner()

from carlotta.core.calls import TgCall

anon = TgCall()


_stopping = False


async def stop() -> None:
    global _stopping
    if _stopping:
        return
    _stopping = True
    logger.info("Stopping...")

    current = asyncio.current_task()
    pending = [task for task in tasks if task is not current and not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    tasks.clear()

    async def cleanup(label, callback):
        try:
            await callback()
        except Exception:
            logger.exception("Failed to clean up %s", label)

    for client in reversed(anon.clients.copy()):
        await cleanup("voice-call client", client.stop)
        anon.clients.remove(client)

    await cleanup("bot client", app.exit)
    await cleanup("assistant clients", userbot.exit)
    await cleanup("MongoDB", db.close)
    await cleanup("thumbnail session", thumb.close)
    await cleanup("YouTube service", yt.close)

    logger.info("Stopped.\\n")
