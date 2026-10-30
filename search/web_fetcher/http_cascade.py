"""Каскадный HTTP: curl_cffi → cloudscraper → aiohttp."""
import asyncio

import aiohttp

try:
    from curl_cffi.requests import AsyncSession as CurlCffiSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    CurlCffiSession = None

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    cloudscraper = None

import config
from core.logging_setup import get_logger

log = get_logger("web_fetcher.http")


class HttpCascade:
    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url
        self._session: aiohttp.ClientSession | None = None
        self._ua_index = 0
        self.stats = {
            "curl_cffi": 0, "cloudscraper": 0,
            "aiohttp": 0, "timeout": 0, "error": 0,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=config.HTTP_FETCH_PER_SOURCE_TIMEOUT
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def next_user_agent(self) -> str:
        uas = config.HTTP_FETCH_USER_AGENTS
        if not uas:
            return config.USER_AGENT
        ua = uas[self._ua_index % len(uas)]
        self._ua_index += 1
        return ua

    async def fetch(self, url: str, headers: dict,
                     proxy: str | None = None) -> tuple[int, str]:
        # 1. curl_cffi (TLS fingerprint) — только без прокси
        if not proxy and HAS_CURL_CFFI and config.USE_CURL_CFFI:
            result = await self._try_curl_cffi(url, headers)
            if result is not None:
                self.stats["curl_cffi"] += 1
                return result

        # 2. cloudscraper — только без прокси
        if not proxy and HAS_CLOUDSCRAPER and config.USE_CLOUDSCRAPER:
            result = await self._try_cloudscraper(url, headers)
            if result is not None:
                self.stats["cloudscraper"] += 1
                return result

        # 3. aiohttp (fallback, поддерживает прокси)
        result = await self._fetch_aiohttp(url, headers, proxy)
        self.stats["aiohttp"] += 1
        return result

    async def _try_curl_cffi(self, url: str, headers: dict):
        try:
            async with CurlCffiSession() as session:
                resp = await session.get(
                    url, headers=headers,
                    impersonate="chrome120",
                    timeout=config.HTTP_FETCH_PER_SOURCE_TIMEOUT,
                )
                return resp.status_code, resp.text
        except asyncio.TimeoutError:
            self.stats["timeout"] += 1
            return None
        except Exception as e:
            log.debug("curl_cffi: %s", e)
            return None

    async def _try_cloudscraper(self, url: str, headers: dict):
        try:
            def _do():
                scraper = cloudscraper.create_scraper()
                r = scraper.get(
                    url, headers=headers,
                    timeout=config.HTTP_FETCH_PER_SOURCE_TIMEOUT,
                )
                return r.status_code, r.text

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _do)
        except Exception as e:
            log.debug("cloudscraper: %s", e)
            return None

    async def _fetch_aiohttp(self, url: str, headers: dict,
                               proxy: str | None) -> tuple[int, str]:
        session = await self._get_session()
        verify_ssl = config.HTTP_FETCH_VERIFY_SSL
        async with session.get(
            url, headers=headers, ssl=verify_ssl, proxy=proxy,
        ) as resp:
            html = await resp.text(errors="ignore")
            return resp.status, html

    async def close(self):
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None