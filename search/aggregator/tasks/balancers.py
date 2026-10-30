"""Task: онлайн-балансеры."""
import asyncio

from core.logging_setup import get_logger

log = get_logger("aggregator.tasks.balancers")

_BALANCER_TIMEOUT = 15.0


async def safe_balancers(balancer_client, title_en: str,
                           title_ru: str, year: str, imdb_id: str):
    if balancer_client is None:
        return []
    query = title_en or title_ru
    if not query:
        return []
    try:
        results = await asyncio.wait_for(
            balancer_client.search(query, year, imdb_id),
            timeout=_BALANCER_TIMEOUT,
        )
        if results:
            log.info("Balancers: %d direct_url", len(results))
        return results
    except asyncio.TimeoutError:
        log.warning("Balancers: timeout")
        return []
    except Exception as e:
        log.warning("Balancers: %s", e)
        return []