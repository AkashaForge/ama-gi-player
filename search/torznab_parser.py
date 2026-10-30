"""Парсер Torznab XML (ответ Jackett)."""

# Amagi-Player — desktop media player for public-domain content
# Copyright (C) 2026 AkashaForge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import re
from defusedxml import ElementTree

from search.filters import is_safe_release

_NS_RE = re.compile(r'xmlns="([^"]+)"')
_ITEM_RE = re.compile(r'<item[^>]*>.*?</item>', re.DOTALL)
_MAGNET_RE = re.compile(r'magnet:\?[^\s"\'<>]+')
_TORRENT_URL_RE = re.compile(
    r'https?://[^\s"\'<>]+(?:\.torrent|/dl/|/download/|/download\.php)[^\s"\'<>]*'
)
_SEEDERS_ATTR_RE = re.compile(r'name="seeders"\s+value="(\d+)"')
_SIZE_ATTR_RE = re.compile(r'name="size"\s+value="(\d+)"')
_INDEXER_ATTR_RE = re.compile(r'name="indexer"\s+value="([^"]+)"')

_MIN_SIZE_BYTES = 300 * 1024 * 1024


def _extract_seeders(item_node, prefix: str, raw_block: str) -> int:
    try:
        node = item_node.find(f"{prefix}seeders")
        if node is not None and node.text:
            return int(node.text)
    except (ValueError, AttributeError):
        pass
    m = _SEEDERS_ATTR_RE.search(raw_block)
    return int(m.group(1)) if m else 0


def _extract_size(item_node, prefix: str, raw_block: str) -> int:
    try:
        node = item_node.find(f"{prefix}size")
        if node is not None and node.text:
            return int(node.text)
    except (ValueError, AttributeError):
        pass
    m = _SIZE_ATTR_RE.search(raw_block)
    return int(m.group(1)) if m else 0


def _extract_indexer(item_node, prefix: str, ns: dict, raw_block: str) -> str:
    node = item_node.find(f"{prefix}jackettindexer", ns)
    if node is not None and node.text:
        return node.text.strip().lower()
    m = _INDEXER_ATTR_RE.search(raw_block)
    if m:
        return m.group(1).strip().lower()
    return ""


def _extract_url(item_node, prefix: str, ns: dict, raw_block: str):
    enc = item_node.find(f"{prefix}enclosure", ns)
    if enc is not None:
        u = (enc.get("url") or "").strip()
        if u.startswith("magnet:"):
            return "magnet", u
        if u.startswith(("http://", "https://")):
            return "torrent_url", u

    link = item_node.find(f"{prefix}link", ns)
    if link is not None and link.text:
        u = link.text.strip()
        if u.startswith("magnet:"):
            return "magnet", u
        if u.startswith(("http://", "https://")):
            return "torrent_url", u

    m = _MAGNET_RE.search(raw_block)
    if m:
        return "magnet", m.group(0)
    m = _TORRENT_URL_RE.search(raw_block)
    if m:
        return "torrent_url", m.group(0)
    return None, None


def parse_torznab_xml(raw_xml: str) -> list[dict]:
    if not raw_xml:
        return []

    ns_match = _NS_RE.search(raw_xml)
    ns = {"dns": ns_match.group(1)} if ns_match else {}
    prefix = "dns:" if ns else ""

    try:
        root = ElementTree.fromstring(raw_xml)
    except ElementTree.ParseError:
        return []

    raw_items = _ITEM_RE.findall(raw_xml)
    parsed: list[dict] = []

    for idx, item in enumerate(root.findall(f".//{prefix}item", ns)):
        title_node = item.find(f"{prefix}title", ns)
        title = title_node.text if title_node is not None else ""

        raw_block = raw_items[idx] if idx < len(raw_items) else ""

        size = _extract_size(item, prefix, raw_block)

        if not is_safe_release(title, size):
            continue

        kind, url = _extract_url(item, prefix, ns, raw_block)
        if not kind or not url:
            continue

        if size and size < _MIN_SIZE_BYTES:
            continue

        seeders = _extract_seeders(item, prefix, raw_block)
        indexer = _extract_indexer(item, prefix, ns, raw_block)

        parsed.append({
            "type": kind,
            "url": url,
            "title": title,
            "size": size,
            "seeders": seeders,
            "indexer": indexer,
        })

    return parsed
