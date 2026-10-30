"""Группировка magnet по info-hash + enrichment."""
import base64
import re

from core.logging_setup import get_logger
from services.torrent.tracker_balancer import DEFAULT_TRACKERS_FALLBACK

log = get_logger("lt.swarm_grouper")

_BTIH_RE = re.compile(r'btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})', re.IGNORECASE)
_TR_RE = re.compile(r'[?&]tr=([^&]+)')
_HASH_IN_URL_RE = re.compile(r'\b([a-fA-F0-9]{40})\b')
_TORRENT_URL_HINTS = (".torrent", "/download/", "/dl/", "/torrent/")


def extract_info_hash(url: str) -> str | None:
    if not url:
        return None
    if url.startswith("magnet:"):
        m = _BTIH_RE.search(url)
        if not m:
            return None
        raw = m.group(1)
        if len(raw) == 40:
            return raw.lower()
        try:
            return base64.b32decode(raw.upper()).hex()
        except Exception:
            return None
    low = url.lower()
    if any(h in low for h in _TORRENT_URL_HINTS):
        m = _HASH_IN_URL_RE.search(url)
        if m:
            return m.group(1).lower()
    return None


def extract_trackers(url: str) -> list[str]:
    if not url:
        return []
    return [tr for tr in _TR_RE.findall(url) if tr]


def _merge_trackers(existing: list[str], extra: list[str] | None) -> list[str]:
    seen = set(existing)
    out = list(existing)
    for t in (extra or []):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def enrich_magnet_with_default_trackers(
    url: str, extra_trackers: list[str] | None = None
) -> str:
    if not url or not url.startswith("magnet:"):
        return url
    existing = extract_trackers(url)
    if len(existing) >= 5 and not extra_trackers:
        return url
    pool = _merge_trackers(existing, extra_trackers or [])
    if len(pool) < 5:
        pool = _merge_trackers(pool, list(DEFAULT_TRACKERS_FALLBACK))
    existing_set = set(existing)
    new = [t for t in pool if t not in existing_set]
    if not new:
        return url
    return url + "".join(f"&tr={t}" for t in new)


def group_sources_by_hash(
    sources: list[dict], extra_trackers: list[str] | None = None
) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for s in sources:
        h = extract_info_hash(s.get("url", ""))
        if not h:
            groups.setdefault(f"__orphan_{id(s)}", []).append(s)
        else:
            groups.setdefault(h, []).append(s)

    multi = {h: srcs for h, srcs in groups.items()
             if not h.startswith("__") and len(srcs) > 1}
    if multi:
        log.info("Multi-swarm groups: %d", len(multi))
        for h, srcs in sorted(multi.items(),
                              key=lambda x: len(x[1]), reverse=True)[:5]:
            total = sum(s.get("seeders", 0) for s in srcs)
            trackers = set()
            for s in srcs:
                trackers.update(extract_trackers(s.get("url", "")))
            log.info("  hash=%s x%d, %d seeders, %d trackers",
                     h[:12], len(srcs), total, len(trackers))
    return groups


def merge_magnets_in_group(
    sources: list[dict], extra_trackers: list[str] | None = None
) -> str:
    if not sources:
        return ""
    base = ""
    for s in sources:
        u = s.get("url", "")
        if u.startswith("magnet:"):
            base = u
            break
    if not base:
        return sources[0].get("url", "")

    all_trackers = set()
    for s in sources:
        all_trackers.update(extract_trackers(s.get("url", "")))
    if extra_trackers:
        all_trackers.update(extra_trackers)
    if len(all_trackers) < 5:
        all_trackers.update(DEFAULT_TRACKERS_FALLBACK)

    existing = set(extract_trackers(base))
    new = all_trackers - existing
    if not new:
        return base
    return base + "".join(f"&tr={t}" for t in new)