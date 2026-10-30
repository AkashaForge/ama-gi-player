"""Task: Jackett (Torznab) поиск."""
import asyncio

from core.logging_setup import get_logger
from search.aggregator.source_counters import count_by_type

log = get_logger("aggregator.tasks.jackett")

_JACKETT_TIMEOUT = 30.0


async def safe_jackett(client, session, **kwargs):
    if client is None:
        return [], {}
    try:
        info = await client.diagnose(session)
        results = await asyncio.wait_for(
            client.search_all(session, **kwargs),
            timeout=_JACKETT_TIMEOUT,
        )
        log.info("Jackett: %d (%s)", len(results), count_by_type(results))
        return results, info
    except asyncio.TimeoutError:
        log.warning("Jackett timeout %.0fs", _JACKETT_TIMEOUT)
        return [], {}
    except Exception as e:
        log.warning("Jackett: %s: %s", type(e).__name__, e)
        return [], {}