"""
Параллельный поиск.

PUBLIC mode (LEGAL_ONLY_MODE=True):
    Только archive.org. Jackett, web_fetcher, YTS не вызываются.

PRIVATE mode (LEGAL_ONLY_MODE=False):
    Все источники параллельно.
"""

import asyncio
import re

import aiohttp

import config
from core.logging_setup import get_logger
from core.utils import dedup_by_url
from search.filters import has_russian_marker, is_safe_release, process_and_rank
from services.torrent.swarm_grouper import enrich_magnet_with_default_trackers

log = get_logger("aggregator")

_JACKETT_TIMEOUT = 45.0
_WEB_FETCHER_TIMEOUT = 90.0
_ARCHIVE_ORG_TIMEOUT = 30.0
_YTS_TIMEOUT = 15.0

_CYRILLIC_RE = re.compile(r'[а-яА-ЯёЁ]')
_EN_STRICT_RUS_RE = re.compile(
    r'\b(?:rus|дубл|лиценз|многоголос|одноголос)\b',
    re.IGNORECASE,
)


def _is_russian_release(title: str, indexer: str = "") -> bool:
    if not title:
        return False
    if _CYRILLIC_RE.search(title):
        return True
    if has_russian_marker(title):
        return True
    if indexer:
        idx_low = indexer.lower()
        ru_indexers = getattr(config, "RU_INDEXER_IDS", frozenset())
        if idx_low in ru_indexers:
            return True
        for ru_id in ru_indexers:
            if ru_id in idx_low:
                return True
    return False


def _filter_ru_strict(sources: list[dict], step: str) -> list[dict]:
    before = len(sources)
    filtered = [
        s for s in sources
        if _is_russian_release(
            s.get("title", ""), (s.get("indexer") or "").lower()
        )
    ]
    if before != len(filtered):
        log.info("[%s] RU-фильтр: %d → %d", step, before, len(filtered))
    return filtered


def _filter_en_strict(sources: list[dict], step: str) -> list[dict]:
    ru_indexers = getattr(config, "RU_INDEXER_IDS", frozenset())
    before = len(sources)
    filtered = []
    for s in sources:
        title = s.get("title", "") or ""
        indexer = (s.get("indexer") or "").lower()

        if indexer == "yts":
            filtered.append(s)
            continue

        if _CYRILLIC_RE.search(title):
            continue
        if indexer:
            if indexer in ru_indexers:
                continue
            if any(ru_id in indexer for ru_id in ru_indexers):
                continue
        if _EN_STRICT_RUS_RE.search(title):
            continue

        filtered.append(s)

    if before != len(filtered):
        log.info("[%s] EN-фильтр: %d → %d", step, before, len(filtered))
    return filtered


def _count_by_type(sources: list[dict]) -> str:
    mag = sum(1 for s in sources if s.get("type") == "magnet")
    tor = sum(1 for s in sources if s.get("type") == "torrent_url")
    dr = sum(1 for s in sources if s.get("type") == "direct_url")
    return f"magnet={mag} torrent_url={tor} direct_url={dr}"


def _enrich_magnets(sources: list[dict]) -> list[dict]:
    out = []
    count = 0
    for s in sources:
        if s.get("type") == "magnet":
            old = s.get("url", "")
            new = enrich_magnet_with_default_trackers(old)
            if new != old:
                count += 1
                s = dict(s)
                s["url"] = new
        out.append(s)
    if count:
        log.info("Enriched %d magnets with default trackers", count)
    return out


# ======================================================================
#  SAFE WRAPPERS
# ======================================================================
async def _safe_jackett(tracker_client, session, **kwargs):
    if tracker_client is None:
        return [], {}
    try:
        info = await tracker_client.diagnose(session)
        results = await asyncio.wait_for(
            tracker_client.search_all(session, **kwargs),
            timeout=_JACKETT_TIMEOUT,
        )
        log.info("Jackett: %d (%s)", len(results), _count_by_type(results))
        return results, info
    except asyncio.TimeoutError:
        log.warning("Jackett: таймаут %.0fs", _JACKETT_TIMEOUT)
        return [], {}
    except Exception as e:
        log.warning("Jackett: %s: %s", type(e).__name__, e)
        return [], {}


async def _safe_web_fetcher(web_fetcher, query):
    if not web_fetcher or not query:
        return []
    try:
        if web_fetcher.is_disabled():
            log.info("web_fetcher: отключён")
            return []
        results = await asyncio.wait_for(
            web_fetcher.search_all(query),
            timeout=_WEB_FETCHER_TIMEOUT,
        )
        log.info("web_fetcher: %d (%s)", len(results), _count_by_type(results))
        return results
    except asyncio.TimeoutError:
        log.warning("web_fetcher: таймаут")
        return []
    except Exception as e:
        log.warning("web_fetcher: %s: %s", type(e).__name__, e)
        return []


async def _safe_archive_org(archive_org, query, year):
    if not archive_org or not query:
        return []
    if not getattr(config, "ARCHIVE_ORG_ENABLED", True):
        return []
    try:
        results = await asyncio.wait_for(
            archive_org.search(query, year),
            timeout=_ARCHIVE_ORG_TIMEOUT,
        )
        log.info("archive.org: %d direct_url", len(results))
        return results
    except asyncio.TimeoutError:
        log.warning("archive.org: таймаут %.0fs", _ARCHIVE_ORG_TIMEOUT)
        return []
    except Exception as e:
        log.warning("archive.org: %s: %s", type(e).__name__, e)
        return []


async def _safe_yts(yts_client, session, query, year):
    if yts_client is None or not yts_client.is_enabled():
        return []
    if not query:
        return []
    try:
        results = await asyncio.wait_for(
            yts_client.search(session, query, year),
            timeout=_YTS_TIMEOUT,
        )
        log.info("YTS: %d (%s)", len(results), _count_by_type(results))
        return results
    except asyncio.TimeoutError:
        log.warning("YTS: таймаут")
        return []
    except Exception as e:
        log.warning("YTS: %s: %s", type(e).__name__, e)
        return []


# ======================================================================
#  MAIN
# ======================================================================
async def find_torrent_stream(
    tracker_client,
    web_fetcher,
    archive_org,
    session: aiohttp.ClientSession,
    title_ru: str = "",
    title_en: str = "",
    year: str = "",
    imdb_id: str = "",
    language: str = "en",
    yts_client=None,
) -> tuple[list[dict], str]:
    title_ru = (title_ru or "").strip()
    title_en = (title_en or "").strip()
    year = (year or "").strip()
    imdb_id = (imdb_id or "").strip()

    if language not in ("ru", "en"):
        return [], f"НЕИЗВЕСТНЫЙ ЯЗЫК: {language}"

    legal_only = getattr(config, "LEGAL_ONLY_MODE", True)

    log.info("=" * 60)
    log.info(
        "ПОИСК (%s): RU='%s' EN='%s' YEAR='%s' IMDb='%s' | mode=%s",
        language.upper(), title_ru, title_en, year, imdb_id,
        "PUBLIC (archive.org only)" if legal_only else "PRIVATE (all)",
    )
    log.info("=" * 60)

    # === Основной запрос для archive.org ===
    # IA плохо работает с кириллицей — для RU используем EN
    if language == "ru":
        archive_query = title_en or title_ru
        primary_query = title_ru
        filter_fn = _filter_ru_strict
    else:
        archive_query = title_en or title_ru
        primary_query = title_en or title_ru
        filter_fn = _filter_en_strict

    # ==================================================================
    #  PUBLIC: только archive.org
    # ==================================================================
    if legal_only:
        log.info("PUBLIC mode: только archive.org (Jackett/web/YTS пропущены)")
        archive_results = await _safe_archive_org(
            archive_org, archive_query, year
        )

        if not archive_results and archive_query != title_ru:
            # Fallback на title_ru (редко, но бывает)
            log.info("IA: retry с title_ru='%s'", title_ru)
            archive_results = await _safe_archive_org(
                archive_org, title_ru, year
            )

        unique = dedup_by_url(archive_results)

        log.info("=" * 60)
        log.info("ИТОГ (public): %d direct_url", len(unique))

        if unique:
            for i, s in enumerate(unique[:5], 1):
                log.info(
                    "  [%d] direct_url size=%.1f MB fmt=%s title='%s'",
                    i, (s.get("size", 0) or 0) / 1024 / 1024,
                    s.get("format", "?"),
                    (s.get("title") or "?")[:60],
                )
            log.info("=" * 60)
            return unique, ""

        log.warning("ИТОГ (public): пусто")
        log.info("=" * 60)
        msg = (
            "ФИЛЬМ НЕ НАЙДЕН В INTERNET ARCHIVE.\n\n"
            "Возможные причины:\n"
            "• Фильм не загружен в Internet Archive\n"
            "• Поиск по названию не сработал — попробуйте другой фильм\n"
            "• В public-версии доступны только фильмы, "
            "загруженные в Internet Archive"
        )
        return [], msg

    # ==================================================================
    #  PRIVATE: все источники
    # ==================================================================
    yts_enabled = (
        language == "en" and yts_client is not None
        and yts_client.is_enabled()
    )

    jackett_task = asyncio.create_task(_safe_jackett(
        tracker_client, session,
        title_ru=title_ru if language == "ru" else "",
        title_en=title_en,
        year=year,
        imdb_id=imdb_id,
        language=language,
    ))
    fetcher_task = asyncio.create_task(
        _safe_web_fetcher(web_fetcher, primary_query)
    )
    archive_task = asyncio.create_task(
        _safe_archive_org(archive_org, archive_query, year)
    )

    if yts_enabled:
        yts_task = asyncio.create_task(
            _safe_yts(yts_client, session, primary_query, year)
        )
        (jackett_results, info), fetcher_results, archive_results, yts_results = (
            await asyncio.gather(
                jackett_task, fetcher_task, archive_task, yts_task
            )
        )
    else:
        (jackett_results, info), fetcher_results, archive_results = (
            await asyncio.gather(jackett_task, fetcher_task, archive_task)
        )
        yts_results = []

    log.info(
        "Поиск завершён: Jackett=%d, web_fetcher=%d, archive=%d, YTS=%d",
        len(jackett_results), len(fetcher_results),
        len(archive_results), len(yts_results),
    )

    combined_p2p = jackett_results + fetcher_results + yts_results
    filtered = filter_fn(combined_p2p, "combined")
    safe = [
        s for s in filtered
        if is_safe_release(s.get("title", ""), s.get("size", 0))
    ]
    safe = _enrich_magnets(safe)

    ranked = process_and_rank(safe, primary_query, year=year)
    unique_p2p = dedup_by_url(ranked)
    archive_unique = dedup_by_url(archive_results)
    unique = unique_p2p + archive_unique

    log.info("=" * 60)
    log.info("ИТОГ: %d источников (%s)",
             len(unique), _count_by_type(unique))

    if unique:
        p2p_only = [s for s in unique
                    if s.get("type") in ("magnet", "torrent_url")]
        direct_only = [s for s in unique if s.get("type") == "direct_url"]

        log.info("Топ-5 P2P:")
        for i, s in enumerate(p2p_only[:5], 1):
            log.info(
                "  [%d] %s seeders=%d size=%.1f MB indexer=%s title='%s'",
                i, s.get("type"), s.get("seeders", 0),
                (s.get("size", 0) or 0) / 1024 / 1024,
                s.get("indexer", "?"),
                (s.get("title") or "?")[:60],
            )

        log.info("=" * 60)
        return p2p_only + direct_only, ""

    log.warning("ИТОГ: пусто")
    log.info("=" * 60)
    return [], f"ПОТОК НЕ НАЙДЕН ({language.upper()})"
