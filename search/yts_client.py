"""Клиент YTS с несколькими зеркалами и retry.

v2.0.21:
  - НЕТ фатального _dns_failed
  - Перебор зеркал из config.YTS_BASE_URLS при ошибке
  - Retry с задержкой
"""
import asyncio

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("yts")


class YTSClient:
    def __init__(self):
        self.base_urls = list(getattr(config, "YTS_BASE_URLS", ()))
        self.enabled = (
            bool(self.base_urls)
            and getattr(config, "YTS_ENABLED", False)
        )
        self.max_results = getattr(config, "YTS_MAX_RESULTS", 20)
        self.timeout = getattr(config, "YTS_REQUEST_TIMEOUT", 10.0)
        self.max_retries = getattr(config, "YTS_MAX_RETRIES", 2)
        self.retry_delay = getattr(config, "YTS_RETRY_DELAY", 2.0)

        if not self.base_urls:
            log.info("YTS: отключён (нет зеркал в config.YTS_BASE_URLS)")
        elif not self.enabled:
            log.info("YTS: отключён (YTS_ENABLED=False)")
        else:
            log.info("YTS: включён, зеркал=%d", len(self.base_urls))

    def is_enabled(self) -> bool:
        return self.enabled

    async def search(self, session: aiohttp.ClientSession,
                     query: str, year: str = "") -> list[dict]:
        if not self.enabled:
            return []

        last_error = None
        for base_url in self.base_urls:
            for attempt in range(1, self.max_retries + 1):
                try:
                    results = await self._search_one(
                        session, base_url, query, year
                    )
                    if results:
                        log.info("YTS [%s]: %d результатов",
                                 base_url, len(results))
                        return results
                    # Пустой ответ — не ошибка, пробуем следующее зеркало
                    log.debug("YTS [%s]: пусто", base_url)
                    break
                except asyncio.TimeoutError:
                    last_error = f"timeout ({base_url})"
                    log.warning("YTS [%s] attempt %d: timeout",
                                base_url, attempt)
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e} ({base_url})"
                    log.warning("YTS [%s] attempt %d: %s",
                                base_url, attempt, e)

                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)

        log.warning("YTS: все зеркала недоступны (%s)", last_error)
        return []

    async def _search_one(self, session, base_url: str,
                          query: str, year: str) -> list[dict]:
        url = f"{base_url}/list_movies.json"
        params = {
            "query_term": query,
            "sort_by": "seeds",
            "limit": self.max_results,
        }
        if year:
            params["year"] = year

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with session.get(url, params=params,
                               timeout=timeout) as resp:
            if resp.status != 200:
                log.warning("YTS [%s] HTTP %d", base_url, resp.status)
                return []
            data = await resp.json()

        movies = (data.get("data") or {}).get("movies") or []
        results = []
        for movie in movies:
            title = movie.get("title_long") or movie.get("title") or "?"
            for torrent in movie.get("torrents") or []:
                magnet = self._magnet_from_hash(torrent.get("hash", ""))
                if not magnet:
                    continue
                quality = torrent.get("quality", "?")
                size = int(torrent.get("size_bytes") or 0)
                seeders = int(torrent.get("seeds") or 0)
                peers = int(torrent.get("peers") or 0)
                results.append({
                    "type": "magnet",
                    "url": magnet,
                    "title": f"{title} [{quality}]",
                    "seeders": seeders,
                    "leechers": peers,
                    "size": size,
                    "indexer": "yts",
                })
        return results

    @staticmethod
    def _magnet_from_hash(info_hash: str) -> str:
        if not info_hash:
            return ""
        trackers = (
            "udp://open.demonii.com:1337/announce",
            "udp://tracker.openbittorrent.com:80",
            "udp://tracker.coppersurfer.tk:6969",
            "udp://exodus.desync.com:6969",
        )
        tr = "".join(f"&tr={t}" for t in trackers)
        return f"magnet:?xt=urn:btih:{info_hash}{tr}"