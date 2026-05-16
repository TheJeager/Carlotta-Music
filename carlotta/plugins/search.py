
from py_yt import VideosSearch
from pyrogram import filters, types

from carlotta import app, lang
from carlotta.helpers import buttons

@app.on_message(filters.command(["search"]) & ~app.bl_users)
@lang.language()
async def _search(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["play_usage"])

    query = " ".join(m.command[1:])
    sent = await m.reply_text(m.lang["play_searching"])

    try:
        search = VideosSearch(query, limit=5)
        results = (await search.next()).get("result", [])
        if not results:
            return await sent.edit_text(m.lang["play_not_found"].format(app.name))

        text = m.lang["search_results"].format(query)
        for i, item in enumerate(results, start=1):
            text += f"<b>{i}.</b> <a href='{item['link']}'>{item['title'][:50]}</a>\n"
            text += f"   - <i>{item['duration']} | {item['viewCount']['short']}</i>\n\n"

        await sent.edit_text(
            text=text,
            reply_markup=buttons.search_markup(results, m.lang, m.from_user.id),
            disable_web_page_preview=True,
        )
    except Exception as e:
        await sent.edit_text(f"Error: {e}")
