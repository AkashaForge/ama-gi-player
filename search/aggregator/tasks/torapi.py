"""TorAPI — русские трекеры (RuTracker, Kinozal, RuTor, NoNameClub).

URL берётся из config.TORAPI_BASE_URL (можно задать через .env).
Формат ответа: предполагается JSON с полями title, size, seeders,
peers, magnet/link. Если поля называются иначе — парсер адаптируется.
"""
import asyncio

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("aggregator.tasks.torapi")


async def safe_torapi(session: aiohttp.ClientSession,
                      query: str, year: str = "") -> list[dict]:
    base_url = getattr(config, "TORAPI_BASE_URL", "").strip()
    if not base_url or not getattr(config, "TORAPI_ENABLED", False):
        return []
    if not query:
        return []

    timeout_sec = getattr(config, "TORAPI_REQUEST_TIMEOUT", 15.0)
    max_results = getattr(config, "TORAPI_MAX_RESULTS", 30)

    url = f"{base_url.rstrip('/')}/search"
    params = {"query": query, "limit": max_results}
    if year:
        params["year"] = year

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with session.get(url, params=params,
                               timeout=timeout) as resp:
            if resp.status != 200:
                log.warning("TorAPI HTTP %d", resp.status)
                return []
            data = await resp.json()
    except asyncio.TimeoutError:
        log.warning("TorAPI: timeout")
        return []
    except Exception as e:
        log.warning("TorAPI: %s", e)
        return []

    items = data if isinstance(data, list) else data.get("results", [])
    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Адаптируем под возможные имена полей
        title = (item.get("title") or item.get("name")
                 or item.get("topic") or "?")
        size = _to_int(item.get("size") or item.get("size_bytes"))
        seeders = _to_int(item.get("seeders") or item.get("seeds"))
        peers = _to_int(item.get("peers") or item.get("leechers")
                         or item.get("piers"))
        magnet = (item.get("magnet") or item.get("magnet_link")
                  or item.get("link") or item.get("url") or "")
        if not magnet.startswith("magnet:"):
            torrent_url = item.get("torrent") or item.get("download")
            if torrent_url and torrent_url.startswith(("http://", "https://")):
                results.append({
                    "type": "torrent_url",
                    "url": torrent_url,
                    "title": title,
                    "seeders": seeders,
                    "leechers": peers,
                    "size": size,
                    "indexer": "torapi",
                })
            continue
        results.append({
            "type": "magnet",
            "url": magnet,
            "title": title,
            "seeders": seeders,
            "leechers": peers,
            "size": size,
            "indexer": "torapi",
        })

    log.info("TorAPI: %d результатов для '%s'", len(results), query)
    return results


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0