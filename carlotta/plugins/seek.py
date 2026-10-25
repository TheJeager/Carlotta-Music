from pyrogram import filters, types

from carlotta import anon, app, config, db, lang, queue
from carlotta.helpers import can_manage_vc


@app.on_message(filters.command(["seek", "seekback"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _seek(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["play_seek_usage"].format(m.command[0]))

    try:
        to_seek = int(m.command[1])
    except (TypeError, ValueError):
        return await m.reply_text(m.lang["play_seek_usage"].format(m.command[0]))
    if to_seek < 10:
        return await m.reply_text(m.lang["play_seek_min"])

    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if not await db.playing(m.chat.id):
        return await m.reply_text(m.lang["play_already_paused"])

    media = queue.get_current(m.chat.id)
    if not media or not media.duration_sec or media.duration_sec <= 0:
        return await m.reply_text(m.lang["play_seek_no_dur"])

    sent = await m.reply_text(m.lang["play_seeking"])
    max_start = max(1, media.duration_sec - 5)
    if m.command[0] == "seekback":
        stype = m.lang["backward"]
        start_from = max(1, media.time - to_seek)
    else:
        stype = m.lang["forward"]
        start_from = media.time + to_seek
    start_from = min(start_from, max_start)

    try:
        await anon.play_media(m.chat.id, sent, media, start_from)
    except Exception:
        return await sent.edit_text(
            m.lang["play_not_found"].format(config.SUPPORT_CHAT)
        )
    media.time = start_from
    user = m.from_user.mention if m.from_user else "Anonymous Admin"
    await sent.edit_text(m.lang["play_seeked"].format(stype, start_from, user))
