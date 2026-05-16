from pyrogram import filters, types

from carlotta import app, db, lang
from carlotta.helpers import admin_check, buttons

STREAM_MODES = ("performance", "balanced", "best")
STREAM_MODE_ALIASES = {
    "fast": "performance",
    "lagless": "performance",
    "nolag": "performance",
    "smooth": "performance",
    "default": "balanced",
    "auto": "balanced",
    "clean": "best",
    "hifi": "best",
}


@app.on_message(filters.command(["quality", "streammode"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def stream_quality(_, m: types.Message):
    if len(m.command) == 1:
        mode = await db.get_stream_mode(m.chat.id)
        return await m.reply_text(
            m.lang["stream_mode_panel"].format(m.lang[f"stream_mode_{mode}"]),
            reply_markup=buttons.quality_markup(m.lang, m.chat.id, mode),
        )

    requested = m.command[1].lower()
    requested = STREAM_MODE_ALIASES.get(requested, requested)
    if requested not in STREAM_MODES:
        return await m.reply_text(m.lang["stream_mode_usage"])

    await db.set_stream_mode(m.chat.id, requested)
    await m.reply_text(
        m.lang["stream_mode_changed"].format(m.lang[f"stream_mode_{requested}"])
    )


@app.on_callback_query(filters.regex("^quality\\s") & ~app.bl_users)
@lang.language()
@admin_check
async def stream_quality_cb(_, query: types.CallbackQuery):
    cmd = query.data.split()
    if len(cmd) < 3:
        return await query.answer()

    action, chat_id = cmd[1], int(cmd[2])
    if chat_id != query.message.chat.id:
        return await query.answer(query.lang["play_expired"], show_alert=True)

    if action == "close":
        await query.answer()
        return await query.message.delete()

    if action != "set" or len(cmd) < 4:
        return await query.answer()

    mode = cmd[3]
    if mode not in STREAM_MODES:
        return await query.answer(query.lang["stream_mode_usage"], show_alert=True)

    current = await db.get_stream_mode(chat_id)
    if current != mode:
        await db.set_stream_mode(chat_id, mode)
        await query.answer(
            query.lang["stream_mode_changed_short"].format(
                query.lang[f"stream_mode_{mode}"]
            )
        )
    else:
        await query.answer(
            query.lang["stream_mode_current"].format(query.lang[f"stream_mode_{mode}"])
        )

    await query.edit_message_text(
        query.lang["stream_mode_panel"].format(query.lang[f"stream_mode_{mode}"]),
        reply_markup=buttons.quality_markup(query.lang, chat_id, mode),
    )
