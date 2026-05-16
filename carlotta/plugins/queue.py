

from html import escape

from pyrogram import filters, types

from carlotta import app, clean, config, db, lang, queue, thumb
from carlotta.helpers import Track, buttons


def format_duration(total_seconds: int) -> str:
    total_seconds = max(int(total_seconds or 0), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return (
        f"{hours}:{minutes:02d}:{seconds:02d}"
        if hours
        else f"{minutes:02d}:{seconds:02d}"
    )


@app.on_message(filters.command(["queue", "playing"]) & filters.group & ~app.bl_users)
@lang.language()
async def _queue_func(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    _reply = await m.reply_text(m.lang["queue_fetching"])
    _queue = queue.get_queue(m.chat.id)
    if not _queue:
        return await _reply.edit_text(m.lang["queue_empty"])

    _media = _queue[0]
    _thumb = (
        await thumb.generate(_media)
        if isinstance(_media, Track)
        else config.DEFAULT_THUMB
    ) if config.THUMB_GEN else None
    if _thumb:
        clean.register_thumb(m.chat.id, _thumb)
    _text = m.lang["queue_curr"].format(
        _media.url,
        _media.title[:50],
        _media.duration,
        _media.user,
    )
    _queue.pop(0)

    _text += m.lang["queue_summary"].format(
        queue.total_items(m.chat.id, include_current=False),
        format_duration(queue.total_duration(m.chat.id, include_current=False)),
    )

    if _queue:
        _text += "<blockquote expandable>"
        for i, media in enumerate(_queue, start=1):
            if i > 15:
                break
            _text += m.lang["queue_item"].format(
                i + 1,
                escape((media.title or "Unknown Title")[:60]),
                media.duration,
            )
        if len(_queue) > 15:
            _text += m.lang["queue_more"].format(len(_queue) - 15)
        _text += "</blockquote>"

    _playing = await db.playing(m.chat.id)
    _buttons = buttons.queue_markup(
            m.chat.id,
            m.lang["playing"] if _playing else m.lang["paused"],
            _playing,
        )
    if _thumb:
        await _reply.edit_media(
            media=types.InputMediaPhoto(
                media=_thumb,
                caption=_text,
            ),
            reply_markup=_buttons,
        )
    else:
        await _reply.edit_text(
            text=_text,
            reply_markup=_buttons,
        )
