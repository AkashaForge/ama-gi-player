"""
Трекинг активных (приоритезированных) пиесов.

Позволяет сбрасывать приоритеты за O(active), а не за O(num_pieces).
При seek не нужно обходить 7000+ пиесов — только те, что были активны.
"""

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
