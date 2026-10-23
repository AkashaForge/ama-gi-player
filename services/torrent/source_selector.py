"""
Выбор источника по композитному скору.

Изменения:
  - Штраф -30 применяется не только к magnet без metadata, но и к
    torrent_url, если у него seeders=0 и size=0. Такие torrent_url
    обычно дают redirect на magnet — реальный size неизвестен.
    Это отсеивает мёртвые .torrent-ссылки из топа.
"""

import config
from core.logging_setup import get_logger
from search.filters import (
    extract_year,
    is_collection,
    is_safe_release,
    year_close,
)
from services.torrent.swarm_grouper import extract_info_hash

log = get_logger("lt.source_selector")

REALLY_BAD = -100.0


class SourceSelector:
    NO_META_PENALTY = 30           # seeders=0 AND size=0 (magnet или torrent_url)
    NO_SEEDERS_PENALTY = 15        # seeders=0, size>0
    HUGE_SIZE_PENALTY = 25
    TORRENT_URL_BONUS = 10
    WRONG_YEAR_PENALTY = 15

    def __init__(self, year: str = ""):
        self.year = (year or "").strip()

    def _quality_score(self, title: str) -> int:
        low = title.lower()
        if "2160p" in low or "4k" in low:
            return 10
        if "1080p" in low:
            return 20
        if "720p" in low:
            return 15
        return 0

    def _size_penalty(self, size: int) -> float:
        gb = (size or 0) / 1024 ** 3
        penalty = gb * getattr(config, "SOURCE_SELECTOR_SIZE_PENALTY_GB", 0.5)
        if gb > 15.0:
            penalty += self.HUGE_SIZE_PENALTY
        return penalty

    def score(self, source: dict) -> float:
        title = source.get("title", "") or ""
        seeders = source.get("seeders", 0) or 0
        size = source.get("size", 0) or 0
        src_type = (source.get("type") or "").lower()

        if not is_safe_release(title, size):
            return REALLY_BAD

        if self.year and is_collection(title):
            return REALLY_BAD

        year_penalty = 0
        if self.year:
            ty = extract_year(title)
            if ty and not year_close(
                [ty], self.year,
                tolerance=getattr(config, "SEARCH_YEAR_TOLERANCE", 1),
            ):
                year_penalty = self.WRONG_YEAR_PENALTY

        base = seeders + self._quality_score(title) - self._size_penalty(size)

        if src_type == "torrent_url":
            base += self.TORRENT_URL_BONUS

        # === УНИВЕРСАЛЬНЫЙ штраф за seeders=0 и size=0 (для ОБОИХ типов) ===
        # Это отсеивает мёртвые .torrent-ссылки и magnet без metadata.
        if seeders == 0 and size == 0:
            base -= self.NO_META_PENALTY
        elif seeders == 0:
            base -= self.NO_SEEDERS_PENALTY

        return base - year_penalty

    def select(self, sources: list[dict]) -> tuple[dict | None, list[dict]]:
        scored = []
        for s in sources:
            sc = self.score(s)
            if sc <= REALLY_BAD:
                continue
            scored.append((sc, s))

        if not scored:
            log.warning("[selector] все источники отклонены")
            return None, []

        scored.sort(key=lambda x: x[0], reverse=True)
        final_ranked = [s for _, s in scored]

        top = final_ranked[0]
        log.info(
            "[selector] %d sources. Top: '%s' (score=%.1f, type=%s, "
            "seeders=%d, size=%.1f MB)",
            len(final_ranked),
            (top.get("title") or "")[:60],
            scored[0][0], top.get("type", "?"),
            top.get("seeders", 0),
            (top.get("size", 0) or 0) / 1024 / 1024,
        )
        for i, (sc, s) in enumerate(scored[:8], 1):
            h = extract_info_hash(s.get("url", "")) or "?"
            log.info(
                "  [%d] score=%.1f type=%s seeders=%d size=%.1fMB "
                "hash=%s: %s",
                i, sc, s.get("type", "?"), s.get("seeders", 0),
                (s.get("size", 0) or 0) / 1024 / 1024,
                (h[:12] if h != "?" else "?"),
                (s.get("title") or "")[:55],
            )

        limit = getattr(config, "SOURCE_SELECTOR_MAX_ALTERNATIVES", 15)
        return final_ranked[0], final_ranked[1:1 + limit]
