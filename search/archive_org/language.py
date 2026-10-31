"""Language scoring для Internet Archive."""

_PREFERRED_EN_MATCH = ("english", "eng", "american", "british", "usa", "uk", "silent")
_PREFERRED_RU_MATCH = ("russian", "rus", "soviet", "ussr", "silent")
_EN_OTHER_LANGS = (
    "russian", "rus", "german", "ger", "french", "fre", "polish", "pol",
    "czech", "cze", "czechoslovak", "spanish", "spa", "italian", "ita",
    "japanese", "jpn", "chinese", "chi", "portuguese", "por", "dutch", "dut",
    "swedish", "swe", "danish", "dan", "norwegian", "nor", "finnish", "fin",
    "hungarian", "hun", "romanian", "rum", "greek", "gre", "turkish", "tur",
    "hebrew", "heb", "arabic", "ara", "hindi", "hin", "korean", "kor",
)

_STOPWORDS = frozenset({
    "the", "and", "of", "a", "an", "in", "on", "for", "with", "to", "by",
})


def lang_score(actual: str, preferred: str, year: str = "") -> float:
    """0.0 — явно чужой, 0.5 — нейтрально, 1.0 — совпал.

    Для немого кино (year < 1930) язык не важен: на IA такие фильмы
    часто записаны с языком титров (Russian/German/French), а не
    оригинальным. Возвращаем 0.9, чтобы фильм не отсеивался.
    """
    try:
        y = int(year)
        if y and y < 1930:
            return 0.9
    except (ValueError, TypeError):
        pass

    if not actual:
        return 0.5
    a = actual.lower().strip()

    if "silent" in a:
        return 0.9
    if "no linguistic" in a or "no dialogue" in a or "music only" in a:
        return 0.9

    if preferred == "en":
        if any(x in a for x in _PREFERRED_EN_MATCH):
            return 1.0
        if any(x in a for x in _EN_OTHER_LANGS):
            return 0.0
        return 0.5

    if preferred == "ru":
        if any(x in a for x in _PREFERRED_RU_MATCH):
            return 1.0
        if any(x in a for x in _EN_OTHER_LANGS):
            return 0.0
        return 0.5

    return 0.5


def title_score(identifier: str, title: str, query: str) -> float:
    """Доля слов запроса, найденных в identifier+title.

    Стоп-слова ("the", "and", "of") не считаются — иначе для запроса
    "The Fatal Mallet" из 3 слов 2 оказываются значимыми, и любой фильм
    с "Fatal" в названии получает 0.66 вместо правильной оценки.
    """
    q_words = [
        w for w in query.lower().split()
        if len(w) >= 3 and w not in _STOPWORDS
    ]
    if not q_words:
        # Все слова были стоп-словами — используем их без фильтра
        q_words = [w for w in query.lower().split() if len(w) >= 2]
    if not q_words:
        return 0.5
    target = (identifier + " " + title).lower()
    matched = sum(1 for w in q_words if w in target)
    return matched / len(q_words)