import aiohttp
import re
from html import unescape
from urllib.parse import quote
from pyrogram import filters, types

from carlotta import app, lang, queue, db, clean
from carlotta.helpers import buttons

GENIUS_SEARCH_URL = "https://genius.com/api/search/multi?per_page=5&q={}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}


async def _fetch_from_genius(session: aiohttp.ClientSession, query: str):
    search_url = GENIUS_SEARCH_URL.format(quote(query))
    async with session.get(search_url, headers=HEADERS) as resp:
        if resp.status != 200:
            return None
        payload = await resp.json(content_type=None)

    sections = payload.get("response", {}).get("sections", [])
    song_hits = []
    for section in sections:
        if section.get("type") == "song":
            song_hits = section.get("hits", [])
            break

    if not song_hits:
        return None

    for hit in song_hits:
        best = hit.get("result", {})
        title = best.get("full_title") or best.get("title") or "Unknown"
        artist = best.get("primary_artist", {}).get("name", "Unknown")
        url = best.get("url")

        if not url:
            continue

        async with session.get(url, headers=HEADERS) as lyr_resp:
            if lyr_resp.status != 200:
                continue
            html = await lyr_resp.text()

        blocks = re.findall(
            r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not blocks:
            continue

        lyrics_parts = []
        for block in blocks:
            block = re.sub(r"<br\s*/?>", "\n", block, flags=re.IGNORECASE)
            block = re.sub(r"<[^>]+>", "", block)
            cleaned = unescape(block).strip()
            if cleaned:
                lyrics_parts.append(cleaned)

        lyrics = "\n".join(lyrics_parts).strip()
        if lyrics:
            return title, artist, lyrics

    return None



@app.on_message(filters.command(["lyrics"]) & ~app.bl_users)
@lang.language()
async def _lyrics(_, m: types.Message):
    if len(m.command) < 2:
        if m.chat.id in db.active_calls:
            media = queue.get_current(m.chat.id)
            if media:
                query = f"{media.title} {media.channel_name}"
            else:
                return await m.reply_text(m.lang["lyrics_usage"])
        else:
            return await m.reply_text(m.lang["lyrics_usage"])
    else:
        query = " ".join(m.command[1:])

    sent = await m.reply_text(m.lang["lyrics_searching"].format(query))

    try:
        async with aiohttp.ClientSession() as session:
            result = await _fetch_from_genius(session, query)
            if not result:
                return await sent.edit_text(m.lang["lyrics_not_found"].format(query))

            title, artist, lyrics = result
            caption = f"<b>🎶 Lyrics for {title} by {artist}</b>\n\n{lyrics}"
            if len(caption) > 4096:
                caption = caption[:4090] + "..."

            await sent.edit_text(
                text=caption,
                reply_markup=buttons.lyrics_markup(m.lang, m.from_user.id),
            )
            clean.create_background_task(
                clean.delete_message_after(m.chat.id, sent.id, delay=300)
            )
    except Exception:
        await sent.edit_text(m.lang["lyrics_not_found"].format(query))


@app.on_callback_query(filters.regex("^lyrics\\s") & ~app.bl_users)
@lang.language()
async def lyrics_callback(_, query: types.CallbackQuery):
    args = query.data.split()
    if len(args) < 3:
        return await query.answer()

    user_id = int(args[1])
    action = args[2]

    if query.from_user.id != user_id:
        return await query.answer(query.lang["playlist_owner_only"], show_alert=True)

    if action == "close":
        await query.message.delete()
