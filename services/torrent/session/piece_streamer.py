"""PieceStreamer — чтение пиесов через read_piece_alert + fallback на файл."""
import asyncio
import time

import config
from core.logging_setup import get_logger
from services.torrent.piece_map import PieceGeometry
from services.torrent.piece_scheduler import PieceScheduler

log = get_logger("lt.session.piece_streamer")


class PieceStreamer:
    def __init__(self, geometry: PieceGeometry,
                 scheduler: PieceScheduler,
                 handle_getter,
                 file_path_getter):
        self.geometry = geometry
        self.scheduler = scheduler
        self._handle_getter = handle_getter
        self._file_path_getter = file_path_getter
        self._pending: dict[int, list[asyncio.Future]] = {}
        self._buffering = False
        self._buffering_since = 0.0

    @property
    def is_buffering(self) -> bool:
        return self._buffering

    def buffering_duration(self) -> float:
        if self._buffering_since <= 0:
            return 0.0
        return time.time() - self._buffering_since

    # ==================================================================
    #  WAIT
    # ==================================================================
    async def wait_for_piece(self, piece: int, is_client_alive=None,
                              timeout: float | None = None) -> bool:
        if timeout is None:
            timeout = getattr(config, "STREAM_WAIT_PIECE_TIMEOUT_SEC", 25.0)
        refresh = getattr(config, "PIECE_SCHEDULER_DEADLINE_REFRESH_SEC", 5.0)

        try:
            self.scheduler.force_deadline(
                piece, lookahead=self.scheduler.LOOKAHEAD
            )
        except Exception:
            pass

        start = time.time()
        last_log = 0.0
        last_force = start

        while True:
            if is_client_alive and not is_client_alive():
                return False
            if self.geometry.have_piece(piece):
                self._buffering = False
                self._buffering_since = 0.0
                return True

            if not self._buffering:
                self._buffering = True
                self._buffering_since = time.time()

            now = time.time()
            if now - last_force > refresh:
                try:
                    self.scheduler.force_deadline(
                        piece, lookahead=self.scheduler.LOOKAHEAD
                    )
                except Exception:
                    pass
                last_force = now

            if now - last_log > 3.0:
                log.warning("wait_piece %d: %.1fs", piece, now - start)
                last_log = now

            if now - start > timeout:
                log.warning("wait_piece %d timeout", piece)
                return False

            await asyncio.sleep(0.1)

    # ==================================================================
    #  READ
    # ==================================================================
    async def read_piece(self, piece: int) -> bytes | None:
        self._buffering = False
        start, end = self.geometry.byte_range_for_piece(piece)
        if start < 0:
            return b""
        size = end - start
        if size <= 0:
            return b""

        handle = self._handle_getter()
        if handle is not None:
            data = await self._read_via_alert(handle, piece)
            if data is not None:
                return data

        return await self._read_file_fallback(start, size, piece)

    async def _read_via_alert(self, handle, piece: int) -> bytes | None:
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        lst = self._pending.setdefault(piece, [])
        max_per = getattr(config, "PENDING_READS_MAX_PER_PIECE", 5)
        if len(lst) >= max_per:
            old = lst.pop(0)
            if not old.done():
                old.cancel()
        lst.append(future)

        timeout_sec = getattr(config, "STREAM_READ_PIECE_TIMEOUT_SEC", 8.0)
        try:
            try:
                handle.read_piece(piece)
            except Exception as e:
                log.debug("read_piece(%d): %s", piece, e)
                return None
            try:
                return await asyncio.wait_for(future, timeout=timeout_sec)
            except asyncio.TimeoutError:
                log.warning("read_piece %d alert timeout", piece)
                return None
        finally:
            cur = self._pending.get(piece)
            if cur is not None:
                try:
                    cur.remove(future)
                except ValueError:
                    pass
                if not cur:
                    self._pending.pop(piece, None)

    async def _read_file_fallback(self, start: int, size: int,
                                    piece: int) -> bytes | None:
        file_path = self._file_path_getter()
        if not file_path:
            return None
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, self._read_sync, file_path, start, size
        )
        if data is None:
            return None
        if data[:1024] == b"\x00" * 1024:
            log.warning("read_piece %d: zeros", piece)
            return None
        return data

    @staticmethod
    def _read_sync(path: str, start: int, size: int) -> bytes | None:
        try:
            with open(path, "rb") as f:
                f.seek(start)
                data = f.read(size)
            return data if len(data) == size else None
        except Exception:
            return None

    # ==================================================================
    #  ALERT HANDLER
    # ==================================================================
    def on_read_piece_alert(self, alert) -> None:
        piece = alert.piece
        lst = self._pending.pop(piece, None)
        if not lst:
            return
        try:
            err = alert.error
            if err and err.value() != 0:
                data = None
            else:
                buf = alert.buffer
                data = bytes(buf) if buf else None
        except Exception:
            data = None
        for fut in lst:
            if not fut.done():
                fut.set_result(data)

    def cancel_all(self) -> None:
        for lst in self._pending.values():
            for fut in lst:
                if not fut.done():
                    fut.cancel()
        self._pending.clear()