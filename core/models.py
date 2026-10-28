"""Модели данных."""

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

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Source:
    type: str
    url: str
    title: str
    seeders: int = 0
    size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(
            type=d.get("type", "magnet"),
            url=d.get("url", ""),
            title=d.get("title", "Без названия"),
            seeders=int(d.get("seeders", 0) or 0),
            size=int(d.get("size", 0) or 0),
        )

    def is_valid(self) -> bool:
        return bool(self.url) and self.type in ("magnet", "torrent_url")
