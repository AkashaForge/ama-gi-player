"""Главный координатор параллельного поиска."""
import asyncio

import aiohttp

import config
from core.logging_setup import get_logger
from core.utils import dedup_by_url
from search.aggregator.language_filter import filter_by_language
from search.aggregator.source_counters import count_by_type, enrich_magnets
from search.aggregator.tasks import (
    safe_archive_org,
    safe_balancers,
    safe_jackett,
    safe_torapi,
    safe_web_fetcher,
    safe_yts,
)
from search.filters import is_safe_release, process_and_rank

log = get_logger("aggregator")


async def find_torrent_stream(
    tracker_client,
    web_fetcher,
    archive_org,
    session: aiohttp.ClientSession,
    balancer_client=None,
    title_ru: str = "",
    title_en: str = "",
    year: str = "",
    imdb_id: str = "",
    language: str = "en",
    yts_client=None,
    extra_trackers: list[str] | None = None,
) -> tuple[list[dict], str]:
    title_ru = (title_ru or "").strip()
    title_en = (title_en or "").strip()
    year = (year or "").strip()
    imdb_id = (imdb_id or "").strip()

    if language not in ("ru", "en"):
        return [], f"UNKNOWN LANGUAGE: {language}"

    legal_only = config.LEGAL_ONLY_MODE

    log.info("=" * 60)
    log.info(
        "SEARCH (%s): RU='%s' EN='%s' YEAR='%s' IMDb='%s' mode=%s",
        language.upper(), title_ru, title_en, year, imdb_id,
        "PUBLIC" if legal_only else "PRIVATE",
    )
    log.info("=" * 60)

    archive_query = title_en or title_ru
    primary_query = title_ru if language == "ru" else (title_en or title_ru)

    if legal_only:
        archive_results = await safe_archive_org(
            archive_org, archive_query, year
        )
        if not archive_results and archive_query != title_ru:
            archive_results = await safe_archive_org(
                archive_org, title_ru, year
            )
        unique = dedup_by_url(archive_results)
        log.info("RESULT (public): %d direct_url", len(unique))
        if unique:
            return unique, ""
        return [], "ФИЛЬМ НЕ НАЙДЕН В INTERNET ARCHIVE"

    yts_on = (
        language == "en"
        and yts_client is not None
        and yts_client.is_enabled()
    )

    jackett_task = asyncio.create_task(safe_jackett(
        tracker_client, session,
        title_ru=title_ru if language == "ru" else "",
        title_en=title_en,
        year=year,
        imdb_id=imdb_id,
        language=language,
    ))
    fetcher_task = asyncio.create_task(
        safe_web_fetcher(web_fetcher, primary_query)
    )
    archive_task = asyncio.create_task(
        safe_archive_org(archive_org, archive_query, year)
    )
    balancer_task = asyncio.create_task(
        safe_balancers(balancer_client, title_en, title_ru, year, imdb_id)
    )
    torapi_task = asyncio.create_task(
        safe_torapi(session, primary_query, year)
    )

    tasks = [jackett_task, fetcher_task, archive_task,
             balancer_task, torapi_task]

    if yts_on:
        yts_task = asyncio.create_task(
            safe_yts(yts_client, session, primary_query, year)
        )
        tasks.append(yts_task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    jackett_res = results[0] if not isinstance(results[0], Exception) else ([], {})
    if isinstance(jackett_res, tuple):
        jackett_results, _info = jackett_res
    else:
        jackett_results, _info = [], {}

    fetcher_results = results[1] if isinstance(results[1], list) else []
    archive_results = results[2] if isinstance(results[2], list) else []
    balancer_results = results[3] if isinstance(results[3], list) else []
    torapi_results = results[4] if isinstance(results[4], list) else []
    yts_results = results[5] if len(results) > 5 and isinstance(results[5], list) else []

    log.info(
        "Search done: Jackett=%d, web=%d, archive=%d, balancers=%d, "
        "TorAPI=%d, YTS=%d",
        len(jackett_results), len(fetcher_results),
        len(archive_results), len(balancer_results),
        len(torapi_results), len(yts_results),
    )

    combined_p2p = (
        jackett_results + fetcher_results
        + yts_results + torapi_results
    )
    filtered = filter_by_language(combined_p2p, language)
    safe = [
        s for s in filtered
        if is_safe_release(s.get("title", ""), s.get("size", 0))
    ]
    safe = enrich_magnets(safe, extra_trackers)

    ranked = process_and_rank(safe, primary_query, year=year)
    unique_p2p = dedup_by_url(ranked)
    archive_unique = dedup_by_url(archive_results)

    balancer_valid = [
        s for s in balancer_results
        if s.get("type") == "direct_url"
    ]
    final = balancer_valid + unique_p2p + archive_unique

    log.info(
        "RESULT: %d (%s, balancers=%d)",
        len(final), count_by_type(final), len(balancer_valid),
    )
    if not final:
        return [], f"ПОТОК НЕ НАЙДЕН ({language.upper()})"
    return final, ""