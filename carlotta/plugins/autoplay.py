from pyrogram import filters, types

from carlotta import app, db, lang
from carlotta.helpers import admin_check, buttons


@app.on_message(filters.command(["autoplay"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def autoplay_toggle(_, m: types.Message):
    chat_id = m.chat.id
    enabled = await db.get_autoplay(chat_id)
    status = m.lang["autoplay_status_enabled"] if enabled else m.lang["autoplay_status_disabled"]
    markup = buttons.autoplay_markup(m.lang, chat_id, enabled)

    if len(m.command) == 1:
        return await m.reply_text(m.lang["autoplay_usage"].format(status), reply_markup=markup)

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
        return await m.reply_text(m.lang["autoplay_usage"].format(status), reply_markup=markup)

    desired = action_map[action]
    if desired == enabled:
        return await m.reply_text(
            m.lang["autoplay_usage"].format(status),
            reply_markup=buttons.autoplay_markup(m.lang, chat_id, desired),
        )

    await db.set_autoplay(chat_id, desired)
    key = "autoplay_enabled" if desired else "autoplay_disabled"
    await m.reply_text(m.lang[key], reply_markup=buttons.autoplay_markup(m.lang, chat_id, desired))


@app.on_callback_query(filters.regex("^autoplay\\s") & ~app.bl_users)
@lang.language()
@admin_check
async def autoplay_toggle_cb(_, query: types.CallbackQuery):
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

    enabled = await db.get_autoplay(chat_id)
    status = (
        query.lang["autoplay_status_enabled"]
        if enabled
        else query.lang["autoplay_status_disabled"]
    )

    if action == "enable":
        if enabled:
            return await query.answer(query.lang["autoplay_already_on"], show_alert=True)
        await db.set_autoplay(chat_id, True)
        enabled = True
        status = query.lang["autoplay_status_enabled"]
        await query.answer(query.lang["autoplay_enabled"], show_alert=True)
    elif action == "disable":
        if not enabled:
            return await query.answer(query.lang["autoplay_already_off"], show_alert=True)
        await db.set_autoplay(chat_id, False)
        enabled = False
        status = query.lang["autoplay_status_disabled"]
        await query.answer(query.lang["autoplay_disabled"], show_alert=True)
    else:
        return await query.answer()

    await query.edit_message_text(
        query.lang["autoplay_usage"].format(status),
        reply_markup=buttons.autoplay_markup(query.lang, chat_id, enabled),
    )
