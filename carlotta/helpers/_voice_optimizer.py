import asyncio
import time
from collections import defaultdict

from carlotta import logger


class VoiceOptimizer:
    def __init__(self) -> None:
        self._invite_cache: dict[int, tuple[str, float]] = {}
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.invite_ttl = 300

    def get_cached_invite(self, chat_id: int) -> str | None:
        data = self._invite_cache.get(chat_id)
        if not data:
            return None
        invite, expires_at = data
        if expires_at < time.time():
            self._invite_cache.pop(chat_id, None)
            return None
        return invite

    def set_cached_invite(self, chat_id: int, invite_link: str) -> None:
        if invite_link:
            self._invite_cache[chat_id] = (invite_link, time.time() + self.invite_ttl)

    async def fast_join(self, client, chat_id: int, invite_link: str) -> None:
        lock = self._locks[chat_id]
        async with lock:
            delays = (0.0, 0.4, 0.8)
            last_error = None
            for delay in delays:
                if delay:
                    await asyncio.sleep(delay)
                try:
                    await client.join_chat(invite_link)
                    return
                except Exception as ex:
                    last_error = ex
                    logger.warning("Fast join retry in %s (%s)", chat_id, type(ex).__name__)
            if last_error:
                raise last_error
