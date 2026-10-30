"""Фильтр по языку: единый для RU и EN."""
import re

from core.logging_setup import get_logger

log = get_logger("aggregator.lang")

_RU_AUDIO_MARKERS = re.compile(
    r'\b(?:mvo|dvo|avo|pdo|dub|дубл|многоголос|одноголос|'
    r'лиценз|лицензия|профессиональн|русск|rus|ru)\b',
    re.IGNORECASE,
)


def cyrillic_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for c in letters if "\u0400" <= c <= "\u04FF")
    return cyr / len(letters)


def is_russian_release(title: str, indexer: str = "") -> bool:
    if not title:
        return False
    if _RU_AUDIO_MARKERS.search(title):
        return True
    if cyrillic_ratio(title) > 0.30:
        return True
    return False


def is_english_release(title: str) -> bool:
    if not title:
        return False
    if cyrillic_ratio(title) > 0.10:
        return False
    if _RU_AUDIO_MARKERS.search(title):
        return False
    return True


def filter_by_language(sources: list[dict], language: str) -> list[dict]:
    before = len(sources)
    if language == "ru":
        filtered = [s for s in sources if is_russian_release(s.get("title", ""))]
    else:
        filtered = [s for s in sources if is_english_release(s.get("title", ""))]
    if before != len(filtered):
        log.info("[%s] language filter: %d → %d",
                 language.upper(), before, len(filtered))
    return filtered