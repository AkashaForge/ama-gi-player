"""WebFetcher — координатор HTTP-фазы + браузерной."""
import asyncio
import os
from urllib.parse import quote_plus

import config
from core.config_loader import load_custom_sources
from core.logging_setup import get_logger
from search.web_fetcher.browser_fetcher import BrowserFetcher
from search.web_fetcher.html_parser import extract_from_html
from search.web_fetcher.http_cascade import HttpCascade

log = get_logger("web_fetcher")


class WebFetcher:
    def __init__(self, chrome_path: str | None = None,
                 sources: list | None = None):
        self._sources = sources
        self._proxy_url: str | None = None

        if config.HTTP_FETCH_USE_SYSTEM_PROXY:
            self._proxy_url = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("https_proxy")
                or os.environ.get("HTTP_PROXY")
                or os.environ.get("http_proxy")
            )
        log.info("Прокси: %s" if self._proxy_url else "Прокси не задан",
                 self._proxy_url or "")

        self.http = HttpCascade(proxy_url=self._proxy_url)
        self.browser = BrowserFetcher(chrome_path)

        self.last_stats = {
            "sources_total": 0, "sources_ok": 0,
            "magnets_found": 0, "torrents_found": 0,
        }

    @property
    def sources(self) -> list:
        if self._sources is None:
            self._sources = load_custom_sources()
        return self._sources

    def is_disabled(self) -> bool:
        return not bool(self.sources)

    # ==================================================================
    #  HTTP
    # ==================================================================
    async def _fetch_http(self, source: dict, query: str) -> list[dict]:
        sid = source["id"]
        url = source["url_template"].format(query=quote_plus(query))
        headers = dict(config.HTTP_FETCH_HEADERS)
        headers["User-Agent"] = self.http.next_user_agent()

        self.last_stats["sources_total"] += 1

        attempts = [("direct", None)]
        if self._proxy_url:
            attempts.insert(0, ("proxy", self._proxy_url))

        for attempt_name, proxy in attempts:
            try:
                status, html = await self.http.fetch(url, headers, proxy)
            except asyncio.TimeoutError:
                log.warning("%s (%s): timeout", sid, attempt_name)
                continue
            except Exception as e:
                log.warning("%s (%s): %s", sid, attempt_name, e)
                continue

            results = extract_from_html(html, base_url=url)
            if status == 200 or results:
                self.last_stats["sources_ok"] += 1
                mag = sum(1 for r in results if r["type"] == "magnet")
                tor = sum(1 for r in results if r["type"] == "torrent_url")
                self.last_stats["magnets_found"] += mag
                self.last_stats["torrents_found"] += tor
                log.info("%s (%s, HTTP %d): magnet=%d torrent_url=%d",
                         sid, attempt_name, status, mag, tor)
                return results

            log.info("%s (%s, HTTP %d): 0", sid, attempt_name, status)

        return []

    async def _http_phase(self, query: str) -> list[dict]:
        sources = self.sources
        if not sources:
            return []
        log.info("HTTP-фаза: %d параллельно", len(sources))
        tasks = [self._fetch_http(s, query) for s in sources]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        out = []
        for r in results_list:
            if isinstance(r, list):
                out.extend(r)
        log.info("HTTP-фаза итог: %d", len(out))
        return out

    # ==================================================================
    #  MAIN
    # ==================================================================
    async def search_all(self, query: str) -> list[dict]:
        self.last_stats = {
            "sources_total": 0, "sources_ok": 0,
            "magnets_found": 0, "torrents_found": 0,
        }

        if not query or not self.sources:
            return []

        http_results = await self._http_phase(query)

        min_http = config.WEB_FETCHER_MIN_HTTP_RESULTS
        browser_results = []
        if len(http_results) < min_http:
            log.info("HTTP %d < %d — пробую браузер",
                     len(http_results), min_http)
            browser_results = await self.browser.fetch_many(
                self.sources, query
            )

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
            "(methods: curl_cffi=%d cloudscraper=%d aiohttp=%d browser=%d)",
            len(http_results), len(browser_results), len(unique),
            s["magnets_found"], s["torrents_found"],
            self.http.stats["curl_cffi"], self.http.stats["cloudscraper"],
            self.http.stats["aiohttp"], self.browser.count_fetched,
        )
        return unique

    async def close(self):
        await self.http.close()
        await self.browser.close()