"""Клиент YTS-совместимого API.

По умолчанию отключён. Активируется только если:
  1. файл data/yts_api_base.txt содержит непустой URL (без строк-комментариев),
  2. config.YTS_ENABLED = True (по умолчанию False).

Файл data/yts_api_base.txt — личный, в git не коммитится (в .gitignore).
Шаблон лежит в data/yts_api_base.example.txt.

Код не содержит ссылок на сторонние ресурсы — URL задаёт пользователь.
"""

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("yts")


def _load_base_url() -> str:
    """Читает URL из data/yts_api_base.txt, игнорируя комментарии и пустые строки."""
    path = config.DATA_DIR / "yts_api_base.txt"
    if not path.exists():
        return ""
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            return line
    except Exception as e:
        log.warning("yts_api_base.txt: %s", e)
    return ""


class YTSClient:
    def __init__(self):
        self.base_url = _load_base_url()
        self.enabled = (
            bool(self.base_url)
            and getattr(config, "YTS_ENABLED", False)
        )
        self.max_results = getattr(config, "YTS_MAX_RESULTS", 20)

        if not self.base_url:
            log.info("YTS: отключён (data/yts_api_base.txt пуст или отсутствует)")
        elif not self.enabled:
            log.info("YTS: отключён (YTS_ENABLED=False)")
        else:
            log.info("YTS: включён, base_url=%s", self.base_url)

    def is_enabled(self) -> bool:
        return self.enabled

    async def search(self, session: aiohttp.ClientSession, query: str,
                     year: str = "") -> list[dict]:
        if not self.enabled:
            return []

        url = f"{self.base_url}/list_movies.json"
        params = {
            "query_term": query,
            "sort_by": "seeds",
            "limit": self.max_results,
        }
        if year:
            params["year"] = year

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    log.warning("YTS HTTP %d", resp.status)
                    return []
                data = await resp.json()
        except Exception as e:
            log.warning("YTS request: %s", e)
            return []

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
                results.append({
                    "type": "magnet",
                    "url": magnet,
                    "title": f"{title} [{quality}]",
                    "seeders": seeders,
                    "size": size,
                    "indexer": "yts",
                })
        log.info("YTS: %d результатов для '%s'", len(results), query)
        return results

    @staticmethod
    def _magnet_from_hash(info_hash: str) -> str:
        """Собирает magnet-ссылку из хеша, который отдаёт API.

        Трекеры — универсальные публичные DHT-bootstrap,
        не привязаны к конкретному ресурсу.
        """
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
