"""
HTTP-клиент Jackett.

Возможности:
  - diagnose через t=indexers&configured=true (только настроенные)
  - поиск: IMDb → EN/RU text (fallback)
  - retry: только если первый запрос был медленный и пустой
  - public mode: фильтрация результатов по LEGAL_JACKET_INDEXERS
  - сохраняет raw XML для отладки

Индексаторы настраиваются пользователем через UI Jackett:
    http://127.0.0.1:9117/UI/Dashboard
Список индексаторов хранится в data/JackettData/Indexers/*.json
(эта папка в .gitignore).
"""

import asyncio
import os
import re
import time
from datetime import datetime

import aiohttp

import config
from core.logging_setup import get_logger
from core.utils import sanitize_query
from search.torznab_parser import parse_torznab_xml

log = get_logger("jackett")

_MOVIE_CATEGORIES = "2000,2010,2030,2040,2045,2050,2060"
_REQUEST_TIMEOUT = 25.0
_RETRY_MIN_ELAPSED = 1.0
_RETRY_DELAYS = [5.0, 10.0, 15.0]

_DEBUG_DIR = config.DATA_DIR / "jackett_debug"
try:
    os.makedirs(_DEBUG_DIR, exist_ok=True)
except Exception:
    pass


class JackettClient:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or f"http://127.0.0.1:{config.JACKETT_PORT}"
        self._api_key_override = api_key
        self._semaphore = asyncio.Semaphore(1)
        self._diagnosed = False
        self._last_diagnose: dict = {}
        self._debug_counter = 0

    @property
    def api_key(self) -> str:
        if self._api_key_override:
            return self._api_key_override
        return getattr(config, "JACKETT_API_KEY", "") or ""

    def _endpoint(self, path: str) -> str:
        return f"{self.base_url}{path}"

    # ==================================================================
    #  PUBLIC MODE FILTER
    # ==================================================================
    def _filter_by_mode(self, results: list[dict]) -> list[dict]:
        """
        В public режиме оставляем только результаты с легальными
        индексаторами (config.LEGAL_JACKET_INDEXERS).

        В private режиме возвращает всё как есть.
        """
        if not results:
            return results

        if not getattr(config, "LEGAL_ONLY_MODE", False):
            return results

        legal = getattr(config, "LEGAL_JACKET_INDEXERS", frozenset())
        if not legal:
            return results

        filtered = []
        for r in results:
            idx = (r.get("indexer") or "").lower()
            if not idx:
                # Если indexer не определён — тоже отбрасываем в public.
                # Иначе рискуем пропустить приватный трекер без метки.
                continue
            if idx in legal:
                filtered.append(r)

        if len(filtered) != len(results):
            log.info(
                "Jackett: public mode filter %d → %d "
                "(kept only LEGAL_JACKET_INDEXERS)",
                len(results), len(filtered),
            )
        return filtered

    # ==================================================================
    #  DIAGNOSE
    # ==================================================================
    async def diagnose(self, session: aiohttp.ClientSession) -> dict:
        if self._diagnosed:
            return self._last_diagnose

        self._diagnosed = True

        if not self.api_key:
            log.error("Jackett diagnose: API-ключ пуст")
            return {}

        log.info("Jackett diagnose: t=indexers&configured=true")
        result = await self._diagnose_torznab(session, configured_only=True)
        if result and result.get("available", 0) > 0:
            self._last_diagnose = result
            return result

        log.info("Jackett diagnose: t=indexers (все)")
        result = await self._diagnose_torznab(session, configured_only=False)
        if result and result.get("available", 0) > 0:
            log.warning(
                "Jackett diagnose: показаны ВСЕ индексаторы (%d), "
                "а не настроенные.",
                result.get("available", 0),
            )
            self._last_diagnose = result
            return result

        log.warning("Jackett diagnose: ни один метод не сработал")
        self._last_diagnose = {
            "available": -1, "ok": -1, "error": -1, "indexers": [],
        }
        return self._last_diagnose

    async def _diagnose_torznab(self, session, configured_only: bool) -> dict:
        url = self._endpoint("/api/v2.0/indexers/all/results/torznab/api")
        params = {"t": "indexers", "apikey": self.api_key}
        if configured_only:
            params["configured"] = "true"

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    log.debug(
                        "diagnose torznab configured=%s: HTTP %d",
                        configured_only, resp.status,
                    )
                    return {}
                xml = await resp.text()
        except Exception as e:
            log.debug("diagnose torznab: %s", e)
            return {}

        indexers = []
        for m in re.finditer(r'<indexer\s+id="([^"]+)"', xml):
            indexers.append(m.group(1))

        if not indexers:
            return {}

        log.info(
            "Jackett (configured=%s): %d индексаторов: %s",
            configured_only, len(indexers), ", ".join(indexers[:10]),
        )
        return {
            "available": len(indexers),
            "ok": len(indexers),
            "error": 0,
            "indexers": indexers,
        }

    # ==================================================================
    #  DEBUG
    # ==================================================================
    def _save_raw_xml(self, xml: str, tag: str):
        try:
            self._debug_counter += 1
            ts = datetime.now().strftime("%H%M%S")
            fname = f"{ts}_{self._debug_counter:03d}_{tag}.xml"
            fname = fname.replace("=", "_").replace("/", "_").replace(" ", "_")
            path = os.path.join(_DEBUG_DIR, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            log.info("Jackett raw XML: %s (%d байт)", fname, len(xml))
        except Exception as e:
            log.debug("save raw xml: %s", e)

    # ==================================================================
    #  HTTP
    # ==================================================================
    async def _get(self, session, params, tag) -> tuple[list[dict], float, int]:
        url = self._endpoint("/api/v2.0/indexers/all/results/torznab/api")
        params = {**params, "apikey": self.api_key}

        t0 = time.time()
        try:
            async with self._semaphore:
                timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
                async with session.get(url, params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        elapsed = time.time() - t0
                        log.warning("'%s' HTTP %d (%.2fs)",
                                    tag, resp.status, elapsed)
                        return [], elapsed, resp.status

                    xml = await resp.text()
                    elapsed = time.time() - t0
                    items_count = xml.count("<item>") + xml.count("<item ")

                    if items_count == 0:
                        log.info("'%s' → 200, items=0 (%.2fs)", tag, elapsed)
                        self._save_raw_xml(xml, tag)
                        return [], elapsed, 200

                    parsed = parse_torznab_xml(xml)
                    mag = sum(1 for r in parsed if r.get("type") == "magnet")
                    tor = sum(1 for r in parsed if r.get("type") == "torrent_url")
                    log.info(
                        "'%s' → 200, XML items=%d, parsed=%d "
                        "(magnet=%d, torrent_url=%d) (%.2fs)",
                        tag, items_count, len(parsed), mag, tor, elapsed,
                    )

                    if items_count > 0 and len(parsed) == 0:
                        self._log_dropped_items(xml, tag)

                    self._save_raw_xml(xml, tag)
                    return parsed, elapsed, 200

        except asyncio.TimeoutError:
            elapsed = time.time() - t0
            log.warning("'%s' timeout (%.2fs)", tag, elapsed)
            return [], elapsed, -1
        except Exception as e:
            elapsed = time.time() - t0
            log.error("'%s' %s: %s", tag, type(e).__name__, e)
            return [], elapsed, -1

    def _log_dropped_items(self, xml: str, tag: str):
        titles = re.findall(r'<title>([^<]*)</title>', xml)
        sizes = re.findall(r'name="size"\s+value="(\d+)"', xml)
        if not titles:
            return
        log.warning(
            "'%s': items=%d, parsed=0 — все отброшены. Первые 3:",
            tag, len(titles),
        )
        for i, title in enumerate(titles[:3]):
            size = int(sizes[i]) if i < len(sizes) else 0
            log.warning("  [%d] title=%r size=%.1f MB",
                        i, title[:80], size / 1024 / 1024)

    async def _try_request(self, session, params, tag,
                           allow_retry: bool = True) -> list[dict]:
        results, elapsed, status = await self._get(session, params, tag)

        # === Применяем фильтр public/private СРАЗУ после первого запроса ===
        results = self._filter_by_mode(results)

        if results:
            return results

        if not allow_retry:
            log.info("'%s': no retry (allow_retry=False)", tag)
            return []

        if status == 200 and elapsed < _RETRY_MIN_ELAPSED:
            log.info(
                "'%s' быстрый пустой за %.2fs — не retry, сразу дальше",
                tag, elapsed,
            )
            return []

        for attempt, delay in enumerate(_RETRY_DELAYS, 1):
            log.info(
                "'%s' пусто (%.2fs, HTTP %d) → retry %d/%d через %.0fs",
                tag, elapsed, status, attempt, len(_RETRY_DELAYS), delay,
            )
            await asyncio.sleep(delay)
            retry_params = {k: v for k, v in params.items() if k != "cat"}
            results, elapsed, status = await self._get(
                session, retry_params, f"{tag} (retry {attempt})",
            )
            results = self._filter_by_mode(results)
            if results:
                return results

        log.warning("'%s': все попытки пусты", tag)
        return []

    # ==================================================================
    #  SEARCH
    # ==================================================================
    async def search_imdb(self, session, imdb_id) -> list[dict]:
        # IMDb: без retry — если пусто, значит пусто.
        return await self._try_request(session, {
            "t": "movie",
            "cat": _MOVIE_CATEGORIES,
            "imdbid": imdb_id.strip(),
        }, f"IMDb={imdb_id}", allow_retry=False)

    async def search_text(self, session, query, tag) -> list[dict]:
        q = sanitize_query(query)
        if not q:
            return []
        return await self._try_request(session, {
            "t": "search",
            "cat": _MOVIE_CATEGORIES,
            "q": q,
        }, tag)

    async def search_all(self, session, title_ru, title_en, year, imdb_id,
                         language="en") -> list[dict]:
        await self.diagnose(session)

        if imdb_id and imdb_id.startswith("tt"):
            results = await self.search_imdb(session, imdb_id)
            if results:
                log.info("Jackett: IMDb дал %d", len(results))
                return results

        if language == "en":
            if title_en and title_en != "----":
                q = f"{title_en} {year}".strip() if year else title_en
                results = await self.search_text(session, q, "EN")
                if results:
                    log.info("Jackett: EN дал %d", len(results))
                    return results
            log.info("Jackett: EN-каскад пуст")
            return []

        if language == "ru":
            if title_ru:
                q = f"{title_ru} {year}".strip() if year else title_ru
                results = await self.search_text(session, q, "RU")
                if results:
                    log.info("Jackett: RU дал %d", len(results))
                    return results
            log.info("Jackett: RU-каскад пуст")
            return []

        return []
