"""Загрузчик внешних списков трекеров."""
import asyncio
import time
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("lt.tracker_balancer")

DEFAULT_TRACKERS_FALLBACK = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.coppersurfer.tk:6969/announce",
    "udp://tracker.leechers-paradise.org:6969/announce",
)

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_safe_balancer_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    if not host or host in _BLOCKED_HOSTS:
        return False
    if host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.",
                         "172.19.", "172.2", "172.30.", "172.31.")):
        return False
    return True


def _is_valid_tracker(t: str) -> bool:
    if not t or "://" not in t:
        return False
    scheme = t.split("://", 1)[0].lower()
    return scheme in ("udp", "http", "https", "wss")


class TrackerBalancer:
    def __init__(self):
        self._trackers: list[str] = []
        self._loaded_at: float = 0.0
        self._ttl = config.TRACKER_BALANCER_TTL_HOURS * 3600

    async def get_trackers(self) -> list[str]:
        now = time.time()
        if self._trackers and (now - self._loaded_at) < self._ttl:
            return self._trackers

        cache_file: Path = config.TRACKER_CACHE_FILE
        if cache_file.exists():
            try:
                age = now - cache_file.stat().st_mtime
                if age < self._ttl:
                    cached = self._read_file(cache_file)
                    if cached:
                        self._trackers = cached
                        self._loaded_at = now
                        log.info("Trackers cache HIT: %d", len(cached))
                        return cached
            except Exception:
                pass

        urls = self._load_urls()
        if not urls:
            log.info("tracker_balancers.txt пуст — fallback (%d)",
                     len(DEFAULT_TRACKERS_FALLBACK))
            self._trackers = list(DEFAULT_TRACKERS_FALLBACK)
            self._loaded_at = now
            return self._trackers

        downloaded = await self._download_all(urls)
        if downloaded:
            self._trackers = downloaded
            self._loaded_at = now
            self._write_file(cache_file, downloaded)
            log.info("Trackers fetched: %d из %d URL", len(downloaded), len(urls))
            return downloaded

        if cache_file.exists():
            cached = self._read_file(cache_file)
            if cached:
                log.warning("Все URL мертвы — stale cache: %d", len(cached))
                self._trackers = cached
                self._loaded_at = now
                return cached

        log.warning("Fallback на %d хардкод-трекеров",
                    len(DEFAULT_TRACKERS_FALLBACK))
        self._trackers = list(DEFAULT_TRACKERS_FALLBACK)
        self._loaded_at = now
        return self._trackers

    def _load_urls(self) -> list[str]:
        path: Path = config.TRACKER_BALANCERS_FILE
        if not path.exists():
            return []
        urls = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if not _is_safe_balancer_url(line):
                    log.warning("Небезопасный URL: %s", line[:60])
                    continue
                urls.append(line)
        except Exception as e:
            log.warning("tracker_balancers.txt: %s", e)
        max_urls = config.TRACKER_BALANCER_MAX_URLS
        if len(urls) > max_urls:
            log.warning("URLs > %d, беру первые %d", max_urls, max_urls)
            urls = urls[:max_urls]
        return urls

    async def _download_all(self, urls: list[str]) -> list[str]:
        tasks = [self._download_one(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: set[str] = set()
        for r in results:
            if isinstance(r, list):
                merged.update(r)
        final = [t for t in merged if _is_valid_tracker(t)]
        max_trackers = config.TRACKER_BALANCER_MAX_TRACKERS
        if len(final) > max_trackers:
            final = final[:max_trackers]
        return final

    async def _download_one(self, url: str) -> list[str]:
        try:
            timeout = aiohttp.ClientTimeout(total=config.TRACKER_BALANCER_TIMEOUT_SEC)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=timeout,
                    ssl=config.TRACKER_BALANCER_VERIFY_SSL,
                ) as resp:
                    if resp.status != 200:
                        log.warning("Tracker URL %s: HTTP %d",
                                    url[:60], resp.status)
                        return []
                    content = await resp.read()
                    if len(content) > config.TRACKER_BALANCER_MAX_RESPONSE_BYTES:
                        log.warning("Tracker URL %s: слишком большой", url[:60])
                        return []
            text = content.decode("utf-8", errors="ignore")
            return [l.strip() for l in text.splitlines()
                    if l.strip() and not l.startswith("#")]
        except Exception as e:
            log.warning("Tracker URL %s: %s", url[:60], e)
            return []

    def _read_file(self, path: Path) -> list[str]:
        try:
            return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
                    if l.strip() and not l.startswith("#")]
        except Exception:
            return []

    def _write_file(self, path: Path, trackers: list[str]):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(trackers), encoding="utf-8")
        except Exception as e:
            log.debug("cache write: %s", e)

    def reload(self):
        self._trackers = []
        self._loaded_at = 0.0