"""
Трекинг активных (приоритезированных) пиесов.

Позволяет сбрасывать приоритеты за O(active), а не за O(num_pieces).
При seek не нужно обходить 7000+ пиесов — только те, что были активны.
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

from core.logging_setup import get_logger

log = get_logger("lt.piece_state")


class PieceStateTracker:
    def __init__(self, geometry):
        self.geometry = geometry
        self._active: set[int] = set()

    def track(self, piece: int) -> None:
        if 0 <= piece < self.geometry.num_pieces:
            self._active.add(piece)

    def untrack(self, piece: int) -> None:
        self._active.discard(piece)

    def set_priority(self, piece: int, priority: int) -> None:
        """Установить приоритет и учесть в трекере."""
        handle = self.geometry.handle
        if not handle or piece < 0 or piece >= self.geometry.num_pieces:
            return
        try:
            handle.piece_priority(piece, priority)
        except Exception:
            return
        if priority > 0:
            self._active.add(piece)
        else:
            self._active.discard(piece)

    def reset_all_active(self) -> int:
        """
        Сбросить приоритеты у всех АКТИВНЫХ пиесов.
        Возвращает число сброшенных.
        Быстро: O(len(active)), не O(num_pieces).
        """
        handle = self.geometry.handle
        if not handle:
            return 0
        count = 0
        # Копируем, т.к. во время итерации модифицируем set.
        for p in list(self._active):
            try:
                handle.piece_priority(p, 0)
                count += 1
            except Exception:
                pass
        self._active.clear()
        return count

    def apply(self, start: int, end: int, priority: int) -> None:
        for p in range(max(0, start), min(self.geometry.num_pieces, end)):
            self.set_priority(p, priority)

    @property
    def active_count(self) -> int:
        return len(self._active)
