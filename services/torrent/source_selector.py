"""SourceSelector v2.0.21 — композитный health score + жёсткий отсев экранок.

Компоненты скора:
  - health (сиды/пиры) — 30%
  - resolution (2160p/1080p/720p) — 25%
  - source (BluRay/WEB-DL/WEBRip/HDRip) — 20%
  - codec (HEVC/H.264) — 15%
  - trusted (YTS/VIP) — 10%

Жёсткий отсев: TELESYNC, CAM, TS, HDCAM, SCREENER — НИКОГДА не попадают в топ.
"""
import math
import re

import config
from core.logging_setup import get_logger
from search.filters import is_safe_release
from services.torrent.swarm_grouper import extract_info_hash

log = get_logger("lt.source_selector")

# Жёсткий отсев экранок — до скоринга
_HARD_REJECT_RE = re.compile(
    r'\b(?:camrip|cam-rip|hdcam|hdts|tsrip|ts-rip|telesync|'
    r'telecine|screener|scr|dvdscr)\b',
    re.IGNORECASE,
)


def _health_component(seeders: int, peers: int) -> float:
    """0..1 — насколько здоров торрент."""
    if seeders <= 0:
        return 0.0
    ratio = seeders / max(1, peers)
    norm_ratio = min(ratio / 5.0, 1.0)          # ratio >= 5 → 1.0
    norm_seeds = min(seeders / 200.0, 1.0)      # seeders >= 200 → 1.0
    return (norm_ratio * 0.4) + (norm_seeds * 0.6)


def _resolution_component(title: str) -> float:
    low = title.lower()
    if "2160p" in low or "4k" in low:
        return config.SCORE_BONUS_2160P
    if "1080p" in low:
        return config.SCORE_BONUS_1080P
    if "720p" in low:
        return config.SCORE_BONUS_720P
    return 0.0


def _source_component(title: str) -> float:
    low = title.lower()
    if "bluray" in low or "blu-ray" in low or "bdremux" in low:
        return config.SCORE_BONUS_BLURAY
    if "web-dl" in low or "webdl" in low:
        return config.SCORE_BONUS_WEB_DL
    if "webrip" in low or "web-rip" in low:
        return 0.05
    if "bdrip" in low or "brrip" in low:
        return 0.05
    if "hdrip" in low:
        return -0.05
    return 0.0


def _codec_component(title: str) -> float:
    low = title.lower()
    if "hevc" in low or "h265" in low or "x265" in low:
        return config.SCORE_BONUS_HEVC
    if "h264" in low or "x264" in low or "avc" in low:
        return 0.0
    return 0.0


def _trusted_component(source: dict) -> float:
    """YTS и известные загрузчики — небольшой бонус."""
    indexer = (source.get("indexer") or "").lower()
    if indexer in ("yts", "rarbg", "eztv", "torrentapi"):
        return 0.10
    return 0.0


def _is_hard_reject(title: str, size: int) -> bool:
    if not title:
        return True
    if _HARD_REJECT_RE.search(title):
        return True
    if not is_safe_release(title, size):
        return True
    return False


class SourceSelector:
    def __init__(self, year: str = "", language: str = ""):
        self.year = (year or "").strip()
        self.language = (language or "").strip().lower()

    def _score(self, source: dict) -> float:
        title = source.get("title", "") or ""
        seeders = source.get("seeders", 0) or 0
        peers = source.get("leechers", 0) or 0

        health = _health_component(seeders, peers)
        res = _resolution_component(title)
        src = _source_component(title)
        codec = _codec_component(title)
        trusted = _trusted_component(source)

        score = (
            health * config.SCORE_WEIGHT_HEALTH
            + res * config.SCORE_WEIGHT_RESOLUTION
            + src * config.SCORE_WEIGHT_SOURCE
            + codec * config.SCORE_WEIGHT_CODEC
            + trusted * config.SCORE_WEIGHT_TRUSTED
        )

        # Штрафы за экранки (на случай, если regex не сработал)
        low = title.lower()
        if "telesync" in low:
            score += config.SCORE_PENALTY_TELESYNC
        if "cam" in low:
            score += config.SCORE_PENALTY_CAM
        if "ts" in low and "telesync" not in low:
            score += config.SCORE_PENALTY_TS
        if "screener" in low or "dvdscr" in low:
            score += config.SCORE_PENALTY_SCREENER

        return round(score, 4)

    def rank(self, sources: list[dict]) -> list[dict]:
        valid = []
        rejected = 0
        for s in sources:
            title = s.get("title", "") or ""
            size = s.get("size", 0) or 0
            if _is_hard_reject(title, size):
                rejected += 1
                continue
            s["_score"] = self._score(s)
            valid.append(s)

        if rejected:
            log.info("[selector] rejected (hard): %d", rejected)

        valid.sort(key=lambda x: x.get("_score", 0), reverse=True)

        log.info("[selector] %d valid (composite health)", len(valid))
        for i, s in enumerate(valid[:15], 1):
            h = extract_info_hash(s.get("url", "")) or "?"
            size = s.get("size", 0) or 0
            log.info(
                "  [%d] score=%.4f seeders=%d peers=%d size=%s hash=%s: %s",
                i, s["_score"], s.get("seeders", 0),
                s.get("leechers", 0),
                f"{size/1024/1024:.1f}MB" if size else "?",
                h[:12] if h != "?" else "?",
                (s.get("title") or "")[:50],
            )
        return valid

    def select(self, sources: list[dict]) -> tuple[dict | None, list[dict]]:
        ranked = self.rank(sources)
        if not ranked:
            log.warning("[selector] no valid sources")
            return None, []
        limit = config.SOURCE_SELECTOR_MAX_ALTERNATIVES
        return ranked[0], ranked[1:1 + limit]