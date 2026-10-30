"""Task: YTS."""
import asyncio

from core.logging_setup import get_logger
from search.aggregator.source_counters import count_by_type

log = get_logger("aggregator.tasks.yts")

_YTS_TIMEOUT = 15.0


async def safe_yts(yts_client, session, query: str, year: str):
    if yts_client is None or not yts_client.is_enabled() or not query:
        return []
    try:
        results = await asyncio.wait_for(
            yts_client.search(session, query, year),
            timeout=_YTS_TIMEOUT,
        )
        log.info("YTS: %d (%s)", len(results), count_by_type(results))
        return results
    except asyncio.TimeoutError:
        log.warning("YTS: timeout")
        return []
    except Exception as e:
        log.warning("YTS: %s", e)
        return []