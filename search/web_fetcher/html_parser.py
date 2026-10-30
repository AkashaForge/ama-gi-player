"""Парсинг HTML: магниты и .torrent-ссылки."""
import re
from urllib.parse import urljoin

_MAGNET_RE = re.compile(r'magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\'<>\s]*')
_TORRENT_LINK_RE = re.compile(
    r'href=["\']([^"\']*(?:/download/|dl\.php\?t=|/torrent/|\.torrent)[^"\']*)["\']',
    re.IGNORECASE,
)
_MAGNET_IN_HREF_RE = re.compile(r'magnet:\?', re.IGNORECASE)
_HTML_ENTITY_RE = re.compile(r'&[a-z]+;')
_WHITESPACE_RE = re.compile(r'\s+')
_TITLE_RE = re.compile(
    r'<a[^>]+href="[^"]*(?:viewtopic|/torrent/|details\.php)[^"]*"[^>]*>'
    r'([^<]{5,300})</a>',
    re.IGNORECASE,
)
_TITLE_FALLBACK_RE = re.compile(r'<a[^>]*>([^<]{5,300})</a>', re.IGNORECASE)
_SEEDERS_RE = re.compile(
    r'class="(?:seedmed|green|seeders?|s|seed)"[^>]*>\s*(\d+)\s*<',
    re.IGNORECASE,
)


def _extract_title(html: str, pos: int) -> str:
    start = max(0, pos - 800)
    context = html[start:pos]
    for pat in (_TITLE_RE, _TITLE_FALLBACK_RE):
        m = pat.search(context)
        if m:
            title = _HTML_ENTITY_RE.sub(' ', m.group(1).strip())
            return _WHITESPACE_RE.sub(' ', title).strip() or "Без названия"
    return "Без названия"


def _extract_seeders(html: str, pos: int) -> int:
    m = _SEEDERS_RE.search(html[pos:pos + 1200])
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 0


def extract_from_html(html: str, base_url: str = "") -> list[dict]:
    if not html:
        return []
    results = []
    seen = set()

    for m in _MAGNET_RE.finditer(html):
        url = m.group(0)
        if url in seen:
            continue
        seen.add(url)
        results.append({
            "type": "magnet",
            "url": url,
            "title": _extract_title(html, m.start()),
            "seeders": _extract_seeders(html, m.start()),
        })

    for m in _TORRENT_LINK_RE.finditer(html):
        href = m.group(1).strip()
        if not href or _MAGNET_IN_HREF_RE.search(href):
            continue
        low = href.lower()
        if any(low.endswith(ext) for ext in (
            '.jpg', '.jpeg', '.png', '.gif', '.css', '.js',
            '.ico', '.svg', '.webp',
        )):
            continue
        if not href.startswith(('http://', 'https://')):
            if not base_url:
                continue
            href = urljoin(base_url, href)
        if href in seen:
            continue
        seen.add(href)
        results.append({
            "type": "torrent_url",
            "url": href,
            "title": _extract_title(html, m.start()),
            "seeders": _extract_seeders(html, m.start()),
        })
    return results


def extract_magnets_from_html(html: str) -> list[dict]:
    return [r for r in extract_from_html(html) if r["type"] == "magnet"]