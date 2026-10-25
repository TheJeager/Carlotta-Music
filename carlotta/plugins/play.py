import asyncio
from pathlib import Path
from html import escape

from pyrogram import filters, types

from carlotta import anon, app, clean, config, db, lang, queue, tg, thumb, yt
from carlotta.helpers import buttons, utils
from carlotta.helpers._play import checkUB


def playlist_to_queue(chat_id: int, tracks: list) -> str:
    available = max(config.QUEUE_LIMIT - len(queue.get_queue(chat_id)), 0)
    tracks[:] = tracks[:available]
    text = "<blockquote expandable>"
    hidden = 0
    for index, track in enumerate(tracks, start=1):
        if index > 10:
            hidden += 1
            continue
        pos = queue.add(chat_id, track)
        title = escape(track.title or "Unknown Title")
        text += f"<b>{pos}.</b> {title}\n"
    if hidden:
        text += f"\n<i>...and {hidden} more track(s).</i>"
    text = text[:1948]
    if not text.endswith("</blockquote>"):
        text += "</blockquote>"
    return text


@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    sent = await m.reply_text(m.lang["play_searching"])
    file = None
    sender = m.from_user
    mention = sender.mention if sender else "Anonymous Admin"
    sender_id = sender.id if sender else None
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    stream_mode = await db.get_stream_mode(m.chat.id)
    tracks = []

    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)
        if not file:
            return
        file.stream_mode = stream_mode

    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )
        file.stream_mode = stream_mode

    elif url:
        if "playlist" in url and yt.valid(url):
            await sent.edit_text(m.lang["playlist_fetch"])
            tracks = await yt.playlist(
                config.PLAYLIST_LIMIT, mention, url, video, stream_mode
            )

            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        elif yt.valid(url):
            file = await yt.search(url, sent.id, video=video, mode=stream_mode)
        elif yt.is_music_url(url):
            await sent.edit_text(m.lang["play_resolving"])
            file = await yt.resolve_music_url(
                url, sent.id, video=video, mode=stream_mode
            )
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt.search(query, sent.id, video=video, mode=stream_mode)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    if not file:
        return await sent.edit_text(
            m.lang["play_usage"],
            reply_markup=buttons.play_usage_markup(
                sender_id or 0,
                m.lang["playlist_button"],
                m.lang["close"],
            ),
        )

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = mention
    if sender_id is not None:
        await db.add_playlist_history(sender_id, file)
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(
                    position,
                    file.url,
                    file.title,
                    file.duration,
                    mention,
                ),
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
            )
            if await db.get_clean(m.chat.id):
                clean.create_background_task(
                    clean.delete_message_after(m.chat.id, sent.id)
                )

            if tracks:
                added = playlist_to_queue(m.chat.id, tracks)
                if tracks:
                    msg = await app.send_message(
                        chat_id=m.chat.id,
                        text=m.lang["playlist_queued"].format(len(tracks)) + added,
                    )
                    if await db.get_clean(m.chat.id):
                        clean.create_background_task(
                            clean.delete_message_after(m.chat.id, msg.id)
                        )
            return

    _thumb = None
    if not file.file_path:
        fname = f"downloads/{file.id}.{file.stream_mode}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
            if config.THUMB_GEN:
                _thumb = await thumb.generate(file)
        else:
            await sent.edit_text(m.lang["play_downloading"])
            tasks = [yt.download(file.id, video=video, mode=file.stream_mode)]
            if config.THUMB_GEN:
                tasks.append(thumb.generate(file))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            if isinstance(results[0], BaseException) or not results[0]:
                return await sent.edit_text(
                    m.lang["play_not_found"].format(config.SUPPORT_CHAT)
                )
            file.file_path = results[0]
            if len(results) > 1:
                _thumb = None if isinstance(results[1], BaseException) else results[1]
    elif config.THUMB_GEN:
        _thumb = await thumb.generate(file)

    if _thumb:
        clean.register_thumb(m.chat.id, _thumb)

    await anon.play_media(
        chat_id=m.chat.id,
        message=sent,
        media=file,
        thumb_path=_thumb,
    )
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    if tracks:
        await app.send_message(
            chat_id=m.chat.id,
            text=m.lang["playlist_queued"].format(len(tracks)) + added,
        )
