"""
Группировка magnet-источников по info-hash для multi-swarm.

Один и тот же файл может быть на разных сервисах — у всех одинаковый info-hash. Объединение даёт пиров
со всех трекеров в один swarm.

Также обогащает magnet-ссылки дефолтными публичными trackers, если
в исходной ссылке их < 5.
"""

import base64
import re

from core.logging_setup import get_logger

log = get_logger("lt.swarm_grouper")


_BTIH_RE = re.compile(r'btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})', re.IGNORECASE)
_TR_RE = re.compile(r'[?&]tr=([^&]+)')


# Публичные трекеры, которые работают в 2024-2026
DEFAULT_TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.coppersurfer.tk:6969/announce",
    "udp://tracker.leechers-paradise.org:6969/announce",
)


def extract_info_hash(url: str) -> str | None:
    """
    Извлекает info-hash из magnet-ссылки.
    Возвращает hex (40 символов) или None.
    """
    if not url or not url.startswith("magnet:"):
        return None
    m = _BTIH_RE.search(url)
    if not m:
        return None
    raw = m.group(1)
    if len(raw) == 40:
        return raw.lower()
    try:
        decoded = base64.b32decode(raw.upper())
        return decoded.hex()
    except Exception:
        return None


def extract_trackers(url: str) -> list[str]:
    """Извлекает список trackers (tr=...) из magnet-ссылки."""
    if not url:
        return []
    return [tr for tr in _TR_RE.findall(url) if tr]


def enrich_magnet_with_default_trackers(url: str) -> str:
    """
    Добавляет дефолтные трекеры к magnet, если их меньше 5.
    """
    if not url or not url.startswith("magnet:"):
        return url

    existing = extract_trackers(url)
    if len(existing) >= 5:
        return url

    existing_set = set(existing)
    new_tr = [tr for tr in DEFAULT_TRACKERS if tr not in existing_set]
    if not new_tr:
        return url

    tr_str = "".join(f"&tr={tr}" for tr in new_tr)
    return url + tr_str


def group_sources_by_hash(sources: list[dict]) -> dict[str, list[dict]]:
    """
    Группирует источники по info-hash.

    Источники без info-hash (torrent_url, magnet без btih) — идут в отдельные
    группы со специальным ключом "__orphan_N".

    Возвращает: {info_hash: [source, source, ...]}
    """
    groups: dict[str, list[dict]] = {}

    for s in sources:
        url = s.get("url", "")
        h = extract_info_hash(url)

        if not h:
            key = f"__orphan_{id(s)}"
            groups.setdefault(key, []).append(s)
            continue

        groups.setdefault(h, []).append(s)

    # Логируем группы с > 1 источником (это и есть multi-swarm)
    multi = {h: srcs for h, srcs in groups.items()
             if not h.startswith("__") and len(srcs) > 1}
    if multi:
        log.info("Multi-swarm groups: %d", len(multi))
        for h, srcs in sorted(multi.items(),
                              key=lambda x: len(x[1]), reverse=True)[:5]:
            total_seeders = sum(s.get("seeders", 0) for s in srcs)
            trackers = set()
            for s in srcs:
                trackers.update(extract_trackers(s.get("url", "")))
            log.info(
                "  hash=%s... x%d sources, %d seeders суммарно, "
                "%d unique trackers",
                h[:12], len(srcs), total_seeders, len(trackers),
            )

    return groups


def merge_magnets_in_group(sources: list[dict]) -> str:
    """
    Объединяет все magnet-ссылки в группе в одну с расширенным списком
    trackers. Берёт magnet из первого источника, добавляет trackers
    из остальных + дефолтные если их всё ещё < 5.
    """
    if not sources:
        return ""

    base = sources[0].get("url", "")
    if not base.startswith("magnet:"):
        return base

    all_trackers = set()
    for s in sources:
        all_trackers.update(extract_trackers(s.get("url", "")))

    # Если после объединения трекеров всё ещё < 5 — добавляем дефолтные
    if len(all_trackers) < 5:
        all_trackers.update(DEFAULT_TRACKERS)

    existing = set(extract_trackers(base))
    new_trackers = all_trackers - existing
    if not new_trackers:
        return base

    tr_str = "".join(f"&tr={tr}" for tr in new_trackers)
    return base + tr_str
