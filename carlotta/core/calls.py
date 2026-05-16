import asyncio
from collections import defaultdict, deque
from ntgcalls import (ConnectionNotFound, TelegramServerError,
                      RTMPStreamingUnsupported, ConnectionError)
from pyrogram.errors import (ChatSendMediaForbidden, ChatSendPhotosForbidden,
                             MessageIdInvalid)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from carlotta import (app, clean, config, db, lang, logger,
                   queue, thumb, userbot, yt)
from carlotta.helpers import Media, Track, buttons


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []
        self.prefetch_tasks = {}
        self.play_next_locks = {}
        self.autoplay_history = defaultdict(lambda: deque(maxlen=30))
        self.download_timeout = 45

    def _get_play_next_lock(self, chat_id: int) -> asyncio.Lock:
        lock = self.play_next_locks.get(chat_id)
        if not lock:
            lock = asyncio.Lock()
            self.play_next_locks[chat_id] = lock
        return lock

    async def _pick_autoplay_track(self, chat_id: int, current: Track) -> Media | Track | None:
        mode = await db.get_stream_mode(chat_id)
        related = await yt.related_tracks(current, limit=20, mode=mode)
        if not related:
            return None

        queued_ids = {item.id for item in queue.get_queue(chat_id)}
        recently_played = set(self.autoplay_history[chat_id])
        for candidate in related:
            if (
                not candidate
                or candidate.id in queued_ids
                or candidate.id in recently_played
            ):
                continue
            candidate.user = "Autoplay"
            candidate.stream_mode = mode
            if not candidate.file_path:
                candidate.file_path = await self._download_with_timeout(chat_id, candidate)
            if candidate.file_path:
                queue.add(chat_id, candidate)
                return candidate
        return None

    async def _download_with_timeout(
        self, chat_id: int, media: Media | Track
    ) -> str | None:
        try:
            return await asyncio.wait_for(
                yt.download(
                    media.id,
                    video=media.video,
                    mode=media.stream_mode,
                ),
                timeout=self.download_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Download timed out in chat %s for media %s",
                chat_id,
                getattr(media, "id", "unknown"),
            )
            return None

    async def _resolve_next_media(
        self,
        chat_id: int,
        current: Media | Track | None,
        allow_autoplay: bool = True,
    ) -> Media | Track | None:
        media = queue.get_next(chat_id)
        if media:
            return media
        if not isinstance(current, Track):
            return None
        if not allow_autoplay or not await db.get_autoplay(chat_id):
            return None
        try:
            return await self._pick_autoplay_track(chat_id, current)
        except Exception as ex:
            logger.warning(
                "Autoplay pick failed in chat %s for track %s: %s",
                chat_id,
                getattr(current, "id", "unknown"),
                ex,
            )
            return None

    async def _prefetch(self, chat_id: int, media: Media | Track) -> None:
        if media.file_path or not isinstance(media, Track):
            return

        tasks = [self._download_with_timeout(chat_id, media)]
        if config.THUMB_GEN:
            tasks.append(thumb.generate(media))

        results = await asyncio.gather(*tasks)
        media.file_path = results[0]

    def schedule_prefetch(self, chat_id: int) -> None:
        media = queue.get_next(chat_id, check=True)
        if not media or media.file_path or not isinstance(media, Track):
            return
        task = self.prefetch_tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
        self.prefetch_tasks[chat_id] = asyncio.create_task(self._prefetch(chat_id, media))

    async def pause(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def _change_volume(self, client: PyTgCalls, chat_id: int, volume: int) -> None:
        change_volume = getattr(client, "change_volume_call", None)
        if change_volume is None:
            change_volume = getattr(client, "change_volume")
        await change_volume(chat_id, volume)

    async def set_volume(self, chat_id: int, volume: int) -> None:
        client = await db.get_assistant(chat_id)
        await self._change_volume(client, chat_id, volume)
        await db.set_volume(chat_id, volume)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        await clean.cleanup_chat_thumbs(chat_id)
        queue.clear(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)
        self.play_next_locks.pop(chat_id, None)
        self.autoplay_history.pop(chat_id, None)
        task = self.prefetch_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

        try:
            await client.leave_call(chat_id, close=False)
        except Exception:
            pass


    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
        thumb_path: str | None = None,
    ) -> None:
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)
        _thumb = thumb_path
        if not _thumb and config.THUMB_GEN:
            _thumb = (
                await thumb.generate(media)
                if isinstance(media, Track)
                else config.DEFAULT_THUMB
            )
        if _thumb:
            clean.register_thumb(chat_id, _thumb)

        if not media.file_path:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            return await self.play_next(chat_id)

        audio_quality = {
            "best": types.AudioQuality.STUDIO,
            "balanced": types.AudioQuality.HIGH,
            "performance": types.AudioQuality.MEDIUM,
        }.get(media.stream_mode, types.AudioQuality.HIGH)
        video_quality = {
            "best": types.VideoQuality.FHD_1080p,
            "balanced": types.VideoQuality.HD_720p,
            "performance": types.VideoQuality.SD_480p,
        }.get(media.stream_mode, types.VideoQuality.HD_720p)
        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=audio_quality,
            video_parameters=video_quality,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
        )
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
            volume = await db.get_volume(chat_id)
            if volume != 100:
                await self._change_volume(client, chat_id, volume)

            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)
                text = _lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    media.user,
                )
                keyboard = buttons.controls(chat_id)
                try:
                    if _thumb:
                        await message.edit_media(
                            media=InputMediaPhoto(
                                media=_thumb,
                                caption=text,
                            ),
                            reply_markup=keyboard,
                        )
                    else:
                        await message.edit_text(text, reply_markup=keyboard)
                except (ChatSendMediaForbidden, ChatSendPhotosForbidden, MessageIdInvalid):
                    if _thumb:
                        sent = await app.send_photo(
                            chat_id=chat_id,
                            photo=_thumb,
                            caption=text,
                            reply_markup=keyboard,
                        )
                    else:
                        sent = await app.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=keyboard,
                        )
                    media.message_id = sent.id
                self.schedule_prefetch(chat_id)
        except FileNotFoundError:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            await self.play_next(chat_id)
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)
        except (ConnectionError, ConnectionNotFound, TelegramServerError):
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])
        except RTMPStreamingUnsupported:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])


    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        if not media:
            return await self.stop(chat_id)
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)


    async def play_next(self, chat_id: int, allow_autoplay: bool = True) -> None:
        lock = self._get_play_next_lock(chat_id)
        async with lock:
            current = queue.get_current(chat_id)
            if current and getattr(current, "id", None):
                self.autoplay_history[chat_id].append(current.id)
            if loop := await db.get_loop(chat_id):
                await db.set_loop(chat_id, loop - 1)
                return await self.replay(chat_id)

            if current and await db.get_clean(chat_id):
                if current.message_id:
                    clean.create_background_task(
                        clean.delete_message(chat_id, current.message_id)
                    )
                await clean.cleanup_chat_thumbs(chat_id)

            media = await self._resolve_next_media(chat_id, current, allow_autoplay=allow_autoplay)

            if not media:
                await self.stop(chat_id)
                return
            try:
                if media.message_id:
                    await app.delete_messages(
                        chat_id=chat_id,
                        message_ids=media.message_id,
                        revoke=True,
                    )
                    media.message_id = 0
            except Exception:
                pass

            _lang = await lang.get_lang(chat_id)
            text = _lang["play_next_autoplay"] if media.user == "Autoplay" else _lang["play_next"]
            msg = await app.send_message(chat_id=chat_id, text=text)
            if not media.file_path:
                media.file_path = await self._download_with_timeout(chat_id, media)
                if not media.file_path:
                    await msg.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
                    for _ in range(5):
                        media = await self._resolve_next_media(chat_id, current, allow_autoplay=allow_autoplay)
                        if not media:
                            await self.stop(chat_id)
                            return
                        if not media.file_path:
                            media.file_path = await self._download_with_timeout(chat_id, media)
                        if media.file_path:
                            break
                    else:
                        await self.stop(chat_id)
                        return

            media.message_id = msg.id
            await self.play_media(chat_id, msg, media)

    async def ping(self) -> float:
        if not self.clients:
            return 0.0
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)


    async def decorators(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def update_handler(_, update: types.Update) -> None:
            if isinstance(update, types.StreamEnded):
                await self.play_next(update.chat_id)
            elif isinstance(update, types.ChatUpdate):
                if update.status in [
                    types.ChatUpdate.Status.KICKED,
                    types.ChatUpdate.Status.LEFT_GROUP,
                    types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                ]:
                    await self.stop(update.chat_id)


    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")
