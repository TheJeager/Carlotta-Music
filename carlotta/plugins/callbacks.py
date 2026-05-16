

import os
import re

from pyrogram import enums, errors, filters, types

from carlotta import anon, app, clean, config, db, lang, queue, tg, thumb, yt
from carlotta.helpers import admin_check, buttons, can_manage_vc


async def _ensure_callback_play_ready(query: types.CallbackQuery, chat_id: int) -> str | None:
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
    except errors.ChatAdminRequired:
        return query.lang["admin_required"]
    except (errors.UserNotParticipant, errors.exceptions.bad_request_400.UserNotParticipant):
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
            except errors.ChatAdminRequired:
                return query.lang["admin_required"]
            except Exception as ex:
                return query.lang["play_invite_error"].format(type(ex).__name__)

        status = await query.message.reply_text(
            query.lang["play_invite"].format(app.name), quote=False
        )
        try:
            await client.join_chat(invite_link)
        except errors.UserAlreadyParticipant:
            pass
        except errors.InviteRequestSent:
            try:
                await app.approve_chat_join_request(chat_id, client.id)
            except errors.HideRequesterMissing:
                pass
            except Exception as ex:
                await status.edit_text(
                    query.lang["play_invite_error"].format(type(ex).__name__)
                )
                return query.lang["play_invite_error"].format(type(ex).__name__)
        except Exception as ex:
            await status.edit_text(
                query.lang["play_invite_error"].format(type(ex).__name__)
            )
            return query.lang["play_invite_error"].format(type(ex).__name__)

        await status.delete()
        await client.resolve_peer(chat_id)

    return None


@app.on_callback_query(filters.regex("cancel_dl") & ~app.bl_users)
@lang.language()
async def cancel_dl(_, query: types.CallbackQuery):
    await query.answer()
    await tg.cancel(query)


@app.on_callback_query(filters.regex("controls") & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _controls(_, query: types.CallbackQuery):
    args = query.data.split()
    action, chat_id = args[1], int(args[2])
    qaction = len(args) == 4
    user = query.from_user.mention

    if not await db.get_call(chat_id):
        try:
            return await query.answer(query.lang["not_playing"], show_alert=True)
        except errors.QueryIdInvalid:
            try:
                await query.message.delete()
            except Exception:
                pass
            return

    if action == "status":
        return await query.answer()
    await query.answer(query.lang["processing"], show_alert=True)

    if action == "pause":
        if not await db.playing(chat_id):
            return await query.answer(
                query.lang["play_already_paused"], show_alert=True
            )
        await anon.pause(chat_id)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(chat_id, query.lang["paused"], False)
            )
        status = query.lang["paused"]
        reply = query.lang["play_paused"].format(user)

    elif action == "resume":
        if await db.playing(chat_id):
            return await query.answer(query.lang["play_not_paused"], show_alert=True)
        await anon.resume(chat_id)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(chat_id, query.lang["playing"], True)
            )
        reply = query.lang["play_resumed"].format(user)

    elif action == "skip":
        await anon.play_next(chat_id)
        status = query.lang["skipped"]
        reply = query.lang["play_skipped"].format(user)

    elif action == "force":
        pos, media = queue.check_item(chat_id, args[3])
        if not media or pos == -1:
            return await query.edit_message_text(query.lang["play_expired"])

        m_id = queue.get_current(chat_id).message_id
        queue.force_add(chat_id, media, remove=pos)
        try:
            await app.delete_messages(
                chat_id=chat_id, message_ids=[m_id, media.message_id], revoke=True
            )
            media.message_id = None
        except Exception:
            pass

        msg = await app.send_message(chat_id=chat_id, text=query.lang["play_next"])
        if not media.file_path:
            media.file_path = await yt.download(
                media.id,
                video=media.video,
                mode=media.stream_mode,
            )
        media.message_id = msg.id
        return await anon.play_media(chat_id, msg, media)

    elif action == "replay":
        media = queue.get_current(chat_id)
        media.user = user
        await anon.replay(chat_id)
        status = query.lang["replayed"]
        reply = query.lang["play_replayed"].format(user)

    elif action == "stop":
        await anon.stop(chat_id)
        status = query.lang["stopped"]
        reply = query.lang["play_stopped"].format(user)

    try:
        if action in ["skip", "replay", "stop"]:
            await query.message.reply_text(reply, quote=False)
            await query.message.delete()
        else:
            mtext = re.sub(
                r"\n\n<blockquote>.*?</blockquote>",
                "",
                query.message.caption.html or query.message.text.html,
                flags=re.DOTALL,
            )
            keyboard = buttons.controls(
                chat_id, status=status if action != "resume" else None
            )
        await query.edit_message_text(
            f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex("help") & ~app.bl_users)
@lang.language()
async def _help(_, query: types.CallbackQuery):
    data = query.data.split()
    if len(data) == 1:
        return await query.answer(url=f"https://t.me/{app.username}?start=help")

    if data[1] == "back":
        return await query.edit_message_text(
            text=query.lang["help_menu"], reply_markup=buttons.help_markup(query.lang)
        )
    elif data[1] == "close":
        try:
            await query.message.delete()
            return await query.message.reply_to_message.delete()
        except Exception:
            return

    await query.edit_message_text(
        text=query.lang[f"help_content_{data[1]}"],
        reply_markup=buttons.help_markup(query.lang, True),
    )


@app.on_callback_query(filters.regex("settings") & ~app.bl_users)
@lang.language()
@admin_check
async def _settings_cb(_, query: types.CallbackQuery):
    cmd = query.data.split()
    if len(cmd) == 1:
        return await query.answer()
    await query.answer(query.lang["processing"], show_alert=True)

    chat_id = query.message.chat.id
    _admin = await db.get_play_mode(chat_id)
    _delete = await db.get_cmd_delete(chat_id)
    _autoplay = await db.get_autoplay(chat_id)
    _clean = await db.get_clean(chat_id)
    _language = await db.get_lang(chat_id)
    _stream_mode = await db.get_stream_mode(chat_id)

    if cmd[1] == "delete":
        _delete = not _delete
        await db.set_cmd_delete(chat_id, _delete)
    elif cmd[1] == "play":
        _admin = not _admin
        await db.set_play_mode(chat_id, _admin)
    elif cmd[1] == "autoplay":
        _autoplay = not _autoplay
        await db.set_autoplay(chat_id, _autoplay)
    elif cmd[1] == "clean":
        _clean = not _clean
        await db.set_clean(chat_id, _clean)
    elif cmd[1] == "quality":
        modes = ["performance", "balanced", "best"]
        _stream_mode = modes[(modes.index(_stream_mode) + 1) % len(modes)]
        await db.set_stream_mode(chat_id, _stream_mode)

    await query.edit_message_reply_markup(
        reply_markup=buttons.settings_markup(
            query.lang,
            _admin,
            _delete,
            _autoplay,
            _clean,
            _language,
            _stream_mode,
            chat_id,
        )
    )


@app.on_callback_query(filters.regex("^clean\\s") & ~app.bl_users)
@lang.language()
@admin_check
async def clean_toggle_cb(_, query: types.CallbackQuery):
    cmd = query.data.split()
    if len(cmd) != 3:
        return await query.answer()

    action = cmd[1]
    try:
        chat_id = int(cmd[2])
    except ValueError:
        return await query.answer()
    if query.message.chat.id != chat_id:
        return await query.answer(query.lang["play_expired"], show_alert=True)

    if action == "close":
        await query.answer()
        return await query.message.delete()

    enabled = await db.get_clean(chat_id)
    status = (
        query.lang["clean_status_enabled"]
        if enabled
        else query.lang["clean_status_disabled"]
    )

    if action == "enable":
        if enabled:
            return await query.answer(query.lang["clean_already_on"], show_alert=True)
        await db.set_clean(chat_id, True)
        enabled = True
        status = query.lang["clean_status_enabled"]
        await query.answer(query.lang["clean_enabled"], show_alert=True)
    elif action == "disable":
        if not enabled:
            return await query.answer(query.lang["clean_already_off"], show_alert=True)
        await db.set_clean(chat_id, False)
        enabled = False
        status = query.lang["clean_status_disabled"]
        await query.answer(query.lang["clean_disabled"], show_alert=True)
    else:
        return await query.answer()

    await query.edit_message_text(
        query.lang["clean_usage"].format(status),
        reply_markup=buttons.clean_markup(query.lang, chat_id, enabled),
    )


@app.on_callback_query(filters.regex("^search\\s") & ~app.bl_users)
@lang.language()
async def search_callback(_, query: types.CallbackQuery):
    args = query.data.split()
    user_id = int(args[1])
    action = args[2]

    if query.from_user.id != user_id:
        return await query.answer(query.lang["playlist_owner_only"], show_alert=True)

    if action == "close":
        await query.message.delete()
        return

    video_id = args[3]
    chat_id = query.message.chat.id
    _lang = query.lang

    res = await _ensure_callback_play_ready(query, chat_id)
    if res:
        return await query.answer(res, show_alert=True)

    await query.answer(query.lang["processing"], show_alert=True)
    await query.message.delete()

    from carlotta.plugins.play import play_hndlr

    # Simulate a message for play_hndlr
    # We need a proper message object for checkUB and play_hndlr
    m = query.message
    m.from_user = query.from_user
    m.command = ["play", video_id]
    m.lang = _lang

    await play_hndlr(_, m, url=f"https://www.youtube.com/watch?v={video_id}")


@app.on_callback_query(filters.regex("^inline_dl\\s") & ~app.bl_users)
@lang.language()
async def inline_dl_cb(_, query: types.CallbackQuery):
    args = query.data.split()
    if len(args) < 3:
        return await query.answer("Invalid Request")

    dl_type = args[1]
    video_id = args[2]

    await query.answer(query.lang["play_downloading"])

    is_video = dl_type == "video"
    stream_mode = await db.get_stream_mode(query.message.chat.id) if query.message else "balanced"

    # Get metadata for better file sending
    track = await yt.search(video_id, 0, video=is_video, mode=stream_mode)
    file_path = await yt.download(video_id, video=is_video, mode=stream_mode)

    if not file_path:
        error_text = query.lang["error_no_file"].format(config.SUPPORT_CHAT)
        if query.message:
            return await query.message.reply_text(error_text)
        return await app.send_message(query.from_user.id, error_text)

    _thumb = None
    if track and config.THUMB_GEN:
        _thumb = await thumb.generate(track)

    try:
        caption = f"<u><i>Fetched by {app.name}</i></u>"
        reply_markup = buttons.search_again_markup()

        if is_video:
            if query.message:
                await query.message.reply_video(
                    video=file_path,
                    caption=caption,
                    thumb=_thumb,
                    duration=track.duration_sec if track else 0,
                    reply_markup=reply_markup,
                )
            else:
                await app.send_video(
                    chat_id=query.from_user.id,
                    video=file_path,
                    caption=caption,
                    thumb=_thumb,
                    duration=track.duration_sec if track else 0,
                    reply_markup=reply_markup,
                )
        else:
            if query.message:
                await query.message.reply_audio(
                    audio=file_path,
                    caption=caption,
                    thumb=_thumb,
                    title=track.title if track else None,
                    performer=track.channel_name if track else None,
                    duration=track.duration_sec if track else 0,
                    reply_markup=reply_markup,
                )
            else:
                await app.send_audio(
                    chat_id=query.from_user.id,
                    audio=file_path,
                    caption=caption,
                    thumb=_thumb,
                    title=track.title if track else None,
                    performer=track.channel_name if track else None,
                    duration=track.duration_sec if track else 0,
                    reply_markup=reply_markup,
                )
    except Exception as e:
        error_text = f"<b>Error:</b> {e}"
        if query.message:
            await query.message.reply_text(error_text)
        else:
            await app.send_message(query.from_user.id, error_text)
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if _thumb and os.path.exists(_thumb):
            os.remove(_thumb)
