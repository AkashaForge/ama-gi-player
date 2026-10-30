"""Браузерная фаза: nodriver для сайтов с JS challenge."""
import asyncio

try:
    import nodriver as uc
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False
    uc = None

try:
    from websockets.exceptions import ConnectionClosedError
except ImportError:
    class ConnectionClosedError(Exception):
        pass

import config
from core.logging_setup import get_logger
from search.web_fetcher.html_parser import extract_from_html

log = get_logger("web_fetcher.browser")


class BrowserFetcher:
    def __init__(self, chrome_path: str | None):
        self.chrome_path = chrome_path or config.CHROME_PATH
        self._browser = None
        self._browser_disabled = False
        self.count_fetched = 0

    @property
    def is_disabled(self) -> bool:
        return self._browser_disabled

    async def _ensure_browser(self):
        if self._browser_disabled:
            raise RuntimeError("browser disabled")
        if self._browser is not None:
            return self._browser

        exe_path = self.chrome_path or ""
        if exe_path and "msedge.exe" in exe_path.lower():
            log.info("Nodriver не поддерживает Edge — пропуск браузерной фазы")
            self._browser_disabled = True
            raise RuntimeError("Edge не поддерживается")

        try:
            self._browser = await uc.start(
                headless=config.BROWSER_HEADLESS,
                browser_executable_path=self.chrome_path,
                browser_args=list(config.BROWSER_EXTRA_ARGS),
            )
        except Exception as e:
            log.error("Browser start: %s", e)
            self._browser_disabled = True
            raise
        return self._browser

    async def fetch_one(self, source: dict, query: str) -> list[dict]:
        from urllib.parse import quote_plus
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
            deadline = (asyncio.get_event_loop().time()
                        + config.BROWSER_FETCH_TIMEOUT)
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
            self.count_fetched += 1
            log.info("%s (browser): %d", sid, len(results))
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

    async def fetch_many(self, sources: list[dict],
                          query: str) -> list[dict]:
        if not HAS_BROWSER or self._browser_disabled:
            return []
        if not config.USE_NODRIVER:
            return []
        if not sources:
            return []

        log.info("Браузерная фаза: %d (max 3 параллельно)", len(sources))
        sem = asyncio.Semaphore(3)

        async def _one(src):
            async with sem:
                if self._browser_disabled:
                    return []
                return await self.fetch_one(src, query)

        all_results = []
        tasks = [asyncio.create_task(_one(s)) for s in sources]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config.BROWSER_MAX_TOTAL_TIMEOUT,
            )
            for r in results:
                if isinstance(r, list):
                    all_results.extend(r)
        except asyncio.TimeoutError:
            log.warning("Browser phase: общий таймаут")
            for t in tasks:
                if not t.done():
                    t.cancel()
        return all_results

    async def close(self):
        if self._browser:
            try:
                await self._browser.stop()
            except Exception:
                pass
            self._browser = None