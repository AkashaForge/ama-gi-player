"""
Чтение пиесов с диска.

КРИТИЧНО: f.read() на 8 MB синхронный. На HDD — до 200ms блокировки
event loop. Читаем в отдельном thread pool через run_in_executor.
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

import asyncio
import os
import time

import config
from core.logging_setup import get_logger
from services.torrent.piece_map import PieceGeometry

log = get_logger("lt.reader")


class PieceReader:
    def __init__(self, geometry: PieceGeometry):
        self.geometry = geometry

    @staticmethod
    def _read_sync(file_path: str, start: int, size: int) -> bytes | None:
        try:
            with open(file_path, "rb") as f:
                f.seek(start)
                data = f.read(size)
            return data if len(data) == size else None
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def read_piece_from_file_sync(self, piece: int,
                                    file_path: str) -> bytes | None:
        """Синхронная версия — для обратной совместимости."""
        if not file_path or not os.path.exists(file_path):
            return None
        start, end = self.geometry.byte_range_for_piece(piece)
        if start < 0:
            return b""
        size = end - start
        if size <= 0:
            return b""

        retries = getattr(config, "STREAMING_FILE_READ_RETRY", 5)
        delay = getattr(config, "STREAMING_FILE_READ_RETRY_DELAY", 0.2)

        for attempt in range(retries):
            data = self._read_sync(file_path, start, size)
            if data is not None:
                return data
            time.sleep(delay)

        log.warning("read_piece(%d): не удалось прочитать %d байт",
                    piece, size)
        return None

    async def read_piece_from_file(self, piece: int,
                                     file_path: str) -> bytes | None:
        """Async: чтение в executor, не блокирует event loop."""
        if not file_path or not os.path.exists(file_path):
            return None
        start, end = self.geometry.byte_range_for_piece(piece)
        if start < 0:
            return b""
        size = end - start
        if size <= 0:
            return b""

        retries = getattr(config, "STREAMING_FILE_READ_RETRY", 5)
        delay = getattr(config, "STREAMING_FILE_READ_RETRY_DELAY", 0.2)
        loop = asyncio.get_event_loop()

        for attempt in range(retries):
            data = await loop.run_in_executor(
                None, self._read_sync, file_path, start, size
            )
            if data is not None:
                return data
            await asyncio.sleep(delay)

        log.warning("read_piece(%d): не удалось прочитать %d байт",
                    piece, size)
        return None
