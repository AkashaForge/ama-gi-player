"""
Состояние одного HTTP Range-запроса.

Каждый новый запрос создаёт новый StreamRequestState. Старые запросы
не влияют на is_buffering для UI — они уже superseded.
"""

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

import time
from dataclasses import dataclass, field


@dataclass
class StreamRequestState:
    request_id: int
    started_at: float = field(default_factory=time.time)
    is_buffering: bool = False
    buffering_since: float | None = None
    current_piece: int = -1
    bytes_served: int = 0

    def set_buffering(self, value: bool) -> None:
        if value and not self.is_buffering:
            self.buffering_since = time.time()
        elif not value and self.is_buffering:
            self.buffering_since = None
        self.is_buffering = value

    def buffering_duration(self) -> float:
        if self.buffering_since is None:
            return 0.0
        return time.time() - self.buffering_since

    def note_piece(self, piece: int) -> None:
        self.current_piece = piece
