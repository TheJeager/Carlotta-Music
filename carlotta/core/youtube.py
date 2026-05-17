import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from py_yt import Playlist, VideosSearch

from carlotta import config, logger
from carlotta.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "carlotta/cookies"
        self.warned = False
        self._download_locks: dict[str, asyncio.Lock] = {}
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )
        self.music_domains = {
            "soundcloud.com",
            "on.soundcloud.com",
            "music.apple.com",
            "geo.music.apple.com",
            "deezer.com",
            "www.deezer.com",
            "tidal.com",
            "listen.tidal.com",
            "bandcamp.com",
            "spotify.com",
            "open.spotify.com",
            "jiosaavn.com",
            "www.jiosaavn.com",
            "saavn.com",
            "www.saavn.com",
        }

    @staticmethod
    def normalize_mode(mode: str | None) -> str:
        return mode if mode in {"best", "balanced", "performance"} else "balanced"

    @staticmethod
    def trim_title(title: str | None, limit: int = 80) -> str | None:
        return title[:limit] if title else title

    @staticmethod
    def format_duration(seconds: int) -> str:
        minutes, secs = divmod(max(seconds, 0), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    def extract_video_id(self, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
            return value

        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        path = parsed.path.strip("/")

        if (host == "youtu.be" or host.endswith(".youtu.be")) and path:
            candidate = path.split("/")[0]
            return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None

        if host == "youtube.com" or host.endswith(".youtube.com"):
            if path == "watch":
                candidate = parse_qs(parsed.query).get("v", [None])[0]
                return candidate if candidate and re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None
            if path.startswith("shorts/") or path.startswith("embed/"):
                candidate = path.split("/")[1]
                return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None

        return None

    def get_cookies(self):
        if not self.checked:
            for file in os.listdir(self.cookie_dir):
                if file.endswith(".txt"):
                    self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for url in urls:
                name = url.split("/")[-1]
                link = "https://batbin.me/raw/" + name
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(f"{self.cookie_dir}/{name}.txt", "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    def is_music_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(host == domain or host.endswith(f".{domain}") for domain in self.music_domains)

    @staticmethod
    async def _resolve_spotify_metadata(url: str) -> tuple[str, str, str]:
        """Best-effort Spotify metadata via public oEmbed endpoint."""
        endpoint = "https://open.spotify.com/oembed"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params={"url": url}, timeout=8) as resp:
                    if resp.status != 200:
                        return "", "", ""
                    payload = await resp.json()
        except Exception:
            return "", "", ""

        title = (payload.get("title") or "").strip()
        if not title:
            return "", "", ""

        # Common oEmbed format is "Song Name - Artist Name"
        song, sep, artist = title.partition(" - ")
        if sep:
            return song.strip(), artist.strip(), ""
        return title, "", ""

    def is_stream_url(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return path.endswith((".m3u8", ".mpd", ".mp3", ".aac", ".flac", ".wav", ".ogg"))

    def _build_track(
        self,
        *,
        data: dict,
        m_id: int = 0,
        video: bool = False,
        mode: str = "balanced",
        fallback_url: str | None = None,
    ) -> Track | None:
        track_id = data.get("id") or self.extract_video_id(data.get("url") or fallback_url)
        if not track_id:
            return None

        thumbnails = data.get("thumbnails") or []
        thumbnail = None
        if thumbnails:
            thumb = thumbnails[-1]
            if isinstance(thumb, dict):
                thumbnail = thumb.get("url")
            elif isinstance(thumb, str):
                thumbnail = thumb
        if thumbnail:
            thumbnail = thumbnail.split("?")[0]

        channel = data.get("channel") or {}
        if not isinstance(channel, dict):
            channel = {}

        url = data.get("link") or data.get("webpage_url") or fallback_url or f"{self.base}{track_id}"
        if isinstance(url, str) and "&list=" in url:
            url = url.split("&list=", 1)[0]

        duration = data.get("duration")
        duration_sec = data.get("duration_sec")
        if duration_sec is None:
            raw_duration = data.get("duration_seconds") or data.get("duration")
            if isinstance(raw_duration, int):
                duration_sec = raw_duration
            else:
                duration_sec = utils.to_seconds(duration) if duration else 0
        if not duration:
            duration = self.format_duration(duration_sec) if duration_sec else "00:00"

        return Track(
            id=track_id,
            album=data.get("album"),
            channel_name=channel.get("name") or data.get("channel_name") or data.get("uploader") or data.get("artist"),
            duration=duration or "00:00",
            duration_sec=duration_sec or 0,
            message_id=m_id,
            title=self.trim_title(data.get("title")),
            thumbnail=thumbnail,
            url=url,
            view_count=(data.get("viewCount") or {}).get("short") if isinstance(data.get("viewCount"), dict) else data.get("view_count"),
            video=video,
            stream_mode=mode,
        )

    @staticmethod
    def _clean_query_value(value: str | None) -> str:
        if not value:
            return ""
        value = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value)
        value = re.sub(
            r"\b(official|video|audio|lyrics|lyrical|visualizer|hd|4k|remix|version)\b",
            " ",
            value,
            flags=re.IGNORECASE,
        )
        return " ".join(value.split()).strip(" -")

    def _split_title_artist(self, title: str | None) -> tuple[str, str]:
        cleaned = self._clean_query_value(title)
        if not cleaned:
            return "", ""

        for separator in (" - ", " – ", " — ", ": "):
            if separator in cleaned:
                left, right = cleaned.split(separator, 1)
                artist = self._clean_query_value(left)
                song = self._clean_query_value(right)
                if artist and song:
                    return artist, song
        return "", cleaned

    def _track_artist_hints(self, track: Track | None) -> list[str]:
        hints: list[str] = []
        if not track:
            return hints

        for value in self._artist_candidates(track):
            if value and value not in hints:
                hints.append(value)

        title_artist, _ = self._split_title_artist(getattr(track, "title", None))
        if title_artist and title_artist not in hints:
            hints.append(title_artist)
        return hints

    def _artist_candidates(self, track: Track | None) -> list[str]:
        if not track:
            return []

        base = self._clean_query_value(getattr(track, "channel_name", None))
        if not base:
            return []

        cleaned = re.sub(r"\s*-\s*topic$", "", base, flags=re.IGNORECASE).strip()
        if not cleaned:
            return []

        candidates: list[str] = []
        for value in re.split(
            r"\s*(?:,|&|/|\bx\b|\bwith\b|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b)\s*",
            cleaned,
            flags=re.IGNORECASE,
        ):
            candidate = self._clean_query_value(value)
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if cleaned not in candidates:
            candidates.insert(0, cleaned)
        return candidates

    def _primary_artist(self, track: Track | None) -> str:
        candidates = self._track_artist_hints(track)
        return candidates[0] if candidates else ""

    def _recommendation_queries(self, track: Track) -> list[str]:
        raw_title = self._clean_query_value(getattr(track, "title", None))
        title_artist, song_title = self._split_title_artist(raw_title)
        title = song_title or raw_title
        channel = self._clean_query_value(getattr(track, "channel_name", None))
        artist = self._primary_artist(track) or title_artist
        album = self._clean_query_value(getattr(track, "album", None))
        queries: list[str] = []
        for value in (
            " - ".join(part for part in [artist, title] if part),
            " - ".join(part for part in [title, channel] if part),
            f"{artist} {album}".strip() if artist and album else "",
            title,
            f"{channel} {title}".strip() if channel else "",
            f"{artist} songs".strip() if artist else "",
            f"{title} audio".strip() if title else "",
        ):
            if value and value not in queries:
                queries.append(value)
        return queries

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _text_matches(self, left: str | None, right: str | None) -> bool:
        left_norm = self._normalize_text(self._clean_query_value(left))
        right_norm = self._normalize_text(self._clean_query_value(right))
        if not left_norm or not right_norm:
            return False
        return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm

    def _is_same_track(self, source: Track, candidate: Track) -> bool:
        if not source or not candidate:
            return False
        if getattr(source, "id", None) and source.id == candidate.id:
            return True

        source_title = self._clean_query_value(getattr(source, "title", None))
        candidate_title = self._clean_query_value(getattr(candidate, "title", None))
        if self._text_matches(source_title, candidate_title):
            source_artist = self._primary_artist(source)
            candidate_artist = self._primary_artist(candidate)
            if not source_artist or not candidate_artist:
                return True
            return self._text_matches(source_artist, candidate_artist)
        return False

    def _related_track_score(self, source: Track, candidate: Track) -> int:
        score = 0
        source_artist = self._primary_artist(source)
        candidate_artist = self._primary_artist(candidate)
        if source_artist and candidate_artist and self._text_matches(source_artist, candidate_artist):
            score += 8

        source_album = self._clean_query_value(getattr(source, "album", None))
        candidate_album = self._clean_query_value(getattr(candidate, "album", None))
        if source_album and candidate_album and self._text_matches(source_album, candidate_album):
            score += 3

        source_title = self._clean_query_value(getattr(source, "title", None))
        candidate_title = self._clean_query_value(getattr(candidate, "title", None))
        if source_title and candidate_title:
            if self._text_matches(source_title, candidate_title):
                score -= 10
            elif any(token in candidate_title.lower() for token in ("mix", "playlist", "live", "hour", "loop")):
                score -= 2
        return score

    def _score_search_candidate(
        self,
        item: dict,
        *,
        title_hint: str | None = None,
        artist_hint: str | None = None,
        album_hint: str | None = None,
    ) -> int:
        title = self._clean_query_value(item.get("title"))
        channel = self._clean_query_value((item.get("channel") or {}).get("name"))
        album = self._clean_query_value(album_hint)
        score = 0

        if title_hint and self._text_matches(title, title_hint):
            score += 8
        if artist_hint and (
            self._text_matches(channel, artist_hint)
            or self._text_matches(title, artist_hint)
        ):
            score += 10
        if album and self._text_matches(title, album):
            score += 4

        duration = item.get("duration")
        if duration and duration != "0:00":
            score += 1
        return score

    async def _extract_info(self, query: str, *, extract_flat: bool = False) -> dict | None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": not extract_flat,
            "extract_flat": extract_flat,
        }
        if cookie := self.get_cookies():
            opts["cookiefile"] = cookie

        def _extract() -> dict | None:
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    return ydl.extract_info(query, download=False)
                except Exception as ex:
                    logger.warning("YouTube extract failed for %s: %s", query, ex)
                    return None

        return await asyncio.to_thread(_extract)

    async def resolve_music_url(
        self,
        url: str,
        m_id: int,
        video: bool = False,
        mode: str = "balanced",
    ) -> Track | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if host == "open.spotify.com" or host.endswith(".spotify.com"):
            title, artist, album = await self._resolve_spotify_metadata(url)
            parts = [part.strip() for part in [artist, title, album] if part and part.strip()]
            if parts:
                query = " - ".join(dict.fromkeys(parts))
                return await self.search(query, m_id, video=video, mode=mode)

        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "noplaylist": True,
        }
        if cookie := self.get_cookies():
            opts["cookiefile"] = cookie

        def _extract() -> dict | None:
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    return ydl.extract_info(url, download=False)
                except Exception as ex:
                    logger.warning("Music URL resolution failed for %s: %s", url, ex)
                    return None

        info = await asyncio.to_thread(_extract)
        if not info:
            return None

        title = info.get("track") or info.get("title") or ""
        artist = info.get("artist") or info.get("uploader") or info.get("channel") or ""
        album = info.get("album") or ""
        parts = [part.strip() for part in [artist, title, album] if part and part.strip()]
        if not parts:
            return None

        query = " - ".join(dict.fromkeys(parts))
        return await self.search(query, m_id, video=video, mode=mode)

    async def search_multi(
        self,
        query: str,
        limit: int = 15,
        video: bool = False,
        mode: str = "balanced",
    ) -> list[Track]:
        mode = self.normalize_mode(mode)
        try:
            search = VideosSearch(
                query,
                limit=limit,
                language="en",
                region="US",
                with_live=False,
            )
            results = (await search.next()).get("result", [])
        except Exception:
            return []

        tracks = []
        for item in results:
            track = self._build_track(data=item, video=video, mode=mode)
            if track:
                tracks.append(track)
        return tracks

    async def advanced_search(
        self,
        query: str,
        limit: int = 5,
        video: bool = False,
        mode: str = "balanced",
    ) -> list[Track]:
        mode = self.normalize_mode(mode)
        candidates = await self.search_multi(
            query=query,
            limit=max(limit * 3, 10),
            video=video,
            mode=mode,
        )
        if not candidates:
            return []

        cleaned_query = self._clean_query_value(query)
        artist_hint, title_hint = self._split_title_artist(cleaned_query)
        scored: list[tuple[int, Track]] = []
        seen: set[str] = set()

        for index, track in enumerate(candidates):
            if not track or not track.id or track.id in seen:
                continue
            seen.add(track.id)

            score = 0
            if title_hint and self._text_matches(track.title, title_hint):
                score += 8
            elif cleaned_query and self._text_matches(track.title, cleaned_query):
                score += 5

            primary_artist = self._primary_artist(track)
            if artist_hint and primary_artist and self._text_matches(primary_artist, artist_hint):
                score += 7

            if track.duration_sec > 0:
                score += 2
            if track.duration_sec > 900:
                score -= 2

            score -= index
            scored.append((score, track))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [track for _, track in scored[:limit]]

    async def search(self, query: str, m_id: int, video: bool = False, mode: str = "balanced") -> Track | None:
        mode = self.normalize_mode(mode)

        resolved_id = self.extract_video_id(query)
        direct_query = self.base + resolved_id if resolved_id else query

        if self.valid(direct_query):
            info = await self._extract_info(direct_query)
            if info:
                return self._build_track(
                    data=info,
                    m_id=m_id,
                    video=video,
                    mode=mode,
                    fallback_url=direct_query,
                )

        try:
            _search = VideosSearch(query, limit=1, language="en", region="US", with_live=False)
            results = await _search.next()
        except Exception:
            return None
        if results and results["result"]:
            return self._build_track(data=results["result"][0], m_id=m_id, video=video, mode=mode)
        return None

    async def search_best(
        self,
        query: str,
        m_id: int,
        *,
        video: bool = False,
        mode: str = "balanced",
        title_hint: str | None = None,
        artist_hint: str | None = None,
        album_hint: str | None = None,
        limit: int = 5,
    ) -> Track | None:
        mode = self.normalize_mode(mode)

        resolved_id = self.extract_video_id(query)
        direct_query = self.base + resolved_id if resolved_id else query

        if self.valid(direct_query):
            info = await self._extract_info(direct_query)
            if info:
                return self._build_track(
                    data=info,
                    m_id=m_id,
                    video=video,
                    mode=mode,
                    fallback_url=direct_query,
                )

        try:
            search = VideosSearch(
                query,
                limit=limit,
                language="en",
                region="US",
                with_live=False,
            )
            results = (await search.next()).get("result", [])
        except Exception:
            return None

        best_item = None
        best_score = -1
        for item in results:
            score = self._score_search_candidate(
                item,
                title_hint=title_hint,
                artist_hint=artist_hint,
                album_hint=album_hint,
            )
            if score > best_score:
                best_score = score
                best_item = item

        if best_item:
            return self._build_track(data=best_item, m_id=m_id, video=video, mode=mode)
        return None

    async def playlist(
        self,
        limit: int,
        user: str,
        url: str,
        video: bool,
        mode: str = "balanced",
    ) -> list[Track | None]:
        tracks = []
        mode = self.normalize_mode(mode)

        try:
            plist = await Playlist.get(url)
            videos = plist.get("videos") or []
            for data in videos[:limit]:
                track = self._build_track(data=data, video=video, mode=mode)
                if track:
                    track.user = user
                    tracks.append(track)
        except Exception as ex:
            logger.warning("Playlist.get failed for %s: %s", url, ex)

        if tracks:
            return tracks

        info = await self._extract_info(url, extract_flat=True)
        if not info:
            return tracks

        entries = info.get("entries") or []
        for entry in entries[:limit]:
            if not isinstance(entry, dict):
                continue
            track = self._build_track(data=entry, video=video, mode=mode)
            if track:
                track.user = user
                tracks.append(track)
        return tracks

    async def related_tracks(
        self,
        track: Track | None,
        limit: int = 4,
        mode: str = "balanced",
        refresh_token: int = 0,
    ) -> list[Track]:
        if not track:
            return []

        mode = self.normalize_mode(mode)
        queries = self._recommendation_queries(track)
        if not queries:
            return []

        suggestions: dict[str, Track] = {}
        seen = {getattr(track, "id", None)}
        search_limit = max(limit * 3, 10)

        for query in queries:
            try:
                search = VideosSearch(
                    query,
                    limit=search_limit,
                    language="en",
                    region="US",
                    with_live=False,
                )
                results = (await search.next()).get("result", [])
            except Exception:
                continue

            for item in results:
                built = self._build_track(
                    data=item,
                    video=getattr(track, "video", False),
                    mode=mode,
                )
                if not built or built.id in seen:
                    continue
                seen.add(built.id)
                suggestions[built.id] = built

        fallback_items = []
        if len(suggestions) < limit:
            fallback_items = await self._extract_related_candidates(track, mode=mode)
            for built in fallback_items:
                if not built or built.id in seen:
                    continue
                seen.add(built.id)
                suggestions[built.id] = built

        items = [item for item in suggestions.values() if not self._is_same_track(track, item)]
        random.Random(f"{getattr(track, 'id', 'mix')}:{refresh_token}").shuffle(items)
        items.sort(key=lambda item: self._related_track_score(track, item), reverse=True)
        return items[:limit]

    async def _extract_related_candidates(
        self,
        track: Track,
        *,
        mode: str = "balanced",
    ) -> list[Track]:
        track_id = self.extract_video_id(getattr(track, "id", None) or getattr(track, "url", None))
        if not track_id:
            return []

        seeds = [
            f"{self.base}{track_id}&list=RD{track_id}",
            f"{self.base}{track_id}",
        ]
        found: dict[str, Track] = {}
        for seed in seeds:
            info = await self._extract_info(seed, extract_flat=True)
            if not isinstance(info, dict):
                continue
            entries = info.get("entries") or []
            for item in entries:
                if not isinstance(item, dict):
                    continue
                built = self._build_track(
                    data=item,
                    video=getattr(track, "video", False),
                    mode=mode,
                    fallback_url=item.get("url") or seed,
                )
                if built and built.id not in found:
                    found[built.id] = built
        return list(found.values())

    async def close(self):
        pass

    async def get_audio_stream(self, video_id: str) -> dict | None:
        resolved_id = self.extract_video_id(video_id) or video_id
        if not resolved_id:
            return None

        url = video_id if self.valid(video_id) else self.base + resolved_id
        info = await self._extract_info(url, extract_flat=False)
        if not info:
            return None

        best_audio = None
        for item in info.get("formats") or []:
            if not isinstance(item, dict):
                continue
            stream_url = item.get("url")
            if not stream_url:
                continue
            if item.get("vcodec") not in (None, "none"):
                continue
            protocol = str(item.get("protocol") or "").lower()
            if "m3u8" in protocol:
                continue

            if (
                not best_audio
                or (item.get("abr") or 0) > (best_audio.get("abr") or 0)
                or (item.get("asr") or 0) > (best_audio.get("asr") or 0)
            ):
                best_audio = item

        audio_url = (best_audio or {}).get("url") or info.get("url")
        if not audio_url:
            return None

        duration = info.get("duration") or 0
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = 0

        return {
            "audio_url": audio_url,
            "duration": duration,
            "title": self.trim_title(info.get("title"), limit=64) or "Unknown Title",
            "performer": info.get("artist") or info.get("uploader") or info.get("channel"),
        }

    async def download(
        self,
        video_id: str,
        video: bool = False,
        mode: str = "balanced",
    ) -> str | None:
        mode = self.normalize_mode(mode)
        resolved_id = self.extract_video_id(video_id) or video_id
        if not resolved_id:
            return None

        url = video_id if self.valid(video_id) else self.base + resolved_id
        ext = "mp4" if video else "webm"
        filename = f"downloads/{resolved_id}.{mode}.{ext}"
        lock_key = f"{resolved_id}:{mode}:{'video' if video else 'audio'}"

        if Path(filename).exists():
            return filename

        lock = self._download_locks.setdefault(lock_key, asyncio.Lock())
        try:
            async with lock:
                if Path(filename).exists():
                    return filename

            cookie = self.get_cookies()
            network_tuning = {
                "best": {
                    "http_chunk_size": 10485760,
                    "concurrent_fragment_downloads": 12,
                    "retries": 12,
                    "fragment_retries": 12,
                },
                "balanced": {
                    "http_chunk_size": 10485760,
                    "concurrent_fragment_downloads": 20,
                    "retries": 10,
                    "fragment_retries": 10,
                },
                "performance": {
                    "http_chunk_size": 10485760,
                    "concurrent_fragment_downloads": 32,
                    "retries": 8,
                    "fragment_retries": 8,
                },
            }[mode]
            base_opts = {
                "outtmpl": f"downloads/%(id)s.{mode}.%(ext)s",
                "quiet": True,
                "no_progress": True,
                "noplaylist": True,
                "geo_bypass": True,
                "no_warnings": True,
                "overwrites": False,
                "nocheckcertificate": True,
                "cookiefile": cookie,
                "socket_timeout": 10,
                **network_tuning,
            }

            if video:
                video_formats = {
                    "best": "(bestvideo[height<=?1080][width<=?1920])+(bestaudio)/best[height<=?1080]",
                    "balanced": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)/best[height<=?720]",
                    "performance": "(bestvideo[height<=?480][width<=?854])+(bestaudio)/best[height<=?480]",
                }
                ydl_opts = {
                    **base_opts,
                    "format": video_formats[mode],
                    "merge_output_format": "mp4",
                }
            else:
                audio_formats = {
                    "best": "bestaudio[acodec=opus]/bestaudio",
                    "balanced": "bestaudio[ext=webm][acodec=opus]/bestaudio",
                    "performance": "worstaudio[acodec=opus]/worstaudio/bestaudio",
                }
                ydl_opts = {
                    **base_opts,
                    "format": audio_formats[mode],
                }

            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(url, download=True)
                    except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                        return None
                    except Exception as ex:
                        logger.warning("Download failed: %s", ex)
                        return None
                requested = filename if Path(filename).exists() else None
                if not requested:
                    for item in Path("downloads").glob(f"{resolved_id}.{mode}.*"):
                        if item.is_file():
                            requested = str(item)
                            break
                return requested or ydl.prepare_filename(info)

            return await asyncio.to_thread(_download)
        finally:
            self._download_locks.pop(lock_key, None)
