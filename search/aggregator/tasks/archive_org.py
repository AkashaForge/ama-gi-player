"""Task: Internet Archive."""
import asyncio

import config
from core.logging_setup import get_logger

log = get_logger("aggregator.tasks.archive_org")

_ARCHIVE_ORG_TIMEOUT = 30.0


async def safe_archive_org(searcher, query: str, year: str):
    if not searcher or not query or not config.ARCHIVE_ORG_ENABLED:
        return []
    try:
        results = await asyncio.wait_for(
            searcher.search(query, year),
            timeout=_ARCHIVE_ORG_TIMEOUT,
        )
        log.info("archive.org: %d direct_url", len(results))
        return results
    except asyncio.TimeoutError:
        log.warning("archive.org: timeout")
        return []
    except Exception as e:
        log.warning("archive.org: %s", e)
        return []