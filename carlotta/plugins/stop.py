from pyrogram import filters, types

from carlotta import anon, app, db, lang
from carlotta.helpers import can_manage_vc


@app.on_message(filters.command(["end", "stop"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _stop(_, m: types.Message):
    if len(m.command) > 1:
        return

    call = await db.get_call(m.chat.id)
    await anon.stop(m.chat.id)
    if not call:
        return await m.reply_text(m.lang["not_playing"])

    mention = m.from_user.mention if m.from_user else "Anonymous Admin"
    await m.reply_text(m.lang["play_stopped"].format(mention))
