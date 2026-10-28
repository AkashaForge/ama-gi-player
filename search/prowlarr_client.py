"""Клиент Prowlarr (native JSON API)."""

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
import time

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("prowlarr")

_REQUEST_TIMEOUT = 25.0


class ProwlarrClient:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or f"http://127.0.0.1:{config.PROWLARR_PORT}"
        self._api_key_override = api_key
        self._semaphore = asyncio.Semaphore(1)
        self._diagnosed = False
        self._indexers: list[dict] = []

    @property
    def api_key(self) -> str:
        return self._api_key_override or ""

    def _headers(self) -> dict:
        return {
            "X-Api-Key": self.api_key,
            "Accept": "application/json",
        }

    async def diagnose(self, session: aiohttp.ClientSession) -> dict:
        if self._diagnosed:
            return {"available": len(self._indexers),
                    "ok": len(self._indexers), "error": 0,
                    "indexers": [i.get("name") for i in self._indexers]}

        self._diagnosed = True
        url = f"{self.base_url}/api/v1/indexer"

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(url, headers=self._headers(),
                                    timeout=timeout) as resp:
                if resp.status != 200:
                    log.warning("Prowlarr diagnose: HTTP %d", resp.status)
                    return {}
                data = await resp.json()
                if not isinstance(data, list):
                    return {}
                self._indexers = [i for i in data if i.get("enable", True)]
                log.info("Prowlarr: %d индексаторов активны",
                         len(self._indexers))
                return {
                    "available": len(data),
                    "ok": len(self._indexers),
                    "error": len(data) - len(self._indexers),
                    "indexers": [i.get("name") for i in self._indexers],
                }
        except Exception as e:
            log.warning("Prowlarr diagnose: %s", e)
            return {}

    async def _search(self, session: aiohttp.ClientSession, query: str,
                      tag: str) -> list[dict]:
        url = f"{self.base_url}/api/v1/search"
        params = {"query": query, "type": "search"}
        if self._indexers:
            params["indexerIds"] = ",".join(
                str(i["id"]) for i in self._indexers if i.get("id")
            )

        t0 = time.time()
        try:
            async with self._semaphore:
                timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
                async with session.get(
                    url, headers=self._headers(), params=params,
                    timeout=timeout,
                ) as resp:
                    elapsed = time.time() - t0
                    if resp.status != 200:
                        log.warning("'%s' HTTP %d", tag, resp.status)
                        return []
                    try:
                        data = await resp.json()
                    except Exception as e:
                        log.warning("'%s' JSON: %s", tag, e)
                        return []
                    items = data if isinstance(data, list) else data.get("results", [])
                    log.info("'%s' → 200, items=%d (%.2fs)",
                             tag, len(items), elapsed)
                    return self._parse_results(items)
        except asyncio.TimeoutError:
            log.warning("'%s' timeout (%.2fs)", tag, time.time() - t0)
            return []
        except Exception as e:
            log.error("'%s' %s: %s", tag, type(e).__name__, e)
            return []

    @staticmethod
    def _parse_results(items: list) -> list[dict]:
        parsed = []
        for it in items:
            magnet = it.get("magnetUrl") or it.get("guid") or ""
            url_field = ""
            if isinstance(magnet, str) and magnet.startswith("magnet:"):
                url_field = magnet
                kind = "magnet"
            else:
                dl = it.get("downloadUrl") or it.get("guid") or ""
                if isinstance(dl, str) and dl.startswith(("http://", "https://")):
                    url_field = dl
                    kind = "torrent_url"
                else:
                    continue

            title = str(it.get("title", "Без названия"))
            try:
                seeders = int(it.get("seeders", 0) or 0)
            except (ValueError, TypeError):
                seeders = 0
            try:
                size = int(it.get("size", 0) or 0)
            except (ValueError, TypeError):
                size = 0

            indexer = str(it.get("indexer", "") or "").lower()

            parsed.append({
                "type": kind,
                "url": url_field,
                "title": title,
                "seeders": seeders,
                "size": size,
                "indexer": indexer,
            })
        return parsed

    async def search_all(self, session: aiohttp.ClientSession,
                         title_ru: str, title_en: str,
                         year: str, imdb_id: str,
                         language: str = "en") -> list[dict]:
        await self.diagnose(session)

        if language == "ru" and title_ru:
            q = f"{title_ru} {year}".strip() if year else title_ru
            results = await self._search(session, q, "RU")
            if results:
                return results

        if title_en and title_en != "----":
            q = f"{title_en} {year}".strip() if year else title_en
            results = await self._search(session, q, "EN")
            if results:
                return results

        log.info("Prowlarr: каскад пуст")
        return []
