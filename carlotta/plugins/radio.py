from __future__ import annotations

from pyrogram import filters, types

from carlotta import app, lang
from carlotta.plugins.play import play_hndlr

RADIO_STATIONS: dict[str, tuple[str, str, str]] = {
    "bbc1": ("BBC Radio 1", "United Kingdom", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one"),
    "bbc2": ("BBC Radio 2", "United Kingdom", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"),
    "bbc3": ("BBC Radio 3", "United Kingdom", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_three"),
    "bbc4": ("BBC Radio 4", "United Kingdom", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_fourfm"),
    "bbcws": ("BBC World Service", "United Kingdom", "https://stream.live.vc.bbcmedia.co.uk/bbc_world_service"),
    "npr": ("NPR Program Stream", "United States", "https://npr-ice.streamguys1.com/live.mp3"),
    "kexp": ("KEXP 90.3", "United States", "https://kexp-mp3-128.streamguys1.com/kexp128.mp3"),
    "wqxr": ("WQXR Classical", "United States", "https://stream.wqxr.org/wqxr"),
    "soma": ("SomaFM Groove Salad", "United States", "https://ice4.somafm.com/groovesalad-128-mp3"),
    "jazz24": ("Jazz24", "United States", "https://live.wostreaming.net/direct/ppm-jazz24mp3-ibc1"),
    "fip": ("FIP", "France", "https://icecast.radiofrance.fr/fip-midfi.mp3"),
    "franceinfo": ("France Info", "France", "https://icecast.radiofrance.fr/franceinfo-midfi.mp3"),
    "franceinter": ("France Inter", "France", "https://icecast.radiofrance.fr/franceinter-midfi.mp3"),
    "rtl": ("RTL", "France", "https://streaming.radio.rtl.fr/rtl-1-44-128"),
    "energy": ("ENERGY Berlin", "Germany", "https://streams.energy.de/energy_berlin"),
    "wdr2": ("WDR 2", "Germany", "https://wdr-wdr2-live.icecastssl.wdr.de/wdr/wdr2/live/mp3/128/stream.mp3"),
    "swr3": ("SWR3", "Germany", "https://liveradio.swr.de/sw282p3/swr3"),
    "ndr2": ("NDR 2", "Germany", "https://icecast.ndr.de/ndr/ndr2/hamburg/mp3/128/stream.mp3"),
    "deejay": ("Radio Deejay", "Italy", "https://radiodeejay-lh.akamaihd.net/i/RadioDeejay_1@347065/master.m3u8"),
    "rai1": ("Rai Radio 1", "Italy", "https://icestreaming.rai.it/1.mp3"),
    "rai2": ("Rai Radio 2", "Italy", "https://icestreaming.rai.it/2.mp3"),
    "rai3": ("Rai Radio 3", "Italy", "https://icestreaming.rai.it/3.mp3"),
    "kissfm": ("Kiss FM", "United Kingdom", "https://stream-kiss.planetradio.co.uk/kissnational.mp3"),
    "capitalfm": ("Capital FM", "United Kingdom", "https://media-ice.musicradio.com/CapitalMP3"),
    "planetrock": ("Planet Rock", "United Kingdom", "https://media-ice.musicradio.com/PlanetRockMP3"),
    "abcnews": ("ABC News Radio", "Australia", "https://mediaserviceslive.akamaized.net/hls/live/2038315/newsradio/masterhq.m3u8"),
    "tripledj": ("triple j", "Australia", "https://live-radio01.mediahubaustralia.com/2TJW/mp3/"),
    "doublej": ("Double J", "Australia", "https://live-radio01.mediahubaustralia.com/DJDW/mp3/"),
    "radionz": ("RNZ National", "New Zealand", "https://radionz-ice.streamguys.com/national.mp3"),
    "rne1": ("RNE Radio Nacional", "Spain", "https://rtvelivestream.akamaized.net/rtvesec/rne/rne_r1_main.m3u8"),
    "los40": ("LOS40", "Spain", "https://playerservices.streamtheworld.com/api/livestream-redirect/LOS40.mp3"),
    "cadena100": ("Cadena 100", "Spain", "https://cadena100-cope.flumotion.com/playlist.m3u8"),
    "radioswissjazz": ("Radio Swiss Jazz", "Switzerland", "https://stream.srg-ssr.ch/m/rsj/mp3_128"),
    "radioswisspop": ("Radio Swiss Pop", "Switzerland", "https://stream.srg-ssr.ch/m/rsp/mp3_128"),
    "slam": ("SLAM!", "Netherlands", "https://22543.live.streamtheworld.com/WEB12_MP3_SC"),
    "qmusicnl": ("Qmusic", "Netherlands", "https://icecast-qmusicnl-cdp.triple-it.nl/Qmusic_nl_live_96.mp3"),
    "dlf": ("Deutschlandfunk", "Germany", "https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3"),
    "drp3": ("DR P3", "Denmark", "https://live-icy.gss.dr.dk/A/A05H.mp3"),
    "sveriges": ("Sveriges Radio P3", "Sweden", "https://http-live.sr.se/p3-mp3-192"),
    "ylex": ("YleX", "Finland", "https://yleuniicodnaudio-live.akamaized.net/hls/live/617138/ylxfin/playlist.m3u8"),
    "polskieradio": ("Polskie Radio Jedynka", "Poland", "https://stream4.nadaje.com:8348/radio1.mp3"),
    "radiojavan": ("Radio Javan", "Iran", "https://stream.radiojavan.com/radiojavan"),
    "redfm": ("Red FM 93.5", "India", "https://n02.radiojar.com/6phb7r0x7vzuv?rj-ttl=5&rj-tok=AAABiZz6QfEAi0CYOacSLbLhSA"),
    "radiomirchi": ("Radio Mirchi Hindi", "India", "https://streams.radio.co/s8d06d0298/listen"),
    "bigfm": ("BIG FM India", "India", "https://stream-1.zeno.fm/0r0xa792kwzuv"),
    "airfm": ("AIR FM Gold", "India", "https://air.pc.cdn.bitgravity.com/air/live/pbaudio044/playlist.m3u8"),
    "airnews": ("AIR News 24x7", "India", "https://air.pc.cdn.bitgravity.com/air/live/pbaudio001/playlist.m3u8"),
    "radio_city": ("Radio City Hindi", "India", "https://prclive4.listenon.in/Hindi"),
    "mangofm": ("Mango FM", "Sri Lanka", "https://ice31.securenetsystems.net/MANGO"),
}

PAGE_SIZE = 12


def _countries() -> list[str]:
    return sorted({country for _, country, _ in RADIO_STATIONS.values()})


def _by_country(country: str) -> list[tuple[str, str]]:
    return sorted([(c, n) for c, (n, k, _) in RADIO_STATIONS.items() if k == country], key=lambda x: x[1])


def _radio_help_text() -> str:
    return (
        "<b>📻 Radio Hub</b>\n"
        f"<b>Total Stations:</b> {len(RADIO_STATIONS)}\n"
        "<b>Tip:</b> Tap a station button to play.\n"
        "• If nothing is playing → starts instantly\n"
        "• If already playing → adds to queue\n\n"
        "<code>/radio list</code> for text list\n"
        "<code>/radio force &lt;code&gt;</code> to force play"
    )


def _radio_station_list() -> str:
    rows = ["<b>📻 Station Directory</b>"]
    for code, (name, country, _) in sorted(RADIO_STATIONS.items()):
        rows.append(f"• <code>{code}</code> — {name} ({country})")
    return "\n".join(rows)


def _country_markup(page: int = 0) -> types.InlineKeyboardMarkup:
    countries = _countries()
    start = page * PAGE_SIZE
    chunk = countries[start:start + PAGE_SIZE]
    rows = [[types.InlineKeyboardButton(f"🌍 {c}", callback_data=f"radio country {c} 0")] for c in chunk]
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("◀️", callback_data=f"radio countries {page - 1}"))
    nav.append(types.InlineKeyboardButton(f"{page + 1}/{max(1, (len(countries) - 1) // PAGE_SIZE + 1)}", callback_data="radio noop"))
    if start + PAGE_SIZE < len(countries):
        nav.append(types.InlineKeyboardButton("▶️", callback_data=f"radio countries {page + 1}"))
    rows.append(nav)
    rows.append([types.InlineKeyboardButton("🇮🇳 India Stations", callback_data="radio country India 0")])
    return types.InlineKeyboardMarkup(rows)


def _station_markup(country: str, page: int = 0) -> types.InlineKeyboardMarkup:
    stations = _by_country(country)
    start = page * PAGE_SIZE
    chunk = stations[start:start + PAGE_SIZE]
    rows = [[types.InlineKeyboardButton(f"🎧 {name}", callback_data=f"radio play {code}")] for code, name in chunk]
    nav = [types.InlineKeyboardButton("🔙 Countries", callback_data="radio countries 0")]
    if page > 0:
        nav.append(types.InlineKeyboardButton("◀️", callback_data=f"radio country {country} {page - 1}"))
    if start + PAGE_SIZE < len(stations):
        nav.append(types.InlineKeyboardButton("▶️", callback_data=f"radio country {country} {page + 1}"))
    rows.append(nav)
    return types.InlineKeyboardMarkup(rows)


@app.on_message(filters.command(["radio", "station", "stations"]) & filters.group & ~app.bl_users)
@lang.language()
async def radio_handler(_, m: types.Message) -> None:
    if len(m.command) == 1:
        return await m.reply_text(_radio_help_text(), reply_markup=_country_markup())

    arg1 = m.command[1].lower().strip()
    if arg1 == "list":
        listing = _radio_station_list()
        for chunk in (listing[i:i + 3900] for i in range(0, len(listing), 3900)):
            await m.reply_text(chunk)
        return

    force = arg1 == "force"
    station_code = m.command[2].lower().strip() if force and len(m.command) > 2 else arg1
    await _play_station(_, m, station_code, force=force)


async def _play_station(_, m: types.Message, station_code: str, force: bool = False) -> None:
    station = RADIO_STATIONS.get(station_code)
    if not station:
        return await m.reply_text("❌ Unknown station code. Use <code>/radio</code> to browse all stations.")
    station_name, country, stream_url = station
    m.command = ["playforce" if force else "play", f"{station_name} ({country})"]
    await m.reply_text(
        f"📡 <b>Selected:</b> {station_name} ({country})\n"
        f"<b>Code:</b> <code>{station_code}</code>\n"
        f"<b>Action:</b> {'Force Play' if force else 'Auto play / queue'}"
    )
    await play_hndlr(_, m, force=force, m3u8=True, url=stream_url)


@app.on_callback_query(filters.regex(r"^radio\s") & ~app.bl_users)
@lang.language()
async def radio_callback(_, query: types.CallbackQuery) -> None:
    parts = query.data.split()
    if len(parts) < 2:
        return await query.answer()
    action = parts[1]
    if action == "noop":
        return await query.answer()
    if action == "countries":
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        await query.message.edit_text(_radio_help_text(), reply_markup=_country_markup(page))
        return await query.answer()
    if action == "country" and len(parts) >= 3:
        country = parts[2]
        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        await query.message.edit_text(
            f"<b>📻 {country} Stations</b>\nSelect any station below.",
            reply_markup=_station_markup(country, page),
        )
        return await query.answer()
    if action == "play" and len(parts) >= 3:
        code = parts[2]
        m = query.message
        m.command = ["radio", code]
        await query.answer("Loading station...", show_alert=False)
        return await _play_station(_, m, code, force=False)
