
from pyrogram import filters, types

from carlotta import anon, app, db, lang
from carlotta.helpers import can_manage_vc


@app.on_message(filters.command(["volume", "vol"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _volume(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if len(m.command) < 2:
        vol = await db.get_volume(m.chat.id)
        return await m.reply_text(m.lang["volume_current"].format(vol))

    if not m.command[1].isdigit():
        return await m.reply_text(m.lang["volume_usage"])

    vol = int(m.command[1])
    if vol < 1:
        vol = 1
    elif vol > 200:
        vol = 200

    await anon.set_volume(m.chat.id, vol)
    await m.reply_text(m.lang["volume_changed"].format(vol, m.from_user.mention))
