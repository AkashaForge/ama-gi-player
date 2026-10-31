"""Поиск на Internet Archive с health scoring по языку."""
import re
import time

import aiohttp

import config
from core.logging_setup import get_logger
from search.archive_org.language import lang_score, title_score
from search.archive_org.metadata import MetadataFetcher

log = get_logger("archive_org.searcher")

_SEARCH_URL = "https://archive.org/advancedsearch.php"

# Берём из IA много результатов (до скоринга), чтобы нишевые старые
# фильмы не отсекались в топ-8 по downloads.
_FETCH_LIMIT = 30
_FINAL_LIMIT = 15

_LUCENE_SPECIAL_RE = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')


def _escape_lucene(s: str) -> str:
    if not s:
        return ""
    return _LUCENE_SPECIAL_RE.sub(r'\\\1', s)


class ArchiveOrgSearcher:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._metadata: MetadataFetcher | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._metadata = MetadataFetcher(self._session)
        return self._session

    @staticmethod
    def _preferred_lang() -> str:
        lang = config.SEARCH_LANGUAGE.lower()
        return lang if lang in ("en", "ru") else "en"

    async def _search_identifiers(
        self, query: str, year: str, use_mediatype: bool = True
    ) -> list[dict]:
        session = await self._ensure_session()
        q_parts = [f'title:("{_escape_lucene(query)}")']
        if year:
            try:
                y = int(year)
                # ±2 вместо ±1 — IA часто пишет год на 1-2 неточно
                q_parts.append(f"year:[{y-2} TO {y+2}]")
            except ValueError:
                pass
        if use_mediatype:
            q_parts.append("mediatype:(movies)")
        q = " AND ".join(q_parts)

        log.info("IA query: %s", q[:200])
        params = {
            "q": q,
            "fl[]": ["identifier", "title", "year", "downloads",
                     "language", "creator"],
            "sort[]": "downloads desc",
            "rows": str(_FETCH_LIMIT),
            "page": "1", "output": "json",
        }
        try:
            async with session.get(_SEARCH_URL, params=params) as resp:
                if resp.status != 200:
                    log.warning("IA search HTTP %d", resp.status)
                    return []
                data = await resp.json()
        except Exception as e:
            log.warning("IA search: %s", e)
            return []

        docs = (data.get("response") or {}).get("docs") or []
        log.info("IA '%s': %d results", query, len(docs))
        return docs

    async def search(self, query: str, year: str = "") -> list[dict]:
        if not config.ARCHIVE_ORG_ENABLED:
            return []
        if not query or not query.strip():
            return []

        query = query.strip()
        year = (year or "").strip()
        preferred = self._preferred_lang()
        log.info("IA: preferred_language=%s", preferred)

        await self._ensure_session()

        # Каскад запросов: точный → без mediatype → без year → только title
        docs = await self._search_identifiers(query, year, use_mediatype=True)
        if not docs and year:
            log.info("IA: fallback 1 — без mediatype")
            docs = await self._search_identifiers(query, year, use_mediatype=False)
        if not docs and year:
            log.info("IA: fallback 2 — без year")
            docs = await self._search_identifiers(query, "", use_mediatype=True)
        if not docs:
            log.info("IA: fallback 3 — только title")
            docs = await self._search_identifiers(query, "", use_mediatype=False)

        if not docs:
            return []

        # Скорим ВСЕ (не обрезаем до скоринга)
        scored = []
        for doc in docs:
            ident = doc.get("identifier") or ""
            if not ident:
                continue
            title = doc.get("title") or "?"
            if isinstance(title, list):
                title = title[0] if title else "?"
            title = str(title).strip()

            lf = doc.get("language") or ""
            if isinstance(lf, list):
                lf = ", ".join(str(x) for x in lf)
            lf = str(lf)

            # Год конкретного документа (не общий из запроса)
            dy_raw = doc.get("year")
            if isinstance(dy_raw, list):
                dy_raw = dy_raw[0] if dy_raw else ""
            dy_str = str(dy_raw).strip() if dy_raw else year

            ls = lang_score(lf, preferred, year=dy_str)
            # Не отсеиваем по 0.0 — только взвешиваем.
            ts = title_score(ident, title, query)
            try:
                downloads = int(doc.get("downloads") or 0)
            except (ValueError, TypeError):
                downloads = 0
            ds = min(1.0, downloads / 5000)
            total = ls * 100 + ts * 50 + ds * 20
            scored.append((total, doc, lf))

        scored.sort(key=lambda x: x[0], reverse=True)
        scored = scored[:_FINAL_LIMIT]

        identifiers = [
            d.get("identifier") for _, d, _ in scored if d.get("identifier")
        ]
        t0 = time.time()
        videos = await self._metadata.find_videos_parallel(identifiers)
        log.info(
            "IA: metadata за %.2fs (%d/%d)",
            time.time() - t0, len(videos), len(identifiers),
        )

        results = []
        for score, doc, lf in scored:
            ident = doc.get("identifier")
            video = videos.get(ident)
            if not video:
                continue
            title = doc.get("title") or "?"
            if isinstance(title, list):
                title = title[0] if title else "?"
            title = str(title).strip()
            dy = doc.get("year")
            if isinstance(dy, list):
                dy = dy[0] if dy else ""
            dy = str(dy) if dy else ""

            results.append({
                "type": "direct_url",
                "url": video["url"],
                "title": f"{title} ({dy})" if dy else title,
                "seeders": 0,
                "size": video["size"],
                "indexer": "internetarchive",
                "filename": video.get("filename", ""),
                "format": video.get("format", ""),
                "downloads": doc.get("downloads") or 0,
                "language": lf,
                "score": score,
            })

        log.info("IA итог: %d direct_url", len(results))
        return results

    async def close(self):
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
            self._metadata = None