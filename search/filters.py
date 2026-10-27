"""Фильтры безопасности и ранжирование релизов."""

import re

import config
from core.logging_setup import get_logger

log = get_logger("filters")


_VIDEO_MARKERS = frozenset({
    "bdrip", "web-dl", "webdl", "webrip", "hdtv", "dvdrip", "bluray",
    "blu-ray", "bdremux", "remux", "hdrip", "camrip", "x264", "x265",
    "h264", "h265", "hevc", "1080p", "720p", "2160p", "4k",
})

_RUS_MARKERS = frozenset({
    "rus", "дубл", "лиценз", "многоголос", "одноголос", "avo", "mvo", "dub",
})

_AUDIO_BOOK_MARKERS = frozenset({
    "аудиокниг", "audiobook", "mp3 audiobook", "flac audiobook", "комикс",
})

_FAKE_MARKERS = frozenset({
    "смотреть онлайн", "бесплатно", "онлайн кинотеатр",
})

_COLLECTION_MARKERS = frozenset({
    "трилоги", "trilogy", "collection", "complete", "антологи",
    "quadrilogy", "tetralogy", "сборник", "boxset", "pentalogy",
    "quadrology", "квадрологи", "тетралоги", "пенталоги",
})

# Паттерны сборников: "1 4 Pack", "1-4", "1-3", "1 2 3", "4 in 1",
# "2 movies collection", "pack of 3" и т.д.
_COLLECTION_PATTERNS = (
    re.compile(r'\b\d\s*[-–]\s*\d\s*(pack|in\s*one|movies?|films?|collection)\b',
               re.IGNORECASE),
    re.compile(r'\b\d\s+\d\s+(pack|in\s*one|movies?|films?)\b',
               re.IGNORECASE),
    re.compile(r'\b\d\s+\d\s+\d\s+\d\b', re.IGNORECASE),  # "1 2 3 4"
    re.compile(r'\b\d+\s*(movies?|films?)\s*(pack|collection|box|set)\b',
               re.IGNORECASE),
    re.compile(r'\b(pack|box|set)\s+of\s+\d+\b', re.IGNORECASE),
    re.compile(r'\b(all\s+\d+\s+(movies?|films?))\b', re.IGNORECASE),
)

_STOP_WORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "и", "в", "на", "с", "по", "из", "от", "до", "для", "или",
})

_MIN_SIZE_BYTES = 300 * 1024 * 1024
_YEAR_RE = re.compile(r'\b(19\d{2}|20\d{2}|21\d{2})\b')


# Негативные маркеры — то, что 100% НЕ фильм
_NEGATIVE_MARKERS = frozenset({
    # Игры
    "игр", "game", "pc game", "ps4", "ps5", "xbox", "nintendo",
    "steam", "repack game", "iso образ",
    # Софт
    "software", "программ", "windows", "photoshop", "office",
    "adobe", "microsoft", "exe",
    # Музыка
    "mp3", "flac", "lossless", "album", "дискография",
    "сборник песен", "music collection",
    # Аудиокниги
    "аудиокниг", "audiobook", "mp3 audiobook", "flac audiobook",
    # Книги
    "pdf", "epub", "fb2", "книга", "book",
    # Обучение
    "курс", "course", "уроки", "обучение", "tutorial",
    # Мусор
    "смотреть онлайн", "бесплатно", "онлайн кинотеатр",
    "комикс", "comic",
})


def is_safe_release(title: str, size: int = 0) -> bool:
    """
    Либиральный фильтр на уровне aggregator.

    Строгая проверка "это видео?" происходит в StreamSession._pick_video_file,
    где уже есть метадата (список файлов с расширениями).

    Здесь мы отбрасываем только 100%-й мусор:
      - игры, софт, музыка, аудиокниги, книги
      - фейковые "смотреть онлайн"
      - файлы < 300 MB (если размер известен)
    """
    if not title:
        return False

    low = title.lower()

    # Явный мусор — отбросить сразу
    if any(m in low for m in _NEGATIVE_MARKERS):
        return False

    # Если размер известен и < 300 MB — это не фильм
    if size and size < 300 * 1024 * 1024:
        return False

    # Всё остальное — пропускаем.
    # Если это магнет без metadata (size=0) — StreamSession сам
    # отбросит после получения списка файлов, если внутри нет видео.
    return True
def has_russian_marker(title: str) -> bool:
    if not title:
        return False
    low = title.lower()
    return any(m in low for m in _RUS_MARKERS)


def _is_collection(title: str) -> bool:
    """
    Определяет сборники/трилогии/квадрологии.
    Покрывает:
      - маркеры: trilogy, collection, complete, boxset, трилоги, etc.
      - паттерны: "1 4 Pack", "1-4", "1 2 3 4", "4 movies collection", etc.
    """
    if not title:
        return False
    low = title.lower()
    if any(m in low for m in _COLLECTION_MARKERS):
        return True
    for pat in _COLLECTION_PATTERNS:
        if pat.search(low):
            return True
    return False


def _extract_query_words(query: str) -> list[str]:
    raw = re.findall(r'\w+', (query or "").lower())
    significant = [w for w in raw if len(w) >= 3 and w not in _STOP_WORDS]
    if significant:
        return significant
    return [w for w in raw if len(w) >= 2]


def _extract_year(query: str) -> str | None:
    m = _YEAR_RE.search(query or "")
    return m.group(1) if m else None


def _min_matches_for(n: int) -> int:
    if n <= 0:
        return 0
    if n == 1:
        return 1
    if n == 2:
        return 2
    ratio = getattr(config, "SEARCH_MIN_MATCHES_RATIO", 0.6)
    return max(2, int(n * ratio + 0.999))


def _year_close(title_years: list[str], query_year: str,
                tolerance: int) -> bool:
    if not title_years or not query_year:
        return False
    try:
        qy = int(query_year)
        return any(abs(int(y) - qy) <= tolerance for y in title_years)
    except ValueError:
        return False


def process_and_rank(releases: list[dict], query: str,
                     year: str = "") -> list[dict]:
    if not releases:
        return []

    q_words = _extract_query_words(query)
    if not q_words:
        return list(releases)

    query_year = (year or "").strip() or _extract_year(query)
    min_matches = _min_matches_for(len(q_words))
    query_low = (query or "").lower().strip()

    year_tolerance = getattr(config, "SEARCH_YEAR_TOLERANCE", 1)
    year_bonus_val = getattr(config, "SEARCH_YEAR_MATCH_BONUS", 20)
    exact_bonus_val = getattr(config, "SEARCH_EXACT_QUERY_BONUS", 30)
    seeders_div = getattr(config, "SEARCH_SEEDERS_DIVISOR", 10)
    max_results = getattr(config, "SEARCH_MAX_RESULTS", 50)
    reject_collections = getattr(
        config, "SEARCH_REJECT_COLLECTIONS_IF_YEAR", True
    )

    log.info(
        "rank: query='%s' year='%s' words=%d min_matches=%d input=%d",
        query, query_year or "-", len(q_words), min_matches, len(releases),
    )

    scored: list[tuple[int, dict]] = []
    rejected_by_year = 0
    rejected_by_collection = 0
    rejected_by_matches = 0
    rejected_by_size = 0

    for r in releases:
        title = r.get("title", "") or ""
        size = r.get("size", 0) or 0
        if not is_safe_release(title, size):
            rejected_by_size += 1
            continue
        low = title.lower()

        matches = sum(1 for w in q_words if w in low)
        if matches < min_matches:
            rejected_by_matches += 1
            continue

        # Коллекции reject'им ДО проверки года
        if query_year and reject_collections and _is_collection(title):
            if rejected_by_collection < 5:
                log.info("[rank] reject collection: '%s'", title[:70])
            rejected_by_collection += 1
            continue

        year_bonus = 0
        if query_year:
            title_years = _YEAR_RE.findall(title)
            if title_years:
                if not _year_close(title_years, query_year, year_tolerance):
                    if rejected_by_year < 5:
                        log.info(
                            "[rank] reject by year: q_year=%s "
                            "title_years=%s title='%s'",
                            query_year, title_years, title[:70],
                        )
                    rejected_by_year += 1
                    continue
                year_bonus = year_bonus_val

        exact_bonus = 0
        if query_low and query_low in low:
            exact_bonus = exact_bonus_val

        seeders = r.get("seeders", 0) or 0
        seed_bonus = seeders // seeders_div if seeders_div > 0 else 0

        score = matches * 10 + year_bonus + exact_bonus + seed_bonus
        scored.append((score, r))

    scored.sort(key=lambda p: p[0], reverse=True)

    log.info(
        "rank result: passed=%d rejected[year=%d, collection=%d, "
        "matches=%d, unsafe/size=%d]",
        len(scored), rejected_by_year, rejected_by_collection,
        rejected_by_matches, rejected_by_size,
    )

    return [r for _, r in scored[:max_results]]


# Public aliases
extract_year = _extract_year
year_close = _year_close
is_collection = _is_collection
