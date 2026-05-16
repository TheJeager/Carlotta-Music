

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


def _item_value(item: PlaylistItem | Track, key: str, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _item_title(item: PlaylistItem | Track, lang_dict: dict) -> str:
    return _item_value(item, "title") or lang_dict["playlist_unknown_song"]


async def _ensure_playlist_chat_ready(query: types.CallbackQuery, chat_id: int) -> str | None:
    if query.message.chat.type != enums.ChatType.SUPERGROUP:
        return query.lang["playlist_play_group_only"]

    if len(queue.get_queue(chat_id)) >= config.QUEUE_LIMIT:
        return query.lang["play_queue_full"].format(config.QUEUE_LIMIT)

    play_mode = await db.get_play_mode(chat_id)
    if play_mode:
        adminlist = await db.get_admins(chat_id)
        if (
            query.from_user.id not in adminlist
            and not await db.is_auth(chat_id, query.from_user.id)
            and query.from_user.id not in app.sudoers
        ):
            return query.lang["play_admin"]

    if chat_id in db.active_calls:
        return None

    client = await db.get_client(chat_id)
    try:
        member = await app.get_chat_member(chat_id, client.id)
        if member.status in [
            enums.ChatMemberStatus.BANNED,
            enums.ChatMemberStatus.RESTRICTED,
        ]:
            try:
                await app.unban_chat_member(chat_id=chat_id, user_id=client.id)
            except Exception:
                return query.lang["play_banned"].format(
                    app.name,
                    client.id,
                    client.mention,
                    f"@{client.username}" if client.username else None,
                )
    except py_errors.ChatAdminRequired:
        return query.lang["admin_required"]
    except (py_errors.UserNotParticipant, py_errors.exceptions.bad_request_400.UserNotParticipant):
        if query.message.chat.username:
            invite_link = query.message.chat.username
            try:
                await client.resolve_peer(invite_link)
            except Exception:
                pass
        else:
            try:
                invite_link = (await app.get_chat(chat_id)).invite_link
                if not invite_link:
                    invite_link = await app.export_chat_invite_link(chat_id)
            except py_errors.ChatAdminRequired:
                return query.lang["admin_required"]
            except Exception as ex:
                return query.lang["play_invite_error"].format(type(ex).__name__)

        status = await query.message.reply_text(query.lang["play_invite"].format(app.name), quote=False)
        await asyncio.sleep(2)
        try:
            await client.join_chat(invite_link)
        except py_errors.UserAlreadyParticipant:
            pass
        except py_errors.InviteRequestSent:
            await asyncio.sleep(2)
            try:
                await app.approve_chat_join_request(chat_id, client.id)
            except py_errors.HideRequesterMissing:
                pass
            except Exception as ex:
                await status.edit_text(query.lang["play_invite_error"].format(type(ex).__name__))
                return query.lang["play_invite_error"].format(type(ex).__name__)
        except Exception as ex:
            logger.error(f"Error joining chat - {chat_id}: {ex}")
            await status.edit_text(query.lang["play_invite_error"].format(type(ex).__name__))
            return query.lang["play_invite_error"].format(type(ex).__name__)

        await status.delete()
        await client.resolve_peer(chat_id)

    return None


def _playlist_file_path(item: PlaylistItem) -> str | None:
    file_path = item.get("file_path")
    if not file_path:
        return None
    if yt.is_stream_url(file_path):
        return file_path
    return file_path if Path(file_path).exists() else None


async def _answer_playlist_query(
    query: types.CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    try:
        await query.answer(text, show_alert=show_alert)
    except py_errors.QueryIdInvalid:
        if not text:
            return
        try:
            await query.message.reply_text(text, quote=False)
        except Exception:
            pass


def _playlist_link(item: dict) -> str:
    link = item.get("url") or "https://t.me"
    return link if yt.valid(link) or yt.is_stream_url(link) else "https://t.me"


async def _save_playlist_item(user_id: int, item, lang_dict: dict) -> str:
    safe_title = _item_title(item, lang_dict)
    item_id = _item_value(item, "id")

    if not item_id:
        return lang_dict["playlist_add_failed"]

    if await db.in_playlist(user_id, item_id):
        return lang_dict["playlist_exists"].format(safe_title)

    _, total = await db.add_playlist_item(user_id, item)
    return lang_dict["playlist_added"].format(safe_title, total)


async def _play_playlist_item(query: types.CallbackQuery, item: dict) -> str | None:
    chat_id = query.message.chat.id
    error = await _ensure_playlist_chat_ready(query, chat_id)
    if error:
        return error

    stream_mode = await db.get_stream_mode(chat_id)
    track = Track(
        id=item["id"],
        channel_name=item.get("channel_name"),
        duration=item.get("duration") or "00:00",
        duration_sec=item.get("duration_sec", 0),
        file_path=_playlist_file_path(item),
        stream_mode=item.get("stream_mode") or stream_mode,
        title=item.get("title") or query.lang["playlist_unknown_song"],
        url=_playlist_link(item),
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
        await query.message.reply_text(
            query.lang["play_queued"].format(
                position,
                track.url or "https://t.me",
                track.title,
                track.duration,
                query.from_user.mention,
            ),
            reply_markup=buttons.play_queued(chat_id, track.id, query.lang["play_now"]),
            quote=False,
            disable_web_page_preview=True,
        )
        return query.lang["playlist_play_queued"]

    if not track.file_path:
        status = await query.message.reply_text(query.lang["play_downloading"], quote=False)
        track.file_path = await yt.download(
            track.url if yt.valid(track.url) else track.id,
            video=track.video,
            mode=track.stream_mode,
        )
        if not track.file_path:
            queue.remove_current(chat_id)
            await status.edit_text(query.lang["error_no_file"].format(config.SUPPORT_CHAT))
            return None

        track.message_id = status.id
        await anon.play_media(chat_id=chat_id, message=status, media=track)
    else:
        status = await query.message.reply_text(query.lang["play_next"], quote=False)
        track.message_id = status.id
        await anon.play_media(chat_id=chat_id, message=status, media=track)

    return query.lang["playlist_play_started"]


def _playlist_text(lang_dict: dict, user: types.User, section: str, item: dict, index: int, total: int) -> str:
    heading = escape(
        lang_dict["playlist_saved_title"] if section == "saved" else lang_dict["playlist_history_title"]
    )
    source = escape(item.get("channel_name") or user.first_name or "Unknown")
    duration = escape(item.get("duration") or "00:00")
    link = escape(_playlist_link(item), quote=True)
    note = escape(
        lang_dict["playlist_saved_note"]
        if section == "saved"
        else lang_dict["playlist_history_note"]
    )
    title = escape(item.get("title") or lang_dict["playlist_unknown_song"])
    return lang_dict["playlist_card"].format(
        heading,
        index + 1,
        total,
        link,
        title,
        duration,
        source,
        note,
    )


async def _edit_playlist_message(
    query: types.CallbackQuery,
    caption: str,
    markup,
    thumbnail: str | None,
) -> None:
    if thumbnail:
        try:
            await query.edit_message_media(
                InputMediaPhoto(media=thumbnail, caption=caption),
                reply_markup=markup,
            )
            return
        except Exception:
            pass

    try:
        if query.message.photo:
            await query.edit_message_caption(caption, reply_markup=markup)
        else:
            await query.edit_message_text(caption, reply_markup=markup, disable_web_page_preview=False)
    except MessageNotModified:
        pass


async def _send_playlist_message(
    message: types.Message,
    caption: str,
    markup,
    thumbnail: str | None,
) -> None:
    if thumbnail:
        await message.reply_photo(
            photo=thumbnail,
            caption=caption,
            reply_markup=markup,
            quote=True,
        )
        return

    await message.reply_text(
        caption,
        reply_markup=markup,
        quote=True,
        disable_web_page_preview=False,
    )


async def _render_playlist(
    target: types.Message | types.CallbackQuery,
    user: types.User,
    lang_dict: dict,
    section: str,
    index: int = 0,
) -> None:
    items = await db.get_playlist(user.id, section)
    if not items:
        text = (
            lang_dict["playlist_saved_empty"]
            if section == "saved"
            else lang_dict["playlist_history_empty"]
        )
        markup = buttons.playlist_empty_markup(user.id, section)
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
    saved = await db.in_playlist(user.id, item["id"])
    caption = _playlist_text(lang_dict, user, section, item, index, len(items))
    markup = buttons.playlist_markup(
        user.id,
        section,
        index,
        len(items),
        saved,
    )

    if isinstance(target, types.CallbackQuery):
        await _edit_playlist_message(target, caption, markup, item.get("thumbnail"))
        return

    await _send_playlist_message(target, caption, markup, item.get("thumbnail"))


def _current_track(chat_id: int):
    current = queue.get_current(chat_id)
    return current if current and getattr(current, "id", None) else None


def _parse_playlist_callback(data: list[str]) -> tuple[str | None, int | None, str | None, int | None]:
    if len(data) < 2:
        return None, None, None, None

    action = data[1]
    owner_id = int(data[2]) if len(data) > 2 and data[2].lstrip("-").isdigit() else None
    section = data[3] if len(data) > 3 and data[3] in {"saved", "history"} else None
    index = int(data[4]) if len(data) > 4 and data[4].lstrip("-").isdigit() else None
    return action, owner_id, section, index


async def _resolve_add_playlist_track(m: types.Message):
    if len(m.command) < 2:
        return _current_track(m.chat.id)

    query = " ".join(m.command[1:]).strip()
    if not query:
        return _current_track(m.chat.id)

    status = await m.reply_text(m.lang["playlist_add_searching"], quote=True)
    stream_mode = await db.get_stream_mode(m.chat.id)

    if yt.is_music_url(query):
        await status.edit_text(m.lang["play_resolving"])
        track = await yt.resolve_music_url(query, status.id, mode=stream_mode)
    else:
        track = await yt.search(query, status.id, mode=stream_mode)

    if not track:
        await status.edit_text(m.lang["playlist_add_not_found"].format(config.SUPPORT_CHAT))
        return False

    track.user = m.from_user.mention
    try:
        await status.delete()
    except Exception:
        pass
    return track


@app.on_message(filters.command(["playlist"]) & ~app.bl_users)
@lang.language()
async def playlist_cmd(_, m: types.Message):
    await _render_playlist(m, m.from_user, m.lang, "saved", 0)


@app.on_message(filters.command(["addpl"]) & ~app.bl_users)
@lang.language()
async def add_playlist_cmd(_, m: types.Message):
    current = await _resolve_add_playlist_track(m)
    if current is False:
        return

    if not current:
        return await m.reply_text(m.lang["playlist_add_usage"], quote=True)

    text = await _save_playlist_item(m.from_user.id, current, m.lang)
    await m.reply_text(text, quote=True)


@app.on_message(filters.command(["delpl"]) & ~app.bl_users)
@lang.language()
async def del_playlist_cmd(_, m: types.Message):
    current = _current_track(m.chat.id)
    if not current:
        return await m.reply_text(m.lang["playlist_no_active"], quote=True)

    removed = await db.del_playlist_item(m.from_user.id, current.id)
    text = (
        m.lang["playlist_removed"].format(current.title)
        if removed
        else m.lang["playlist_missing"].format(current.title)
    )
    await m.reply_text(text, quote=True)


@app.on_callback_query(filters.regex("^playlist") & ~app.bl_users)
@lang.language()
async def playlist_callbacks(_, query: types.CallbackQuery):
    action, owner_id, section, index = _parse_playlist_callback(query.data.split())
    if not action:
        return await _answer_playlist_query(query)

    if action == "savecurrent":
        if owner_id is None:
            return await _answer_playlist_query(query, query.lang["playlist_action_invalid"], show_alert=True)

        current = _current_track(owner_id)
        if not current:
            return await query.answer(query.lang["playlist_no_active"], show_alert=True)
        text = await _save_playlist_item(query.from_user.id, current, query.lang)
        return await query.answer(text, show_alert=True)

    if owner_id is None:
        return await _answer_playlist_query(query, query.lang["playlist_action_invalid"], show_alert=True)

    if query.from_user.id != owner_id:
        return await query.answer(query.lang["playlist_owner_only"], show_alert=True)

    if action == "close":
        await query.answer()
        return await query.message.delete()

    if action == "noop":
        return await query.answer()

    if section is None or index is None:
        return await _answer_playlist_query(query, query.lang["playlist_action_invalid"], show_alert=True)

    if action in {"open", "nav", "switch"}:
        await query.answer()
        return await _render_playlist(query, query.from_user, query.lang, section, index)

    items = await db.get_playlist(query.from_user.id, section)
    if not items:
        await query.answer()
        return await _render_playlist(query, query.from_user, query.lang, section, 0)

    index %= len(items)
    item = items[index]

    if action == "play":
        response = await _play_playlist_item(query, item)
        if response:
            await _answer_playlist_query(query, response, show_alert=True)
        return await _render_playlist(query, query.from_user, query.lang, section, index)

    if action == "save":
        await _answer_playlist_query(
            query,
            await _save_playlist_item(query.from_user.id, item, query.lang),
            show_alert=True,
        )
        return await _render_playlist(query, query.from_user, query.lang, section, index)

    if action == "delete":
        removed = await db.del_playlist_item(query.from_user.id, item["id"])
        await _answer_playlist_query(
            query,
            (
                query.lang["playlist_removed"].format(_item_title(item, query.lang))
                if removed
                else query.lang["playlist_missing"].format(_item_title(item, query.lang))
            ),
            show_alert=True,
        )
        next_index = max(index - 1, 0) if section == "saved" else index
        return await _render_playlist(query, query.from_user, query.lang, section, next_index)

    return await _answer_playlist_query(query, query.lang["playlist_action_invalid"], show_alert=True)
