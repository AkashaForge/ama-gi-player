"""
Планировщик пиесов через set_piece_deadline + piece_priority.

КРИТИЧНО:
  - set_piece_deadline(index, 0) = "no deadline" — НЕ работает!
    Дедлайн ДОЛЖЕН быть положительным (100ms минимум).
  - piece_priority(7) ставится явно — не надеемся на file_priority
    (при seek file_priority уже не влияет на новые пиесы).
"""

import config
from core.logging_setup import get_logger

log = get_logger("lt.piece_scheduler")


class PieceScheduler:
    def __init__(self, geometry):
        self.geometry = geometry
        self._current_piece = -1
        self._current_byte_pos = 0

        # deadline 0 = "no deadline" в libtorrent → заменяем на 100ms
        raw_head = getattr(
            config, "PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS", 100
        )
        self.DEADLINE_HEAD_MS = max(100, raw_head)
        self.LOOKAHEAD = getattr(
            config, "PIECE_SCHEDULER_LOOKAHEAD_PIECES", 10
        )
        self.DEADLINE_STEP_MS = getattr(
            config, "PIECE_SCHEDULER_DEADLINE_STEP_MS", 150
        )
        self.TRAILING_RETENTION = getattr(
            config, "PIECE_SCHEDULER_TRAILING_RETENTION", 3
        )
        self.TAIL_DEADLINE_MS = getattr(
            config, "PIECE_SCHEDULER_TAIL_DEADLINE_MS", 1000
        )
        self.PRIORITY_TOP = 7

    @property
    def current_piece(self) -> int:
        return self._current_piece

    @property
    def current_byte_pos(self) -> int:
        return self._current_byte_pos

    def _set_high_priority(self, piece: int, deadline_ms: int):
        """
        Ставит И piece_priority(7), И set_piece_deadline.
        Оба обязательны:
          - deadline без priority: libtorrent может игнорировать,
            если пиес далеко от очереди
          - priority без deadline: нет time-critical приоритизации
        """
        handle = self.geometry.handle
        if not handle or piece < 0 or piece >= self.geometry.num_pieces:
            return

        # 1. Явный high priority
        try:
            handle.piece_priority(piece, self.PRIORITY_TOP)
        except Exception as e:
            log.debug("piece_priority(%d): %s", piece, e)

        # 2. Positive deadline (100ms минимум — иначе "no deadline")
        if deadline_ms <= 0:
            deadline_ms = self.DEADLINE_HEAD_MS
        try:
            handle.set_piece_deadline(piece, deadline_ms)
        except Exception as e:
            log.debug("set_piece_deadline(%d, %d): %s",
                      piece, deadline_ms, e)

    def _apply_deadlines(self, start_piece: int):
        for i in range(self.LOOKAHEAD):
            p = start_piece + i
            if p >= self.geometry.num_pieces:
                break
            deadline = self.DEADLINE_HEAD_MS + i * self.DEADLINE_STEP_MS
            self._set_high_priority(p, deadline)
            log.debug("playhead: piece=%d deadline=%dms prio=7",
                      p, deadline)

    def on_position(self, byte_pos: int):
        if not self.geometry.handle:
            return
        piece = self.geometry.piece_for_byte(byte_pos)
        if piece < 0 or piece == self._current_piece:
            return

        self._current_piece = piece
        self._current_byte_pos = byte_pos
        self.geometry.current_piece = piece
        self._apply_deadlines(piece)

        # Trailing retention: пиесы ДО playhead тоже нужны
        # (FFmpeg может перечитать заголовок/Cues)
        for i in range(1, self.TRAILING_RETENTION + 1):
            p = piece - i
            if p >= 0:
                self._set_high_priority(p, self.TAIL_DEADLINE_MS)

    def on_seek(self, byte_pos: int):
        if not self.geometry.handle:
            return
        try:
            self.geometry.handle.clear_piece_deadlines()
        except Exception as e:
            log.debug("clear_piece_deadlines: %s", e)
        self._current_piece = -1
        self.on_position(byte_pos)

    def on_startup(self, first_piece: int, adaptive_count: int):
        if not self.geometry.handle:
            return
        try:
            self.geometry.handle.clear_piece_deadlines()
        except Exception:
            pass

        for i in range(adaptive_count):
            p = first_piece + i
            if p >= self.geometry.num_pieces:
                break
            deadline = self.DEADLINE_HEAD_MS + i * self.DEADLINE_STEP_MS
            self._set_high_priority(p, deadline)

        # Tail (moov-атом в MKV/MP4) — но с большим deadline
        for p in range(
            max(0, self.geometry.num_pieces - 3),
            self.geometry.num_pieces,
        ):
            self._set_high_priority(p, self.TAIL_DEADLINE_MS)
