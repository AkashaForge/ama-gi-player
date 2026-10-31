"""IA metadata: LRU-кэш + поиск видеофайла."""
import asyncio
import re
import time
from collections import OrderedDict

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("archive_org.metadata")

_METADATA_URL = "https://archive.org/metadata/{identifier}"
_DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"

_VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ogv", ".mpg")
_VIDEO_FORMAT_MARKERS = (
    "mpeg4", "h.264", "matroska", "ogg video", "mpeg2",
    "quicktime", "windows media", "divx", "xvid", "webm", "avi",
)

# "trailer"/"teaser"/"making of" — реально трейлеры. "clip" НЕ включён:
# на IA старые фильмы часто залиты с "clip" в имени, хотя это полный фильм.
_TRAILER_RE = re.compile(
    r'\b(?:trailer|teaser|making\s+of|behind\s+the\s+scenes)\b',
    re.IGNORECASE,
)

# Файл меньше 50 MB с "trailer" в имени — точно трейлер. Больше — это
# скорее всего полный фильм, залитый криворуко.
_TRAILER_SIZE_BYTES = 50 * 1024 * 1024

_MIN_FULL_MOVIE_BYTES = config.ARCHIVE_ORG_MIN_MOVIE_SIZE


class _LRUCache:
    def __init__(self, maxsize: int, ttl: float):
        self.maxsize = max(1, int(maxsize))
        self.ttl = float(ttl)
        self._data: OrderedDict[str, tuple] = OrderedDict()

    def get(self, key: str):
        e = self._data.get(key)
        if e is None:
            return None
        value, ts = e
        if (time.time() - ts) >= self.ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def contains(self, key: str) -> bool:
        return key in self._data

    def put(self, key: str, value):
        self._data[key] = (value, time.time())
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)


_CACHE = _LRUCache(
    config.ARCHIVE_ORG_METADATA_CACHE_MAX,
    config.ARCHIVE_ORG_METADATA_CACHE_TTL,
)


def _normalize_filename(name: str) -> str:
    return name.lower().replace("_", " ").replace("-", " ")


class MetadataFetcher:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def find_video_file(self, identifier: str) -> dict | None:
        cached = _CACHE.get(identifier)
        if cached is not None or _CACHE.contains(identifier):
            return cached

        try:
            async with self.session.get(
                _METADATA_URL.format(identifier=identifier)
            ) as resp:
                if resp.status != 200:
                    _CACHE.put(identifier, None)
                    return None
                data = await resp.json()
        except Exception as e:
            log.debug("metadata %s: %s", identifier, e)
            _CACHE.put(identifier, None)
            return None

        files = data.get("files") or []
        result = self._pick_best_video(identifier, files)
        if not result:
            log.info("metadata %s: no playable video in %d files",
                     identifier, len(files))
        _CACHE.put(identifier, result)
        return result

    @staticmethod
    def _pick_best_video(identifier: str, files: list[dict]) -> dict | None:
        best = None
        for f in files:
            name = (f.get("name") or "").strip()
            if not name:
                continue
            low = name.lower()
            fmt = (f.get("format") or "").strip().lower()
            is_video = (any(low.endswith(e) for e in _VIDEO_EXTS)
                        or any(m in fmt for m in _VIDEO_FORMAT_MARKERS))
            if not is_video:
                continue
            try:
                size = int(f.get("size") or 0)
            except (ValueError, TypeError):
                size = 0
            if size <= 0:
                continue
            if size > config.ARCHIVE_ORG_MAX_FILE_SIZE:
                continue

            # Трейлер отбрасываем только если ОБА признака: имя намекает
            # на трейлер И файл меньше 50 MB. Если имя "trailer" но файл
            # большой — это скорее всего полный фильм, не отбрасываем.
            norm_name = _normalize_filename(name)
            trailer_by_name = bool(_TRAILER_RE.search(norm_name))
            is_small = size < _TRAILER_SIZE_BYTES
            if trailer_by_name and is_small:
                continue

            if size < _MIN_FULL_MOVIE_BYTES:
                log.debug(
                    "metadata %s: '%s' too small (%.1f MB < %.1f MB), skip",
                    identifier, name, size / 1e6, _MIN_FULL_MOVIE_BYTES / 1e6,
                )
                continue

            if best is None or size > best[0]:
                best = (size, name, fmt)

        if not best:
            return None
        size, name, fmt = best
        return {
            "url": _DOWNLOAD_URL.format(identifier=identifier, filename=name),
            "size": size,
            "format": fmt,
            "filename": name,
        }

    async def find_videos_parallel(self, identifiers: list[str]) -> dict[str, dict]:
        if not identifiers:
            return {}

        async def _one(ident):
            try:
                return ident, await self.find_video_file(ident)
            except Exception:
                return ident, None

        pairs = await asyncio.gather(*(_one(i) for i in identifiers))
        return {k: v for k, v in pairs if v is not None}