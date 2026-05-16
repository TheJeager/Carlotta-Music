from pyrogram import filters, types

from carlotta import app, db, lang
from carlotta.helpers import admin_check, buttons


@app.on_message(filters.command(["clean"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def clean_toggle(_, m: types.Message):
    chat_id = m.chat.id
    enabled = await db.get_clean(chat_id)
    status = m.lang["clean_status_enabled"] if enabled else m.lang["clean_status_disabled"]
    markup = buttons.clean_markup(m.lang, chat_id, enabled)

    if len(m.command) == 1:
        return await m.reply_text(m.lang["clean_usage"].format(status), reply_markup=markup)

    action = m.command[1].lower()
    action_map = {
        "on": True,
        "off": False,
        "enable": True,
        "disable": False,
        "enabled": True,
        "disabled": False,
    }
    if action not in action_map:
        return await m.reply_text(m.lang["clean_usage"].format(status), reply_markup=markup)

    desired = action_map[action]
    if desired == enabled:
        return await m.reply_text(
            m.lang["clean_usage"].format(status),
            reply_markup=buttons.clean_markup(m.lang, chat_id, desired),
        )

    await db.set_clean(chat_id, desired)
    key = "clean_enabled" if desired else "clean_disabled"
    await m.reply_text(m.lang[key], reply_markup=buttons.clean_markup(m.lang, chat_id, desired))
