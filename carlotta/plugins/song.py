import os
import asyncio
from pathlib import Path

from pyrogram import filters, types, errors

from carlotta import app, config, db, lang, yt

INLINE_STORE_CHAT_ID = getattr(config, "LOGGER_ID", None)

async def _ensure_mp3(source_file: str, track=None) -> str:
    """
    Converts a source audio file to high-quality MP3 (320kbps)
    and embeds metadata/thumbnail if provided.
    """
    mp3_file = f"{os.path.splitext(source_file)[0]}.mp3"

    # Base command for high-quality 320kbps CBR conversion
    command = [
        "ffmpeg", "-y", "-i", source_file
    ]

    thumb_path = None
    if track and track.thumbnail:
        from carlotta import thumb
        # Temporarily generate/get thumbnail path
        thumb_path = await thumb.save_thumb(f"cache/inline_thumb_{track.id}.jpg", track.thumbnail)
        if thumb_path and os.path.exists(thumb_path):
            command.extend(["-i", thumb_path])

    command.extend([
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", "320k",
    ])

    if track:
        # Embed metadata
        title = track.title or "Unknown"
        performer = track.channel_name or "Radha Player"
        command.extend([
            "-metadata", f"title={title}",
            "-metadata", f"artist={performer}",
        ])
        if thumb_path and os.path.exists(thumb_path):
            # Map the second input (thumbnail) as video stream and set as attachment
            command.extend([
                "-map", "0:a",
                "-map", "1:v",
                "-disposition:v", "attached_pic",
            ])

    command.append(mp3_file)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate()

    if thumb_path and os.path.exists(thumb_path):
        try: os.remove(thumb_path)
        except: pass

    if process.returncode == 0 and Path(mp3_file).exists():
        if source_file != mp3_file and os.path.exists(source_file):
            os.remove(source_file)
        return mp3_file
    return source_file


@app.on_message(filters.private & filters.text & ~filters.regex(r"^/") & ~app.bl_users)
@lang.language()
async def advanced_song_private(_, m: types.Message):
    if not m.text:
        return

    query = m.text.strip()
    if len(query) < 2:
        return

    stream_mode = await db.get_stream_mode(m.chat.id)
    sent = await m.reply_text(m.lang["play_searching"], quote=True)
    tracks = await yt.advanced_search(
        query=query,
        limit=5,
        mode=stream_mode,
    )
    if not tracks:
        return await sent.edit_text(m.lang["play_not_found"].format(config.SUPPORT_CHAT))

    first_track = tracks[0]
    first_file = await yt.download(first_track.id, video=False, mode=stream_mode)
    if first_file:
        audio_file = await _ensure_mp3(first_file, track=first_track)
        try:
            await m.reply_audio(
                audio=audio_file,
                title=first_track.title or query,
                performer=first_track.channel_name or app.name,
                duration=first_track.duration_sec or 0,
                caption=f"<b>{first_track.title or query}</b>",
            )
        finally:
            if os.path.exists(audio_file):
                os.remove(audio_file)

    await sent.delete()


@app.on_inline_query(~app.bl_users)
async def song_inline_query(_, inline_query: types.InlineQuery):
    query = (inline_query.query or "").strip()
    if len(query) < 2:
        try:
            return await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True,
                switch_pm_text="Type a song name",
                switch_pm_parameter="song_search",
            )
        except errors.QueryIdInvalid:
            return

    tracks = await yt.advanced_search(query=query, limit=10, mode="balanced")
    if not tracks:
        try:
            return await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True,
                switch_pm_text="No songs found",
                switch_pm_parameter="song_search",
            )
        except errors.QueryIdInvalid:
            return

    async def _cache_audio_file_id(track):
        # 1. Check persistent cache (MongoDB)
        cached_id = await db.get_inline_cache(track.id)
        if cached_id:
            return cached_id

        # 2. Download and convert if not cached
        source_file = await yt.download(track.id, video=False, mode="balanced")
        if not source_file:
            return None

        audio_file = await _ensure_mp3(source_file, track=track)
        try:
            target_chat_id = INLINE_STORE_CHAT_ID if INLINE_STORE_CHAT_ID else "me"
            sent_audio = await app.send_audio(
                chat_id=target_chat_id,
                audio=audio_file,
                title=track.title or "Unknown Title",
                performer=track.channel_name or app.name,
                duration=track.duration_sec or 0,
            )
            if not sent_audio or not sent_audio.audio:
                return None

            file_id = sent_audio.audio.file_id
            # Save to persistent cache
            await db.set_inline_cache(track.id, file_id)
            return file_id
        except Exception:
            return None
        finally:
            if os.path.exists(audio_file):
                os.remove(audio_file)

    # Resolve all tracks. Cached ones return immediately; others download in parallel.
    # We use a timeout to ensure we respond to Telegram before the inline query expires.
    tasks_list = [asyncio.create_task(_cache_audio_file_id(track)) for track in tracks]

    try:
        # Give it up to 15 seconds to fetch as many as possible
        await asyncio.wait(tasks_list, timeout=15)
    except Exception:
        pass

    file_ids = []
    for t in tasks_list:
        if t.done() and not t.cancelled():
            try:
                file_ids.append(t.result())
            except Exception:
                file_ids.append(None)
        else:
            file_ids.append(None)
            # Cancel unfinished tasks to save resources
            if not t.done():
                t.cancel()

    results = []
    for index, (track, f_id) in enumerate(zip(tracks, file_ids), start=1):
        if not f_id:
            continue

        results.append(
            types.InlineQueryResultCachedAudio(
                id=f"{track.id}_{index}",
                audio_file_id=f_id,
                caption=f"<b>{track.title or 'Unknown Title'}</b>",
            )
        )

    if not results:
        try:
            return await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True,
                switch_pm_text="No playable audio streams found",
                switch_pm_parameter="song_search",
            )
        except errors.QueryIdInvalid:
            return

    try:
        await inline_query.answer(
            results=results,
            cache_time=1,
            is_personal=True,
            switch_pm_text="Select a song to send directly",
            switch_pm_parameter="song_search",
        )
    except errors.QueryIdInvalid:
        pass
