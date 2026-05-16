import asyncio
import os
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any

from carlotta import app, config, logger


class Cleaner:
    def __init__(self):
        self.thumb_files: dict[int, set[str]] = defaultdict(set)
        self._background_tasks: set[asyncio.Task] = set()

    def register_thumb(self, chat_id: int, thumb_path: str | None) -> None:
        if not thumb_path:
            return
        if thumb_path == config.DEFAULT_THUMB:
            return
        if not os.path.exists(thumb_path):
            return
        self.thumb_files[chat_id].add(thumb_path)

    async def cleanup_chat_thumbs(self, chat_id: int) -> int:
        files = list(self.thumb_files.pop(chat_id, set()))
        removed = 0
        for file_path in files:
            try:
                os.remove(file_path)
                removed += 1
            except FileNotFoundError:
                continue
            except Exception as ex:
                logger.warning("Failed to remove thumbnail %s: %s", file_path, ex)
        return removed

    async def delete_message_after(
        self, chat_id: int, message_id: int, delay: int = 20
    ) -> None:
        await asyncio.sleep(max(delay, 1))
        await self.delete_message(chat_id=chat_id, message_id=message_id)

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        try:
            await app.delete_messages(chat_id=chat_id, message_ids=message_id)
        except Exception as ex:
            logger.debug(
                "Unable to delete message %s in chat %s: %s", message_id, chat_id, ex
            )

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._background_tasks.discard(task)
        try:
            error = task.exception()
        except asyncio.CancelledError:
            return
        if error is not None:
            logger.debug("Background clean task failed: %s", error)

    def create_background_task(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task
