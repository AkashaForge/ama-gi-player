"""Утилиты."""

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
