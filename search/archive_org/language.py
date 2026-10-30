"""Language scoring для Internet Archive."""

_PREFERRED_EN_MATCH = ("english", "eng", "american", "british", "usa", "uk")
_PREFERRED_RU_MATCH = ("russian", "rus", "soviet", "ussr")
_EN_OTHER_LANGS = (
    "russian", "rus", "german", "ger", "french", "fre", "polish", "pol",
    "czech", "cze", "czechoslovak", "spanish", "spa", "italian", "ita",
    "japanese", "jpn", "chinese", "chi", "portuguese", "por", "dutch", "dut",
    "swedish", "swe", "danish", "dan", "norwegian", "nor", "finnish", "fin",
    "hungarian", "hun", "romanian", "rum", "greek", "gre", "turkish", "tur",
    "hebrew", "heb", "arabic", "ara", "hindi", "hin", "korean", "kor",
)


def lang_score(actual: str, preferred: str) -> float:
    """0.0 — явно чужой, 0.5 — нейтрально, 1.0 — совпал."""
    if not actual:
        return 0.5
    a = actual.lower().strip()
    if "silent" in a:
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
    q_words = [w for w in query.lower().split() if len(w) >= 3]
    if not q_words:
        return 0.5
    target = (identifier + " " + title).lower()
    matched = sum(1 for w in q_words if w in target)
    return matched / len(q_words)