"""
HTTP-клиент Jackett.

Изменения v2.0.6:
  - _RETRY_DELAYS = [1.0, 2.0] (было [5, 10, 15] — 30с впустую)
  - _REQUEST_TIMEOUT = 15.0 (было 25 — Jackett локальный)
  - каскад IMDb + текст параллельно (было последовательно)
  - diagnose: не кэшируем провал навсегда, retry через 60с
  - _save_raw_xml за флагом config.JACKETT_DEBUG_SAVE_XML
  - Semaphore(2) вместо 1
"""

# Amagi-Player — desktop media player for public-domain content
# Copyright (C) 2026 AkashaForge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
_REQUEST_TIMEOUT = getattr(config, "JACKETT_REQUEST_TIMEOUT", 10.0)
_RETRY_MIN_ELAPSED = 1.0
_RETRY_DELAYS = getattr(config, "JACKETT_RETRY_DELAYS", [0.5, 1.0])
_DIAGNOSE_RETRY_DELAY = 60.0

_DEBUG_DIR = config.DATA_DIR / "jackett_debug"
try:
    os.makedirs(_DEBUG_DIR, exist_ok=True)
except Exception:
    pass


class JackettClient:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or f"http://127.0.0.1:{config.JACKETT_PORT}"
        self._api_key_override = api_key
        self._semaphore = asyncio.Semaphore(2)
        self._diagnosed = False
        self._last_diagnose: dict = {}
        self._diagnose_retry_ts = 0.0
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
        now = time.time()

        if self._diagnosed:
            return self._last_diagnose
        if now < self._diagnose_retry_ts:
            return self._last_diagnose

        if not self.api_key:
            log.error("Jackett diagnose: API-ключ пуст")
            self._diagnose_retry_ts = now + _DIAGNOSE_RETRY_DELAY
            return {}

        log.info("Jackett diagnose: t=indexers&configured=true")
        result = await self._diagnose_torznab(session, configured_only=True)
        if result and result.get("available", 0) > 0:
            self._last_diagnose = result
            self._diagnosed = True
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
            self._diagnosed = True
            return result

        log.warning(
            "Jackett diagnose: ни один метод не сработал "
            "(следующая попытка через %.0fs)",
            _DIAGNOSE_RETRY_DELAY,
        )
        self._last_diagnose = {
            "available": -1, "ok": -1, "error": -1, "indexers": [],
        }
        # НЕ ставим _diagnosed=True — попробуем снова, но с backoff.
        self._diagnose_retry_ts = now + _DIAGNOSE_RETRY_DELAY
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
        if not getattr(config, "JACKETT_DEBUG_SAVE_XML", False):
            return
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

        tasks: list[asyncio.Task] = []

        # IMDb-запрос и текстовый запрос — независимы, запускаем параллельно.
        if imdb_id and imdb_id.startswith("tt"):
            tasks.append(asyncio.create_task(
                self.search_imdb(session, imdb_id)
            ))

        if language == "en":
            if title_en and title_en != "----":
                q = f"{title_en} {year}".strip() if year else title_en
                tasks.append(asyncio.create_task(
                    self.search_text(session, q, "EN")
                ))
        elif language == "ru":
            if title_ru:
                q = f"{title_ru} {year}".strip() if year else title_ru
                tasks.append(asyncio.create_task(
                    self.search_text(session, q, "RU")
                ))

        if not tasks:
            return []

        try:
            results_list = await asyncio.gather(
                *tasks, return_exceptions=True
            )
        except Exception as e:
            log.warning("Jackett gather: %s", e)
            return []

        for r in results_list:
            if isinstance(r, list) and r:
                return r

        if language == "en":
            log.info("Jackett: EN-каскад пуст")
        elif language == "ru":
            log.info("Jackett: RU-каскад пуст")
        return []