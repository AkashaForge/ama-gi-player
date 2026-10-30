"""Клиент онлайн-балансеров. VideoCDN — основной рабочий."""
import asyncio
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("balancer")

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_M3U8_RE = re.compile(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*')
_MP4_RE = re.compile(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*')


def _is_safe_url(url: str) -> bool:
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


def _is_valid_stream_url(url: str) -> bool:
    if not _is_safe_url(url):
        return False
    low = url.lower()
    if any(x in low for x in ("/ads/", "banner", "promo", "/trailer/", "/ad/")):
        return False
    return True


class BalancerClient:
    def __init__(self):
        self._cache: dict[str, tuple[list[dict], float]] = {}
        self._blacklist: dict[str, float] = {}
        self._failures: dict[str, int] = {}

    async def search(self, query: str, year: str, imdb_id: str) -> list[dict]:
        balancers = self._load_balancers()
        if not balancers:
            return []

        cache_key = f"{query}|{year}|{imdb_id}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached:
            data, ts = cached
            if (now - ts) < config.BALANCER_CACHE_TTL_HOURS * 3600:
                log.info("Balancers cache HIT: %d", len(data))
                return data

        tasks = [
            self._query_balancer(name, btype, url, query, year, imdb_id)
            for name, (btype, url) in balancers.items()
        ]
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        for res in results_nested:
            if isinstance(res, list):
                all_results.extend(res)

        validated = self._validate_and_dedup(all_results, query)
        self._cache[cache_key] = (validated, now)
        log.info("Balancers: %d валидных из %d", len(validated), len(all_results))
        return validated

    def _load_balancers(self) -> dict[str, tuple[str, str]]:
        path: Path = config.BALANCERS_FILE
        if not path.exists():
            return {}
        balancers = {}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|", 1)
                if len(parts) != 2:
                    log.warning("Balancers: bad format: %s", line[:50])
                    continue
                btype, url = parts[0].strip().lower(), parts[1].strip()
                if btype not in ("json", "videocdn", "html"):
                    log.warning("Balancers: unknown type '%s'", btype)
                    continue
                if not _is_safe_url(url.replace("{query}", "x")
                                    .replace("{year}", "2026")
                                    .replace("{imdb_id}", "tt0")):
                    log.warning("Balancers: unsafe URL: %s", url[:60])
                    continue
                name = urlparse(url).netloc or f"b{len(balancers)}"
                balancers[name] = (btype, url)
        except Exception as e:
            log.warning("Balancers read: %s", e)
        return balancers

    async def _query_balancer(self, name, btype, url_template,
                                query, year, imdb_id):
        if name in self._blacklist and time.time() < self._blacklist[name]:
            return []
        try:
            url = url_template.format(
                query=quote_plus(query or ""),
                year=year or "",
                imdb_id=imdb_id or "",
            )
        except KeyError as e:
            log.warning("Balancer '%s': template error %s", name, e)
            return []

        try:
            timeout = aiohttp.ClientTimeout(total=config.BALANCER_REQUEST_TIMEOUT_SEC)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout,
                                        ssl=config.BALANCER_VERIFY_SSL) as resp:
                    if resp.status != 200:
                        log.warning("Balancer '%s': HTTP %d", name, resp.status)
                        self._on_failure(name)
                        return []
                    content = await resp.read()
                    if len(content) > config.BALANCER_MAX_RESPONSE_BYTES:
                        log.warning("Balancer '%s': response too big", name)
                        return []
                    text = content.decode("utf-8", errors="ignore")
        except asyncio.TimeoutError:
            log.warning("Balancer '%s': timeout", name)
            self._on_failure(name)
            return []
        except Exception as e:
            log.warning("Balancer '%s': %s", name, e)
            self._on_failure(name)
            return []

        if btype == "json":
            results = self._parse_json(text, name, query)
        elif btype == "videocdn":
            results = self._parse_videocdn(text, name, query)
        elif btype == "html":
            results = self._parse_html(text, name, query)
        else:
            results = []

        if results:
            self._on_success(name)
        else:
            self._on_failure(name)
        return results

    def _parse_json(self, text, name, query):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        urls = self._find_urls_in_json(data)
        return [{"type": "direct_url", "url": u, "title": query,
                 "indexer": "balancer", "size": 0, "seeders": 0}
                for u in urls]

    def _parse_videocdn(self, text, name, query):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        urls = []
        if isinstance(data, dict):
            for item in data.get("results", []) or data.get("data", []) or []:
                if isinstance(item, dict):
                    link = (item.get("link") or item.get("url")
                            or item.get("stream") or "")
                    if link and _is_valid_stream_url(link):
                        urls.append(link)
        if not urls:
            urls = self._find_urls_in_json(data)
        return [{"type": "direct_url", "url": u, "title": query,
                 "indexer": "videocdn", "size": 0, "seeders": 0}
                for u in urls]

    def _parse_html(self, text, name, query):
        urls = set()
        for pat in (_M3U8_RE, _MP4_RE):
            for m in pat.finditer(text):
                u = m.group(0)
                if _is_valid_stream_url(u):
                    urls.add(u)
        return [{"type": "direct_url", "url": u, "title": query,
                 "indexer": "balancer", "size": 0, "seeders": 0}
                for u in urls]

    def _find_urls_in_json(self, obj, depth=0):
        if depth > 5:
            return []
        urls = []
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, str) and _is_valid_stream_url(v):
                    urls.append(v)
                elif isinstance(v, (dict, list)):
                    urls.extend(self._find_urls_in_json(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                urls.extend(self._find_urls_in_json(item, depth + 1))
        return urls

    def _validate_and_dedup(self, results, query):
        import difflib
        seen = set()
        out = []
        for r in results:
            url = r.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            title = r.get("title", "")
            if title and query:
                ratio = difflib.SequenceMatcher(
                    None, title.lower(), query.lower()
                ).ratio()
                if ratio < config.BALANCER_VALIDATE_TITLE_THRESHOLD:
                    continue
            out.append(r)
        return out

    def _on_failure(self, name):
        self._failures[name] = self._failures.get(name, 0) + 1
        if self._failures[name] >= config.BALANCER_BLACKLIST_FAILURES:
            self._blacklist[name] = time.time() + config.BALANCER_BLACKLIST_TTL_HOURS * 3600
            log.warning("Balancer '%s' → blacklist", name)

    def _on_success(self, name):
        self._failures[name] = 0