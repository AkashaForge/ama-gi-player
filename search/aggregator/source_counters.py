"""Счётчики и enrichment магнитов."""
from core.logging_setup import get_logger
from services.torrent.swarm_grouper import enrich_magnet_with_default_trackers

log = get_logger("aggregator.counters")


def count_by_type(sources: list[dict]) -> str:
    mag = sum(1 for s in sources if s.get("type") == "magnet")
    tor = sum(1 for s in sources if s.get("type") == "torrent_url")
    dr = sum(1 for s in sources if s.get("type") == "direct_url")
    return f"magnet={mag} torrent_url={tor} direct_url={dr}"


def enrich_magnets(sources: list[dict],
                     extra_trackers: list[str] | None = None) -> list[dict]:
    out = []
    count = 0
    for s in sources:
        if s.get("type") == "magnet":
            old = s.get("url", "")
            new = enrich_magnet_with_default_trackers(old, extra_trackers)
            if new != old:
                count += 1
                s = dict(s)
                s["url"] = new
        out.append(s)
    if count:
        log.info("Enriched %d magnets", count)
    return out