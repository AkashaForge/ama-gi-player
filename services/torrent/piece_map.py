"""Геометрия пиесов."""

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

log = get_logger("lt.piecemap")


class PieceGeometry:
    def __init__(self):
        self.handle = None
        self.file_idx = -1
        self.file_size = 0
        self.piece_length = 0
        self.num_pieces = 0
        self.file_offset_in_torrent = 0
        self.current_piece = -1

    def configure(self, handle, file_idx: int, file_size: int,
                  piece_length: int, num_pieces: int,
                  file_offset_in_torrent: int):
        self.handle = handle
        self.file_idx = file_idx
        self.file_size = file_size
        self.piece_length = piece_length
        self.num_pieces = num_pieces
        self.file_offset_in_torrent = file_offset_in_torrent
        self.current_piece = -1

    def piece_for_byte(self, byte_pos: int) -> int:
        if not self.handle:
            return -1
        try:
            return self.handle.torrent_file().map_file(
                self.file_idx, byte_pos, 1
            ).piece
        except Exception:
            return -1

    def byte_range_for_piece(self, piece: int) -> tuple[int, int]:
        piece_start_in_torrent = piece * self.piece_length
        piece_end_in_torrent = piece_start_in_torrent + self.piece_length
        file_start_in_torrent = self.file_offset_in_torrent
        file_end_in_torrent = self.file_offset_in_torrent + self.file_size

        overlap_start = max(piece_start_in_torrent, file_start_in_torrent)
        overlap_end = min(piece_end_in_torrent, file_end_in_torrent)

        if overlap_start >= overlap_end:
            return -1, -1

        return (
            overlap_start - self.file_offset_in_torrent,
            overlap_end - self.file_offset_in_torrent,
        )

    def have_piece(self, piece: int) -> bool:
        if not self.handle:
            return False
        try:
            return bool(self.handle.have_piece(piece))
        except Exception:
            return False
