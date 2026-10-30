"""Task: web_fetcher поиск."""
import asyncio

from core.logging_setup import get_logger
from search.aggregator.source_counters import count_by_type

log = get_logger("aggregator.tasks.web_fetcher")

_WEB_FETCHER_TIMEOUT = 60.0


async def safe_web_fetcher(fetcher, query: str):
    if not fetcher or not query:
        return []
    try:
        if fetcher.is_disabled():
            return []
        results = await asyncio.wait_for(
            fetcher.search_all(query),
            timeout=_WEB_FETCHER_TIMEOUT,
        )
        log.info("web_fetcher: %d (%s)", len(results), count_by_type(results))
        return results
    except asyncio.TimeoutError:
        log.warning("web_fetcher: timeout")
        return []
    except Exception as e:
        log.warning("web_fetcher: %s", e)
        return []