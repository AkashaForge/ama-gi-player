"""
Web fetcher: HTTP + браузер. Парсит И магниты, И .torrent-ссылки.
Использует cloudscraper для обхода Cloudflare (опционально).
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
from urllib.parse import quote_plus, urljoin

import aiohttp

try:
    import nodriver as uc
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False
    uc = None
    print("[WEB-FETCHER] nodriver не установлен — браузер-фаза отключена")

try:
    from websockets.exceptions import ConnectionClosedError
except ImportError:
    class ConnectionClosedError(Exception):
        pass

import config
from core.config_loader import load_custom_sources
from core.logging_setup import get_logger

log = get_logger("web_fetcher")

# Магниты
_MAGNET_RE = re.compile(r'magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\'<>\s]*')

# .torrent-ссылки в HTML
_TORRENT_LINK_RE = re.compile(
    r'href=["\']([^"\']*(?:/download/|dl\.php\?t=|/torrent/|\.torrent)[^"\']*)["\']',
    re.IGNORECASE,
)
_MAGNET_IN_HREF_RE = re.compile(r'magnet:\?', re.IGNORECASE)

_HTML_ENTITY_RE = re.compile(r'&[a-z]+;')
_WHITESPACE_RE = re.compile(r'\s+')
_TITLE_RE = re.compile(
    r'<a[^>]+href="[^"]*(?:viewtopic|/torrent/|details\.php)[^"]*"[^>]*>'
    r'([^<]{5,300})</a>',
    re.IGNORECASE,
)
_TITLE_FALLBACK_RE = re.compile(r'<a[^>]*>([^<]{5,300})</a>', re.IGNORECASE)
_SEEDERS_RE = re.compile(
    r'class="(?:seedmed|green|seeders?|s|seed)"[^>]*>\s*(\d+)\s*<',
    re.IGNORECASE,
)

_MIN_HTTP_RESULTS = 3


def _extract_title(html: str, pos: int) -> str:
    start = max(0, pos - 800)
    context = html[start:pos]
    for pat in (_TITLE_RE, _TITLE_FALLBACK_RE):
        m = pat.search(context)
        if m:
            title = _HTML_ENTITY_RE.sub(' ', m.group(1).strip())
            return _WHITESPACE_RE.sub(' ', title).strip() or "Без названия"
    return "Без названия"


def _extract_seeders(html: str, pos: int) -> int:
    m = _SEEDERS_RE.search(html[pos:pos + 1200])
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 0


def extract_from_html(html: str, base_url: str = "") -> list[dict]:
    if not html:
        return []

    results = []
    seen = set()

    # 1. Магниты
    for m in _MAGNET_RE.finditer(html):
        url = m.group(0)
        if url in seen:
            continue
        seen.add(url)
        results.append({
            "type": "magnet",
            "url": url,
            "title": _extract_title(html, m.start()),
            "seeders": _extract_seeders(html, m.start()),
        })

    # 2. .torrent-ссылки
    for m in _TORRENT_LINK_RE.finditer(html):
        href = m.group(1).strip()
        if not href or _MAGNET_IN_HREF_RE.search(href):
            continue
        low = href.lower()
        if any(low.endswith(ext) for ext in (
            '.jpg', '.jpeg', '.png', '.gif', '.css', '.js',
            '.ico', '.svg', '.webp',
        )):
            continue
        if not href.startswith(('http://', 'https://')):
            if not base_url:
                continue
            href = urljoin(base_url, href)
        if href in seen:
            continue
        seen.add(href)
        results.append({
            "type": "torrent_url",
            "url": href,
            "title": _extract_title(html, m.start()),
            "seeders": _extract_seeders(html, m.start()),
        })

    return results


def extract_magnets_from_html(html: str) -> list[dict]:
    """Обратная совместимость — только магниты."""
    return [r for r in extract_from_html(html) if r["type"] == "magnet"]


class WebFetcher:
    def __init__(self, chrome_path: str = None, sources: list = None):
        self.chrome_path = chrome_path or config.CHROME_PATH
        self._sources = sources if sources is not None else None
        self._browser = None
        self._browser_disabled = False
        self._http_session: aiohttp.ClientSession | None = None
        self._ua_index = 0

        self._proxy_url: str | None = None
        if getattr(config, "HTTP_FETCH_USE_SYSTEM_PROXY", True):
            self._proxy_url = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("https_proxy")
                or os.environ.get("HTTP_PROXY")
                or os.environ.get("http_proxy")
            )
        if self._proxy_url:
            log.info("Прокси из env: %s", self._proxy_url)
        else:
            log.info("Прокси не задан — прямой запрос")

        self.last_stats = {
            "sources_total": 0,
            "sources_ok": 0,
            "sources_ok_via_proxy": 0,
            "sources_451_parsed": 0,
            "sources_451_empty": 0,
            "sources_403": 0,
            "sources_timeout": 0,
            "sources_error": 0,
            "magnets_found": 0,
            "torrents_found": 0,
        }

    @property
    def sources(self) -> list:
        if self._sources is None:
            self._sources = load_custom_sources()
        return self._sources

    def is_disabled(self) -> bool:
        return not bool(self.sources)

    async def _get_http_session(self) -> aiohttp.ClientSession:
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(
                total=config.HTTP_FETCH_PER_SOURCE_TIMEOUT
            )
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    def _next_user_agent(self) -> str:
        uas = config.HTTP_FETCH_USER_AGENTS
        if not uas:
            return config.USER_AGENT
        ua = uas[self._ua_index % len(uas)]
        self._ua_index += 1
        return ua

    async def _do_request(self, url: str, headers: dict,
                           proxy: str | None) -> tuple[int, str]:
        session = await self._get_http_session()
        async with session.get(
            url, headers=headers, ssl=False, proxy=proxy,
        ) as resp:
            html = await resp.text(errors="ignore")
            return resp.status, html

    async def _fetch_http(self, source: dict, query: str) -> list[dict]:
        sid = source["id"]
        url = source["url_template"].format(query=quote_plus(query))

        headers = dict(config.HTTP_FETCH_HEADERS)
        headers["User-Agent"] = self._next_user_agent()

        self.last_stats["sources_total"] += 1

        attempts = []
        if self._proxy_url:
            attempts.append(("proxy", self._proxy_url))
            attempts.append(("direct", None))
        else:
            attempts.append(("direct", None))

        for attempt_name, proxy in attempts:
            try:
                status, html = await self._do_request(url, headers, proxy)
            except asyncio.TimeoutError:
                self.last_stats["sources_timeout"] += 1
                log.warning("%s (%s): timeout", sid, attempt_name)
                continue
            except Exception as e:
                self.last_stats["sources_error"] += 1
                log.warning("%s (%s): %s: %s",
                            sid, attempt_name, type(e).__name__, e)
                continue

            results = extract_from_html(html, base_url=url)

            if status == 200:
                self.last_stats["sources_ok"] += 1
                if attempt_name == "proxy":
                    self.last_stats["sources_ok_via_proxy"] += 1
                mag = sum(1 for r in results if r["type"] == "magnet")
                tor = sum(1 for r in results if r["type"] == "torrent_url")
                self.last_stats["magnets_found"] += mag
                self.last_stats["torrents_found"] += tor
                log.info("%s (%s, HTTP 200): magnet=%d torrent_url=%d",
                         sid, attempt_name, mag, tor)
                return results

            if status == 451:
                if results:
                    self.last_stats["sources_451_parsed"] += 1
                    mag = sum(1 for r in results if r["type"] == "magnet")
                    tor = sum(1 for r in results if r["type"] == "torrent_url")
                    self.last_stats["magnets_found"] += mag
                    self.last_stats["torrents_found"] += tor
                    log.info(
                        "%s (%s, HTTP 451, тело с раздачами): "
                        "magnet=%d torrent_url=%d",
                        sid, attempt_name, mag, tor,
                    )
                    return results
                log.info(
                    "%s (%s, HTTP 451, тело пустое) — пробую %s",
                    sid, attempt_name,
                    "напрямую" if attempt_name == "proxy" else "(больше нет)",
                )
                continue

            if status == 403:
                self.last_stats["sources_403"] += 1
                log.warning("%s (%s, HTTP 403): 0 magnet", sid, attempt_name)
                continue

            if results:
                self.last_stats["sources_ok"] += 1
                mag = sum(1 for r in results if r["type"] == "magnet")
                tor = sum(1 for r in results if r["type"] == "torrent_url")
                self.last_stats["magnets_found"] += mag
                self.last_stats["torrents_found"] += tor
                log.info(
                    "%s (%s, HTTP %d, тело с раздачами): "
                    "magnet=%d torrent_url=%d",
                    sid, attempt_name, status, mag, tor,
                )
                return results

            log.info("%s (%s, HTTP %d): 0 magnet",
                     sid, attempt_name, status)

        self.last_stats["sources_451_empty"] += 1
        return []

    async def _http_phase(self, query: str) -> list[dict]:
        sources = self.sources
        if not sources:
            return []

        log.info("HTTP-фаза: %d источников параллельно", len(sources))
        tasks = [self._fetch_http(src, query) for src in sources]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        for r in results_list:
            if isinstance(r, list):
                all_results.extend(r)

        log.info("HTTP-фаза итог: %d", len(all_results))
        return all_results

    async def _ensure_browser(self):
        if self._browser_disabled:
            raise RuntimeError("браузер отключён")
        if self._browser is not None:
            return self._browser

        exe_path = self.chrome_path or ""
        if exe_path and "msedge.exe" in exe_path.lower():
            log.info("Nodriver не поддерживает Edge — браузерная фаза пропущена")
            self._browser_disabled = True
            raise RuntimeError("Edge не поддерживается Nodriver")

        try:
            self._browser = await uc.start(
                headless=config.BROWSER_HEADLESS,
                browser_executable_path=self.chrome_path,
                browser_args=list(config.BROWSER_EXTRA_ARGS),
            )
        except Exception as e:
            log.error("Не удалось запустить браузер: %s", e)
            self._browser_disabled = True
            raise
        return self._browser

    async def _fetch_browser(self, source: dict, query: str) -> list[dict]:
        sid = source["id"]
        url = source["url_template"].format(query=quote_plus(query))
        log.info("%s (browser): '%s'", sid, query)

        try:
            browser = await self._ensure_browser()
        except Exception:
            return []

        page = None
        try:
            page = await browser.get(url)
            await page.sleep(2.0)

            marker = source["ready_selector"].lstrip("#.")
            deadline = (
                asyncio.get_event_loop().time() + config.BROWSER_FETCH_TIMEOUT
            )
            ready = False
            while asyncio.get_event_loop().time() < deadline:
                try:
                    html = await page.get_content()
                except Exception:
                    html = ""
                if marker in html:
                    ready = True
                    break
                await page.sleep(0.5)

            if not ready:
                log.warning("%s (browser): селектор не найден", sid)

            html = await page.get_content()
            results = extract_from_html(html, base_url=url)
            mag = sum(1 for r in results if r["type"] == "magnet")
            tor = sum(1 for r in results if r["type"] == "torrent_url")
            log.info("%s (browser): magnet=%d torrent_url=%d", sid, mag, tor)
            return results
        except ConnectionClosedError:
            log.error("%s (browser): соединение потеряно", sid)
            return []
        except Exception as e:
            log.error("%s (browser): %s: %s", sid, type(e).__name__, e)
            return []
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _browser_phase(self, query: str) -> list[dict]:
        if not HAS_BROWSER:
            return []
        if self._browser_disabled:
            return []
        sources = self.sources
        if not sources:
            return []

        log.info("Браузерная фаза: %d источников последовательно", len(sources))
        all_results = []

        try:
            async with asyncio.timeout(config.BROWSER_MAX_TOTAL_TIMEOUT):
                for src in sources:
                    if self._browser_disabled:
                        break
                    results = await self._fetch_browser(src, query)
                    all_results.extend(results)
        except asyncio.TimeoutError:
            log.warning("Браузерная фаза: общий таймаут")

        return all_results

    async def search_all(self, query: str) -> list[dict]:
        self.last_stats = {
            "sources_total": 0, "sources_ok": 0, "sources_ok_via_proxy": 0,
            "sources_451_parsed": 0, "sources_451_empty": 0,
            "sources_403": 0, "sources_timeout": 0,
            "sources_error": 0, "magnets_found": 0, "torrents_found": 0,
        }

        if not query:
            return []
        if not self.sources:
            return []

        http_results = await self._http_phase(query)

        browser_results = []
        if len(http_results) < _MIN_HTTP_RESULTS:
            log.info("HTTP дал %d (< %d) — пробую браузер",
                     len(http_results), _MIN_HTTP_RESULTS)
            browser_results = await self._browser_phase(query)

        combined = http_results + browser_results
        seen = set()
        unique = []
        for m in combined:
            url = m.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            unique.append(m)

        s = self.last_stats
        log.info(
            "web_fetcher итог: HTTP=%d + browser=%d → unique=%d "
            "(magnet=%d torrent_url=%d) "
            "(ok=%d, ok_proxy=%d, 451_parsed=%d, 451_empty=%d, "
            "403=%d, timeout=%d, err=%d)",
            len(http_results), len(browser_results), len(unique),
            s["magnets_found"], s["torrents_found"],
            s["sources_ok"], s["sources_ok_via_proxy"],
            s["sources_451_parsed"], s["sources_451_empty"],
            s["sources_403"], s["sources_timeout"], s["sources_error"],
        )
        return unique

    async def close(self):
        if self._http_session and not self._http_session.closed:
            try:
                await self._http_session.close()
            except Exception:
                pass
            self._http_session = None
        if self._browser:
            try:
                await self._browser.stop()
            except Exception:
                pass
            self._browser = None
