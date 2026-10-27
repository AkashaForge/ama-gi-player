"""
Поиск на Internet Archive с фильтрацией по языку.

Проблема: query=title:("The Kid") возвращает и польскую версию "Brzdąc",
и английскую. Старый код брал самый большой файл → польский.

Решение:
  - Запрашиваем поле language из advancedsearch
  - Фильтруем по preferred_language (из config.SEARCH_LANGUAGE)
  - Скоринг: язык (100) + точность title (50) + downloads (/100)
  - Если ничего не подошло по языку — лог предупреждение (не играем)
"""


import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("archive_org")

_SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_URL = "https://archive.org/metadata/{identifier}"
_DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"

_VIDEO_EXTS = (
    ".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ogv", ".mpg",
)

_VIDEO_FORMAT_MARKERS = (
    "mpeg4", "h.264", "matroska", "ogg video", "mpeg2",
    "quicktime", "windows media", "divx", "xvid", "webm", "avi",
)

_MAX_ITEMS_TO_CHECK = 8


class ArchiveOrgSearcher:
    def __init__(self):
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=getattr(config, "NETWORK_TIMEOUT", 15)
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    # ==================================================================
    #  ЯЗЫК
    # ==================================================================
    @staticmethod
    def _get_preferred_language() -> str:
        """Возвращает 'en' или 'ru' из config.SEARCH_LANGUAGE."""
        lang = getattr(config, "SEARCH_LANGUAGE", "en").lower()
        return lang if lang in ("en", "ru") else "en"

    @staticmethod
    def _lang_score(actual: str, preferred: str) -> float:
        """
        0.0  — явно не тот язык
        0.5  — язык не указан (нейтрально)
        1.0  — совпал (или silent)
        """
        if not actual:
            return 0.5
        a = actual.lower().strip()
        if "silent" in a:
            return 0.9    # немое кино — интертитры всё равно нужны
        if preferred == "en":
            if any(x in a for x in ("english", "eng", "american",
                                     "british", "usa", "uk")):
                return 1.0
            if any(x in a for x in ("russian", "rus", "german", "ger",
                                     "french", "fre", "polish", "pol",
                                     "czech", "cze", "czechoslovak",
                                     "spanish", "spa", "italian", "ita",
                                     "japanese", "jpn", "chinese", "chi",
                                     "portuguese", "por", "dutch", "dut",
                                     "swedish", "swe", "danish", "dan",
                                     "norwegian", "nor", "finnish", "fin",
                                     "hungarian", "hun", "romanian", "rum",
                                     "greek", "gre", "turkish", "tur",
                                     "hebrew", "heb", "arabic", "ara",
                                     "hindi", "hin", "korean", "kor")):
                return 0.0
            return 0.5
        if preferred == "ru":
            if any(x in a for x in ("russian", "rus", "soviet", "ussr")):
                return 1.0
            if any(x in a for x in ("english", "eng", "german", "ger",
                                     "french", "fre", "polish", "pol",
                                     "czech", "cze", "spanish", "spa",
                                     "italian", "ita", "japanese", "jpn")):
                return 0.0
            return 0.5
        return 0.5

    @staticmethod
    def _title_score(identifier: str, title: str, query: str) -> float:
        """
        0..1: насколько identifier/title похож на запрос.
        'the-kid-1921' для query='The Kid' → 1.0
        'Brzdac1921' для query='The Kid' → 0.2 (нет слов запроса)
        """
        q_words = [w for w in query.lower().split() if len(w) >= 3]
        if not q_words:
            return 0.5
        target = (identifier + " " + title).lower()
        matched = sum(1 for w in q_words if w in target)
        return matched / len(q_words)

    # ==================================================================
    #  SEARCH
    # ==================================================================
    async def _search_identifiers(
        self, query: str, year: str = ""
    ) -> list[dict]:
        session = await self._get_session()

        q_parts = [f'title:("{query}")']
        if year:
            try:
                y = int(year)
                q_parts.append(f"year:[{y-1} TO {y+1}]")
            except ValueError:
                pass
        q_parts.append("mediatype:(movies)")
        q = " AND ".join(q_parts)

        log.info("IA query: %s", q[:200])

        params = {
            "q": q,
            "fl[]": ["identifier", "title", "year", "downloads",
                     "language", "creator"],
            "sort[]": "downloads desc",
            "rows": str(config.ARCHIVE_ORG_MAX_RESULTS),
            "page": "1",
            "output": "json",
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

    # ==================================================================
    #  METADATA → видеофайл
    # ==================================================================
    async def _find_video_file(self, identifier: str) -> dict | None:
        session = await self._get_session()
        try:
            async with session.get(
                _METADATA_URL.format(identifier=identifier)
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except Exception as e:
            log.debug("IA metadata %s: %s", identifier, e)
            return None

        files = data.get("files") or []
        if not files:
            return None

        best = None
        for f in files:
            name = (f.get("name") or "").strip()
            if not name:
                continue
            low = name.lower()
            fmt = (f.get("format") or "").strip().lower()
            is_video_ext = any(low.endswith(ext) for ext in _VIDEO_EXTS)
            is_video_format = any(
                marker in fmt for marker in _VIDEO_FORMAT_MARKERS
            )
            if not (is_video_ext or is_video_format):
                continue
            try:
                size = int(f.get("size") or 0)
            except (ValueError, TypeError):
                size = 0
            if size <= 0:
                continue
            if size > config.ARCHIVE_ORG_MAX_FILE_SIZE:
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

    # ==================================================================
    #  MAIN
    # ==================================================================
    async def search(self, query: str, year: str = "") -> list[dict]:
        if not getattr(config, "ARCHIVE_ORG_ENABLED", True):
            return []
        if not query or not query.strip():
            return []

        query = query.strip()
        year = (year or "").strip()
        preferred = self._get_preferred_language()
        log.info("IA: preferred_language=%s", preferred)

        docs = await self._search_identifiers(query, year)
        if not docs and year:
            log.info("IA: retry без year фильтра")
            docs = await self._search_identifiers(query, year="")
        if not docs:
            return []

        # Ограничиваем для metadata-запросов
        docs = docs[:_MAX_ITEMS_TO_CHECK]

        # === Скоринг и фильтрация ===
        scored_docs = []
        for doc in docs:
            identifier = doc.get("identifier") or ""
            title = doc.get("title") or "Без названия"
            if isinstance(title, list):
                title = title[0] if title else "Без названия"
            title = str(title).strip()

            lang_field = doc.get("language") or ""
            if isinstance(lang_field, list):
                lang_field = ", ".join(str(x) for x in lang_field)
            lang_field = str(lang_field)

            lang_s = self._lang_score(lang_field, preferred)
            title_s = self._title_score(identifier, title, query)

            try:
                downloads = int(doc.get("downloads") or 0)
            except (ValueError, TypeError):
                downloads = 0
            downloads_s = min(1.0, downloads / 5000)

            # === Отсев: явно чужой язык → skip ===
            if lang_s == 0.0:
                log.info(
                    "IA '%s': skip — язык '%s' не подходит для %s",
                    identifier, lang_field[:40], preferred,
                )
                continue

            total = lang_s * 100 + title_s * 50 + downloads_s * 20
            scored_docs.append((total, doc, lang_field, lang_s, title_s))

        # Сортируем по убыванию score
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        log.info(
            "IA: %d → %d после фильтра языка",
            len(docs), len(scored_docs),
        )

        results = []
        for score, doc, lang_field, lang_s, title_s in scored_docs:
            identifier = doc.get("identifier")
            if not identifier:
                continue

            title = doc.get("title") or "Без названия"
            if isinstance(title, list):
                title = title[0] if title else "Без названия"
            title = str(title).strip()

            doc_year = doc.get("year")
            if isinstance(doc_year, list):
                doc_year = doc_year[0] if doc_year else ""
            doc_year = str(doc_year) if doc_year else ""

            downloads = doc.get("downloads") or 0

            video = await self._find_video_file(identifier)
            if not video:
                log.debug("IA '%s': нет видеофайла", identifier)
                continue

            results.append({
                "type": "direct_url",
                "url": video["url"],
                "title": f"{title} ({doc_year})" if doc_year else title,
                "seeders": 0,
                "size": video["size"],
                "indexer": "internetarchive",
                "filename": video.get("filename", ""),
                "format": video.get("format", ""),
                "downloads": downloads,
                "language": lang_field,
                "score": score,
            })
            log.info(
                "IA '%s': %s (%.1f MB, lang='%s', score=%.1f)",
                identifier,
                video["filename"][:60],
                video["size"] / 1024 / 1024,
                lang_field[:30] or "?",
                score,
            )

        log.info("IA итог: %d direct_url", len(results))
        return results

    async def close(self):
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
