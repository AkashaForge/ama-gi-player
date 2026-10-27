"""Утилиты."""

import re

_SPECIAL_CHARS_RE = re.compile(r'[:;,\'\"\!\(\)\[\]\{\}\<\>]')
_WHITESPACE_RE = re.compile(r'\s+')


def sanitize_query(query: str) -> str:
    if not query:
        return ""
    cleaned = _SPECIAL_CHARS_RE.sub(' ', str(query))
    return _WHITESPACE_RE.sub(' ', cleaned).strip()


def dedup_by_url(items) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(item)
    return out
