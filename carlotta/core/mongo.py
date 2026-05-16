

from random import randint
from time import time

from pymongo import AsyncMongoClient

from carlotta import config, logger, userbot


class MongoDB:
    def __init__(self):
        """
        Initialize the MongoDB connection.
        """
        self.mongo = AsyncMongoClient(config.MONGO_URL, serverSelectionTimeoutMS=12500)
        self.db = self.mongo.Anon

        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.cmd_delete = []
        self.autoplay = []
        self.clean = []
        self.loop = {}
        self.notified = []
        self.stream_mode = {}
        self.volume = {}
        self.cache = self.db.cache
        self.logger = False

        self.assistant = {}
        self.assistantdb = self.db.assistant

        self.auth = {}
        self.authdb = self.db.auth

        self.chats = []
        self.chatsdb = self.db.chats

        self.lang = {}
        self.langdb = self.db.lang

        self.users = []
        self.usersdb = self.db.users
        self.inline_cache = self.db.inline_cache
        self.playlist_saved_limit = 50
        self.playlist_history_limit = 25

    async def connect(self) -> None:
        """Check if we can connect to the database.

        Raises:
            SystemExit: If the connection to the database fails.
        """
        try:
            start = time()
            await self.mongo.admin.command("ping")
            logger.info(f"Database connection successful. ({time() - start:.2f}s)")
            await self.load_cache()
        except Exception as e:
            raise SystemExit(f"Database connection failed: {type(e).__name__}") from e

    async def close(self) -> None:
        """Close the connection to the database."""
        await self.mongo.close()
        logger.info("Database connection closed.")

    # CACHE
    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.active_calls

    async def add_call(self, chat_id: int) -> None:
        self.active_calls[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls.get(chat_id, 0))

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        from carlotta.helpers._admins import reload_admins

        if chat_id not in self.admin_list or reload:
            self.admin_list[chat_id] = await reload_admins(chat_id)
        return self.admin_list[chat_id]

    async def get_loop(self, chat_id: int) -> int:
        return self.loop.get(chat_id, 0)

    async def set_loop(self, chat_id: int, count: int) -> None:
        self.loop[chat_id] = count

    async def get_stream_mode(self, chat_id: int) -> str:
        if chat_id not in self.stream_mode:
            doc = await self.chatsdb.find_one({"_id": chat_id}) or {}
            self.stream_mode[chat_id] = doc.get("stream_mode", "balanced")
        return self.stream_mode[chat_id]

    async def set_stream_mode(self, chat_id: int, mode: str) -> None:
        self.stream_mode[chat_id] = mode
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"stream_mode": mode}},
            upsert=True,
        )

    async def get_volume(self, chat_id: int) -> int:
        if chat_id not in self.volume:
            doc = await self.chatsdb.find_one({"_id": chat_id}) or {}
            self.volume[chat_id] = doc.get("volume", 100)
        return self.volume[chat_id]

    async def set_volume(self, chat_id: int, volume: int) -> None:
        self.volume[chat_id] = volume
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"volume": volume}},
            upsert=True,
        )

    # AUTH METHODS
    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True
            )

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$pull": {"user_ids": user_id}}
            )

    # ASSISTANT METHODS
    async def set_assistant(self, chat_id: int) -> int:
        num = randint(1, len(userbot.clients))
        await self.assistantdb.update_one(
            {"_id": chat_id},
            {"$set": {"num": num}},
            upsert=True,
        )
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id: int):
        from carlotta import anon

        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id}) or {}
            num = doc.get("num") or await self.set_assistant(chat_id)
            self.assistant[chat_id] = num

        if not anon.clients:
             raise RuntimeError("No assistant clients available.")
        return anon.clients[self.assistant[chat_id] - 1]

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)
        return {1: userbot.one, 2: userbot.two, 3: userbot.three}.get(
            self.assistant[chat_id]
        )

    # BLACKLIST METHODS
    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.append(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"}, {"$addToSet": {"chat_ids": chat_id}}, upsert=True
            )
        await self.cache.update_one(
            {"_id": "bl_users"}, {"$addToSet": {"user_ids": chat_id}}, upsert=True
        )

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.remove(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"},
                {"$pull": {"chat_ids": chat_id}},
            )
        await self.cache.update_one(
            {"_id": "bl_users"},
            {"$pull": {"user_ids": chat_id}},
        )

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklisted
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    # CHAT METHODS
    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def add_chat(self, chat_id: int) -> None:
        if not await self.is_chat(chat_id):
            self.chats.append(chat_id)
            await self.chatsdb.insert_one({"_id": chat_id})

    async def rm_chat(self, chat_id: int) -> None:
        if await self.is_chat(chat_id):
            self.chats.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self) -> list:
        if not self.chats:
            self.chats.extend([chat["_id"] async for chat in self.chatsdb.find()])
        return self.chats

    # COMMAND DELETE
    async def get_cmd_delete(self, chat_id: int) -> bool:
        if chat_id not in self.cmd_delete:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete.append(chat_id)
        return chat_id in self.cmd_delete

    async def set_cmd_delete(self, chat_id: int, delete: bool = False) -> None:
        if delete:
            if chat_id not in self.cmd_delete:
                self.cmd_delete.append(chat_id)
        elif chat_id in self.cmd_delete:
            self.cmd_delete.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"cmd_delete": delete}},
            upsert=True,
        )

    # AUTOPLAY
    async def get_autoplay(self, chat_id: int) -> bool:
        if chat_id not in self.autoplay:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("autoplay"):
                self.autoplay.append(chat_id)
        return chat_id in self.autoplay

    async def set_autoplay(self, chat_id: int, enabled: bool = False) -> None:
        if enabled:
            if chat_id not in self.autoplay:
                self.autoplay.append(chat_id)
        elif chat_id in self.autoplay:
            self.autoplay.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"autoplay": enabled}},
            upsert=True,
        )

    # CLEAN MODE
    async def get_clean(self, chat_id: int) -> bool:
        if chat_id not in self.clean:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("clean"):
                self.clean.append(chat_id)
        return chat_id in self.clean

    async def set_clean(self, chat_id: int, enabled: bool = False) -> None:
        if enabled:
            if chat_id not in self.clean:
                self.clean.append(chat_id)
        elif chat_id in self.clean:
            self.clean.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"clean": enabled}},
            upsert=True,
        )

    # LANGUAGE METHODS
    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one(
            {"_id": chat_id},
            {"$set": {"lang": lang_code}},
            upsert=True,
        )
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else config.LANG_CODE
        return self.lang[chat_id]

    # LOGGER METHODS
    async def is_logger(self) -> bool:
        return self.logger

    async def get_logger(self) -> bool:
        doc = await self.cache.find_one({"_id": "logger"})
        if doc:
            self.logger = doc["status"]
        return self.logger

    async def set_logger(self, status: bool) -> None:
        self.logger = status
        await self.cache.update_one(
            {"_id": "logger"},
            {"$set": {"status": status}},
            upsert=True,
        )

    # PLAY MODE METHODS
    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        if remove and chat_id in self.admin_play:
            self.admin_play.remove(chat_id)
        else:
            self.admin_play.append(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"admin_play": not remove}},
            upsert=True,
        )

    # SUDO METHODS
    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True
        )

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$pull": {"user_ids": user_id}}
        )

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    # USER METHODS
    async def is_user(self, user_id: int) -> bool:
        return user_id in self.users

    async def add_user(self, user_id: int) -> None:
        if not await self.is_user(user_id):
            self.users.append(user_id)
            await self.usersdb.insert_one({"_id": user_id})

    async def rm_user(self, user_id: int) -> None:
        if await self.is_user(user_id):
            self.users.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self) -> list:
        if not self.users:
            self.users.extend([user["_id"] async for user in self.usersdb.find()])
        return self.users

    @staticmethod
    def _serialize_playlist_item(item) -> dict:
        if isinstance(item, dict):
            return {
                "id": item["id"],
                "channel_name": item.get("channel_name"),
                "duration": item.get("duration", "00:00"),
                "duration_sec": item.get("duration_sec", 0),
                "file_path": item.get("file_path"),
                "stream_mode": item.get("stream_mode", "balanced"),
                "thumbnail": item.get("thumbnail"),
                "title": item.get("title"),
                "url": item.get("url"),
                "user": item.get("user"),
                "video": item.get("video", False),
            }

        channel_name = getattr(item, "channel_name", None)
        return {
            "id": item.id,
            "channel_name": channel_name,
            "duration": item.duration,
            "duration_sec": item.duration_sec,
            "file_path": item.file_path,
            "stream_mode": getattr(item, "stream_mode", "balanced"),
            "thumbnail": getattr(item, "thumbnail", None),
            "title": item.title,
            "url": item.url,
            "user": item.user,
            "video": getattr(item, "video", False),
        }

    async def get_playlist(self, user_id: int, section: str = "saved") -> list[dict]:
        doc = await self.usersdb.find_one(
            {"_id": user_id},
            {"playlist_saved": 1, "playlist_history": 1},
        ) or {}
        key = "playlist_saved" if section == "saved" else "playlist_history"
        return doc.get(key, [])

    async def add_playlist_item(self, user_id: int, item) -> tuple[bool, int]:
        data = self._serialize_playlist_item(item)
        current = await self.get_playlist(user_id, "saved")
        is_new = not any(track.get("id") == data["id"] for track in current)
        current = [track for track in current if track.get("id") != data["id"]]
        current.insert(0, data)
        current = current[: self.playlist_saved_limit]
        await self.usersdb.update_one(
            {"_id": user_id},
            {"$set": {"playlist_saved": current}},
            upsert=True,
        )
        return is_new, len(current)

    async def del_playlist_item(self, user_id: int, item_id: str) -> bool:
        current = await self.get_playlist(user_id, "saved")
        updated = [track for track in current if track.get("id") != item_id]
        if len(updated) == len(current):
            return False
        await self.usersdb.update_one(
            {"_id": user_id},
            {"$set": {"playlist_saved": updated}},
            upsert=True,
        )
        return True

    async def in_playlist(self, user_id: int, item_id: str) -> bool:
        current = await self.get_playlist(user_id, "saved")
        return any(track.get("id") == item_id for track in current)

    async def add_playlist_history(self, user_id: int, item) -> int:
        data = self._serialize_playlist_item(item)
        history = await self.get_playlist(user_id, "history")
        history = [track for track in history if track.get("id") != data["id"]]
        history.insert(0, data)
        history = history[: self.playlist_history_limit]
        await self.usersdb.update_one(
            {"_id": user_id},
            {"$set": {"playlist_history": history}},
            upsert=True,
        )
        return len(history)

    # INLINE CACHE
    async def get_inline_cache(self, track_id: str) -> str | None:
        doc = await self.inline_cache.find_one({"_id": track_id})
        return doc.get("file_id") if doc else None

    async def set_inline_cache(self, track_id: str, file_id: str) -> None:
        await self.inline_cache.update_one(
            {"_id": track_id},
            {"$set": {"file_id": file_id}},
            upsert=True,
        )


    async def migrate_coll(self) -> None:
        logger.info("Migrating users and chats from old collections...")

        users, musers, mchats = [], [], []
        seen_chats, seen_users = set(), set()
        users.extend([user async for user in self.usersdb.find()])
        users.extend([user async for user in self.db.tgusersdb.find()])

        for user in users:
            _id = user.get("_id")
            if isinstance(_id, int):
                user_id = _id
            else:
                user_id = int(user.get("user_id"))

            if user_id in seen_users:
                continue
            seen_users.add(user_id)
            musers.append({"_id": user_id})

        await self.usersdb.drop()
        await self.db.tgusersdb.drop()
        if musers:
            await self.usersdb.insert_many(musers)

        async for chat in self.chatsdb.find():
            _id = chat.get("_id")
            if isinstance(_id, int):
                chat_id = _id
            else:
                chat_id = int(chat.get("chat_id"))

            if chat_id in seen_chats:
                continue
            seen_chats.add(chat_id)
            mchats.append({"_id": chat_id})

        await self.chatsdb.drop()
        if mchats:
            await self.chatsdb.insert_many(mchats)

        await self.cache.insert_one({"_id": "migrated"})
        logger.info("Migration completed successfully.")

    async def load_cache(self) -> None:
        doc = await self.cache.find_one({"_id": "migrated"})
        if not doc:
            await self.migrate_coll()

        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()
        logger.info("Database cache loaded.")
