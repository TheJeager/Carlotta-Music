import asyncio
from html import escape
from pathlib import Path
from typing import Any

from pyrogram import enums, filters, types
from pyrogram import errors as py_errors
from pyrogram.errors import MessageNotModified
from pyrogram.types import InputMediaPhoto

from carlotta import anon, app, config, db, lang, logger, queue, yt
from carlotta.helpers import Track, buttons

PlaylistItem = dict[str, Any]


def _value(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _title(item, fallback="Unknown Title"):
    return _value(item, "title") or fallback


def _code_collection():
    return db.db.playlist_codes


async def _get_or_create_code(user_id: int) -> str:
    doc = await _code_collection().find_one({"_user_id": user_id})
    if doc and doc.get("code"):
        return doc["code"]
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    import secrets
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(4))
        try:
            await _code_collection().insert_one({"_id": code, "_user_id": user_id, "code": code})
            return code
        except Exception:
            continue
    raise RuntimeError("Unable to allocate playlist code")


async def _find_user_by_code(code: str):
    code = code.strip().upper()
    if len(code) != 4:
        return None
    doc = await _code_collection().find_one({"_id": code}, {"_user_id": 1})
    return int(doc["_user_id"]) if doc and doc.get("_user_id") else None


async def _ensure_chat(query: types.CallbackQuery, chat_id: int) -> str | None:
    if query.message.chat.type != enums.ChatType.SUPERGROUP:
        return query.lang["playlist_play_group_only"]
    if len(queue.get_queue(chat_id)) >= config.QUEUE_LIMIT:
        return query.lang["play_queue_full"].format(config.QUEUE_LIMIT)
    if await db.get_play_mode(chat_id):
        admins = await db.get_admins(chat_id)
        if query.from_user.id not in admins and not await db.is_auth(chat_id, query.from_user.id) and query.from_user.id not in app.sudoers:
            return query.lang["play_admin"]
    if chat_id in db.active_calls:
        return None
    client = await db.get_client(chat_id)
    try:
        member = await app.get_chat_member(chat_id, client.id)
        if member.status in [enums.ChatMemberStatus.BANNED, enums.ChatMemberStatus.RESTRICTED]:
            try:
                await app.unban_chat_member(chat_id, client.id)
            except Exception:
                return query.lang["play_banned"].format(app.name, client.id, client.mention, f"@{client.username}" if client.username else None)
    except py_errors.ChatAdminRequired:
        return query.lang["admin_required"]
    except py_errors.UserNotParticipant:
        try:
            chat = await app.get_chat(chat_id)
            invite = chat.invite_link or await app.export_chat_invite_link(chat_id)
            try:
                await client.join_chat(invite)
            except py_errors.UserAlreadyParticipant:
                pass
            except py_errors.InviteRequestSent:
                try:
                    await app.approve_chat_join_request(chat_id, client.id)
                except Exception:
                    pass
            await client.resolve_peer(chat_id)
        except py_errors.ChatAdminRequired:
            return query.lang["admin_required"]
        except Exception as ex:
            logger.error("Playlist assistant join failed in %s: %s", chat_id, ex)
            return query.lang["play_invite_error"].format(type(ex).__name__)
    return None


def _link(item):
    url = _value(item, "url") or "https://t.me"
    return url if yt.valid(url) or yt.is_stream_url(url) else "https://t.me"


def _file(item):
    path = _value(item, "file_path")
    if not path:
        return None
    if yt.is_stream_url(path):
        return path
    return path if Path(path).exists() else None


async def _save(user_id: int, item, language: dict):
    item_id = _value(item, "id")
    if not item_id:
        return False, language["playlist_add_failed"], None
    if await db.in_playlist(user_id, item_id):
        code = await _get_or_create_code(user_id)
        return False, language["playlist_exists"].format(_title(item)), code
    _, total = await db.add_playlist_item(user_id, item)
    code = await _get_or_create_code(user_id)
    return True, language["playlist_added"].format(_title(item), total), code


async def _current(chat_id: int):
    item = queue.get_current(chat_id)
    return item if item and getattr(item, "id", None) else None


async def _resolve_track(message: types.Message):
    if len(message.command) < 2:
        return _current(message.chat.id)
    query = " ".join(message.command[1:]).strip()
    status = await message.reply_text(message.lang["playlist_add_searching"], quote=True)
    mode = await db.get_stream_mode(message.chat.id)
    try:
        if yt.is_music_url(query):
            await status.edit_text(message.lang["play_resolving"])
            track = await yt.resolve_music_url(query, status.id, mode=mode)
        else:
            track = await yt.search(query, status.id, mode=mode)
    except Exception as ex:
        logger.warning("Playlist search failed: %s", ex)
        track = None
    if not track:
        await status.edit_text(message.lang["playlist_add_not_found"].format(config.SUPPORT_CHAT))
        return False
    track.user = message.from_user.mention
    try:
        await status.delete()
    except Exception:
        pass
    return track


def _card(lang_dict, user, code, item, index, total):
    title = escape(_title(item, lang_dict["playlist_unknown_song"]))
    artist = escape(_value(item, "channel_name") or user.first_name or "Unknown")
    duration = escape(_value(item, "duration") or "00:00")
    return (
        f"<b>🎵 My Playlist</b>\n\n"
        f"<b>Code:</b> <code>{code}</code>\n"
        f"<b>Track:</b> {index + 1}/{total}\n\n"
        f"<b>{title}</b>\n"
        f"<i>{artist} • {duration}</i>"
    )


async def _render(target, user, lang_dict, index=0, code=None):
    if code:
        owner = await _find_user_by_code(code)
        if owner != user.id:
            text = "❌ Invalid or unavailable playlist code."
            if isinstance(target, types.CallbackQuery):
                return await target.answer(text, show_alert=True)
            return await target.reply_text(text, quote=True)
    else:
        code = await _get_or_create_code(user.id)

    items = await db.get_playlist(user.id, "saved")
    if not items:
        markup = buttons.playlist_empty_markup(user.id, "saved")
        text = f"<b>🎵 My Playlist</b>\n\nYour playlist is empty.\n\n<b>Playlist Code:</b> <code>{code}</code>\n\nUse <code>/addplaylist song name</code> or tap <b>Add to Playlist</b> on a playing track."
        if isinstance(target, types.CallbackQuery):
            if target.message.photo:
                await target.edit_message_caption(text, reply_markup=markup)
            else:
                await target.edit_message_text(text, reply_markup=markup)
        else:
            await target.reply_text(text, reply_markup=markup, quote=True)
        return

    index %= len(items)
    item = items[index]
    markup = buttons.playlist_markup(user.id, "saved", index, len(items), True, code=code)
    text = _card(lang_dict, user, code, item, index, len(items))
    thumb = item.get("thumbnail")
    if isinstance(target, types.CallbackQuery):
        try:
            if thumb:
                await target.edit_message_media(InputMediaPhoto(thumb, caption=text), reply_markup=markup)
            elif target.message.photo:
                await target.edit_message_caption(text, reply_markup=markup)
            else:
                await target.edit_message_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        except Exception:
            try:
                await target.edit_message_text(text, reply_markup=markup)
            except Exception:
                pass
    else:
        if thumb:
            await target.reply_photo(thumb, caption=text, reply_markup=markup, quote=True)
        else:
            await target.reply_text(text, reply_markup=markup, quote=True)


async def _play_item(query, item):
    chat_id = query.message.chat.id
    error = await _ensure_chat(query, chat_id)
    if error:
        return error
    mode = await db.get_stream_mode(chat_id)
    track = Track(
        id=item["id"],
        channel_name=item.get("channel_name"),
        duration=item.get("duration") or "00:00",
        duration_sec=item.get("duration_sec", 0),
        file_path=_file(item),
        stream_mode=item.get("stream_mode") or mode,
        title=item.get("title") or "Unknown Title",
        url=_link(item),
        thumbnail=item.get("thumbnail"),
        user=query.from_user.mention,
        video=item.get("video", False),
    )
    if not track.file_path and yt.is_stream_url(track.url):
        track.file_path = track.url
    if track.duration_sec > config.DURATION_LIMIT:
        return query.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
    await db.add_playlist_history(query.from_user.id, track)
    position = queue.add(chat_id, track)
    if position != 0 or await db.get_call(chat_id):
        await query.message.reply_text(query.lang["play_queued"].format(position, track.url, track.title, track.duration, query.from_user.mention), reply_markup=buttons.play_queued(chat_id, track.id, query.lang["play_now"]), quote=False, disable_web_page_preview=True)
        return query.lang["playlist_play_queued"]
    status = await query.message.reply_text(query.lang["play_downloading"] if not track.file_path else query.lang["play_next"], quote=False)
    if not track.file_path:
        track.file_path = await yt.download(track.id, video=track.video, mode=track.stream_mode)
    if not track.file_path:
        queue.remove_current(chat_id)
        await status.edit_text(query.lang["error_no_file"].format(config.SUPPORT_CHAT))
        return None
    track.message_id = status.id
    await anon.play_media(chat_id, status, track)
    return query.lang["playlist_play_started"]


async def _play_all(query, user_id: int, code: str):
    if query.from_user.id != user_id:
        return await query.answer("This playlist belongs to another user.", show_alert=True)
    items = await db.get_playlist(user_id, "saved")
    if not items:
        return await query.answer("Playlist is empty.", show_alert=True)
    error = await _ensure_chat(query, query.message.chat.id)
    if error:
        return await query.answer(error, show_alert=True)
    chat_id = query.message.chat.id
    available = max(config.QUEUE_LIMIT - len(queue.get_queue(chat_id)), 0)
    if available <= 0:
        return await query.answer(query.lang["play_queue_full"].format(config.QUEUE_LIMIT), show_alert=True)
    selected = items[:available]
    for item in selected:
        track = Track(
            id=item["id"], channel_name=item.get("channel_name"), duration=item.get("duration") or "00:00",
            duration_sec=item.get("duration_sec", 0), file_path=_file(item), stream_mode=item.get("stream_mode") or await db.get_stream_mode(chat_id),
            title=item.get("title") or "Unknown Title", url=_link(item), thumbnail=item.get("thumbnail"), user=query.from_user.mention, video=item.get("video", False)
        )
        queue.add(chat_id, track)
    if await db.get_call(chat_id):
        return await query.answer(f"Added {len(selected)} tracks to the queue.", show_alert=True)
    current = queue.get_current(chat_id)
    if current and not current.file_path:
        current.file_path = await yt.download(current.id, video=current.video, mode=current.stream_mode)
    if not current or not current.file_path:
        queue.remove_current(chat_id)
        return await query.answer("Unable to load the first track.", show_alert=True)
    msg = await query.message.reply_text(query.lang["play_next"], quote=False)
    current.message_id = msg.id
    await anon.play_media(chat_id, msg, current)
    await query.answer(f"Started playlist • {len(selected)} tracks", show_alert=False)


@app.on_message(filters.command(["playlist"]) & ~app.bl_users)
@lang.language()
async def playlist_cmd(_, m: types.Message):
    code = m.command[1].upper() if len(m.command) > 1 else None
    await _render(m, m.from_user, m.lang, 0, code)


@app.on_message(filters.command(["addpl", "addplaylist"]) & ~app.bl_users)
@lang.language()
async def add_playlist_cmd(_, m: types.Message):
    track = await _resolve_track(m)
    if track is False:
        return
    if not track:
        return await m.reply_text(m.lang["playlist_add_usage"], quote=True)
    _, text, code = await _save(m.from_user.id, track, m.lang)
    await m.reply_text(f"{text}\n\n<b>Playlist Code:</b> <code>{code}</code>\nUse <code>/playlist {code}</code> to open it.", quote=True)


@app.on_message(filters.command(["delpl", "delplaylist"]) & ~app.bl_users)
@lang.language()
async def del_playlist_cmd(_, m: types.Message):
    item = _current(m.chat.id)
    if not item:
        return await m.reply_text(m.lang["playlist_no_active"], quote=True)
    removed = await db.del_playlist_item(m.from_user.id, item.id)
    text = m.lang["playlist_removed"].format(item.title) if removed else m.lang["playlist_missing"].format(item.title)
    await m.reply_text(text, quote=True)


@app.on_callback_query(filters.regex(r"^playlist\s") & ~app.bl_users)
@lang.language()
async def playlist_callbacks(_, query: types.CallbackQuery):
    data = query.data.split()
    if len(data) < 2:
        return await query.answer()
    action = data[1]
    try:
        owner_id = int(data[2]) if len(data) > 2 else None
    except ValueError:
        owner_id = None
    if action == "savecurrent":
        current = _current(owner_id or query.message.chat.id)
        if not current:
            return await query.answer(query.lang["playlist_no_active"], show_alert=True)
        _, text, code = await _save(query.from_user.id, current, query.lang)
        return await query.answer(f"{text} • Code: {code}", show_alert=True)
    if owner_id != query.from_user.id:
        return await query.answer(query.lang["playlist_owner_only"], show_alert=True)
    if action == "close":
        await query.answer()
        return await query.message.delete()
    if action == "playall":
        return await _play_all(query, owner_id, data[3] if len(data) > 3 else "")
    section = data[3] if len(data) > 3 and data[3] in {"saved", "history"} else "saved"
    try:
        index = int(data[4]) if len(data) > 4 else 0
    except ValueError:
        index = 0
    items = await db.get_playlist(owner_id, section)
    if action in {"open", "nav", "switch"}:
        await query.answer()
        return await _render(query, query.from_user, query.lang, index)
    if not items:
        return await _render(query, query.from_user, query.lang, 0)
    index %= len(items)
    item = items[index]
    if action == "play":
        result = await _play_item(query, item)
        if result:
            await query.answer(result, show_alert=True)
        return await _render(query, query.from_user, query.lang, index)
    if action == "save":
        _, text, _ = await _save(query.from_user.id, item, query.lang)
        await query.answer(text, show_alert=True)
        return await _render(query, query.from_user, query.lang, index)
    if action == "delete":
        removed = await db.del_playlist_item(query.from_user.id, item["id"])
        await query.answer("Removed from playlist." if removed else "Track not found.", show_alert=True)
        return await _render(query, query.from_user, query.lang, max(index - 1, 0))
    await query.answer(query.lang["playlist_action_invalid"], show_alert=True)
