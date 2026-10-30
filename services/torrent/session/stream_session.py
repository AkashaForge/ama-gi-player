"""StreamSession — координатор. ~230 строк.

Все тяжёлые части вынесены в:
  - HandleRegistry     (управление handle_info)
  - SourceLoader       (добавление + pre-merge)
  - FilePicker         (выбор видеофайла)
  - ReadyDetector      (выбор победителя по метрикам)
  - PieceStreamer      (wait_for_piece / read_piece)
  - AlertPump          (pop_alerts loop)
"""
import asyncio
import os
import random
import shutil
import time

import aiohttp
import libtorrent as lt

import config
from core.logging_setup import get_logger
from services.torrent.http_range_server import HttpRangeServer
from services.torrent.peer_monitor import PeerMonitor
from services.torrent.piece_map import PieceGeometry
from services.torrent.piece_scheduler import PieceScheduler
from services.torrent.session.alert_pump import AlertPump
from services.torrent.session.file_picker import FilePicker
from services.torrent.session.handle_registry import HandleRegistry
from services.torrent.session.piece_streamer import PieceStreamer
from services.torrent.session.ready_detector import ReadyDetector
from services.torrent.session.source_loader import SourceLoader
from services.torrent.source_selector import SourceSelector
from services.torrent.swarm_grouper import (
    group_sources_by_hash, merge_magnets_in_group,
)
from services.torrent.tracker_balancer import TrackerBalancer

log = get_logger("lt.stream_session")


class StreamSession:
    MAX_SOURCES = getattr(config, "STREAM_MAX_SOURCES", 12)
    READY_TIMEOUT = 30.0
    PRIORITY_TOP = 7
    DEADLINE_FIRST_PIECES = 3

    def __init__(self, http_session: aiohttp.ClientSession,
                 downloads_dir: str,
                 libtorrent_session,
                 progress_cb=None, finished_cb=None, failed_cb=None):
        if libtorrent_session is None:
            raise ValueError("requires libtorrent_session")
        self.http_session = http_session
        self.session = libtorrent_session
        self.base_downloads_dir = str(downloads_dir)
        self.downloads_dir = ""
        self._year = ""
        self.progress_cb = progress_cb
        self.finished_cb = finished_cb
        self.failed_cb = failed_cb

        self._cancelled = False
        self._ready = False
        self.handle = None
        self.torrent_info = None
        self.file_idx = -1
        self.file_size = 0
        self.file_path = ""
        self.content_type = "video/mp4"
        self.alternatives: list[dict] = []

        # Компоненты
        self.registry = HandleRegistry()
        self.file_picker = FilePicker()
        self.geometry = PieceGeometry()
        self.scheduler = PieceScheduler(self.geometry)
        self.monitor = PeerMonitor(self.geometry)
        self.http_server: HttpRangeServer | None = None

        self.piece_streamer = PieceStreamer(
            geometry=self.geometry,
            scheduler=self.scheduler,
            handle_getter=lambda: self.handle,
            file_path_getter=lambda: self.file_path,
        )
        self.alert_pump = AlertPump(
            self.session, self.piece_streamer.on_read_piece_alert
        )
        self._loader: SourceLoader | None = None

    # ==================================================================
    #  СТАРТ
    # ==================================================================
    async def start(self, sources: list[dict], year: str = ""):
        if not sources:
            self._fail("Список источников пуст")
            return

        self._year = (year or "").strip()
        self.downloads_dir = self._create_session_dir()
        self.file_picker = FilePicker(self._year)
        self._loader = SourceLoader(
            self.http_session, self.session, self.registry,
            self.file_picker, self._prioritize,
        )
        self.alert_pump.start()

        dynamic_trackers = await self._load_trackers()

        language = getattr(config, "SEARCH_LANGUAGE", "en")
        selector = SourceSelector(year, language=language)
        primary, alternatives = selector.select(sources)
        self.alternatives = alternatives
        if primary is None:
            self._fail("Нет подходящих источников")
            return

        candidates = ([primary] + alternatives)[: self.MAX_SOURCES]
        log.info("Taking %d candidates (max %d)",
                 len(candidates), self.MAX_SOURCES)

        groups = group_sources_by_hash(
            candidates, extra_trackers=dynamic_trackers
        )
        unique = self._dedup_and_merge(groups, dynamic_trackers)
        await self._load_sources(unique)

        if len(self.registry) == 0:
            self._fail("Не удалось добавить ни один источник")
            return

        if getattr(config, "STREAM_SEQUENTIAL_DOWNLOAD", True):
            for info in self.registry:
                try:
                    info.handle.set_sequential_download(True)
                except Exception:
                    pass
            log.info("Sequential download ON for %d handles (probe)",
                     len(self.registry))

        log.info("Waiting up to %.0fs for any of %d sources...",
                 self.READY_TIMEOUT, len(self.registry))

        detector = ReadyDetector(
            registry=self.registry,
            file_picker=self.file_picker,
            on_prioritize=self._prioritize,
            on_kill=self._kill_handle,
        )
        winner = await detector.detect(
            self.READY_TIMEOUT,
            cancelled_check=lambda: self._cancelled,
        )
        if winner is None:
            if not self._cancelled:
                self._fail(f"Ни один из {len(self.registry)} не начал качать")
            return

        if not self._activate_winner(winner):
            return

        self._ready = True
        self.monitor.start()

        log.info("StreamSession ready — calling finished_cb")
        if self.finished_cb:
            try:
                self.finished_cb(self)
            except Exception as e:
                log.exception("finished_cb: %s", e)

    # ==================================================================
    #  ПОДГОТОВКА
    # ==================================================================
    async def _load_trackers(self) -> list[str]:
        try:
            balancer = TrackerBalancer()
            trackers = await balancer.get_trackers()
            log.info("Trackers: %d", len(trackers))
            return trackers
        except Exception as e:
            log.warning("TrackerBalancer: %s", e)
            return []

    def _dedup_and_merge(self, groups: dict,
                          dynamic_trackers: list[str]) -> list[dict]:
        unique = []
        for hash_key, srcs in groups.items():
            if hash_key.startswith("__"):
                unique.append(srcs[0])
            else:
                best = srcs[0]
                merged_url = merge_magnets_in_group(
                    srcs, extra_trackers=dynamic_trackers
                )
                merged_src = dict(best)
                merged_src["url"] = merged_url
                if len(srcs) > 1:
                    log.info("Merged swarm %s x%d",
                             hash_key[:12], len(srcs))
                unique.append(merged_src)
        return unique

    async def _load_sources(self, unique_sources: list[dict]) -> None:
        for i, src in enumerate(unique_sources[: self.MAX_SOURCES]):
            save_dir = os.path.join(self.downloads_dir, f"h{i:02d}")
            os.makedirs(save_dir, exist_ok=True)
            result = await self._loader.load(
                src, save_dir=save_dir, is_primary=(i == 0)
            )
            if result is None:
                continue
            info, is_new = result
            log.info("Added [%d/%d] %s → h%02d%s: %s",
                     i + 1, len(unique_sources),
                     src.get("type", "?"), i,
                     "" if is_new else " (merged)",
                     (src.get("title") or "")[:55])

    # ==================================================================
    #  АКТИВАЦИЯ ПОБЕДИТЕЛЯ
    # ==================================================================
    def _activate_winner(self, winner) -> bool:
        log.info("Using working handle")
        self.handle = winner.handle
        self.downloads_dir = winner.save_dir
        try:
            self.torrent_info = winner.handle.get_torrent_info()
        except Exception as e:
            log.error("get_torrent_info: %s", e)
            self._fail("Не удалось получить torrent_info")
            return False

        self.file_idx = winner.file_idx
        try:
            self.file_size = self.torrent_info.files().file_size(
                winner.file_idx
            )
            rel_path = self.torrent_info.files().file_path(winner.file_idx)
        except Exception as e:
            log.error("file_size/path: %s", e)
            self._fail("Не удалось прочитать файл")
            return False

        candidate = os.path.normpath(os.path.join(self.downloads_dir, rel_path))
        real_base = os.path.realpath(self.downloads_dir)
        real_target = os.path.realpath(candidate)
        if not (real_target == real_base
                or real_target.startswith(real_base + os.sep)):
            log.error("Path traversal: rel=%r", rel_path)
            self._fail(f"Path traversal: {rel_path!r}")
            return False
        self.file_path = real_target

        ext = os.path.splitext(self.file_path)[1].lower()
        self.content_type = {
            '.mp4': 'video/mp4', '.mkv': 'video/x-matroska',
            '.webm': 'video/webm', '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime', '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv', '.ts': 'video/mp2t',
            '.m2ts': 'video/mp2t', '.mts': 'video/mp2t',
        }.get(ext, 'application/octet-stream')

        try:
            self.geometry.configure(
                handle=winner.handle,
                file_idx=self.file_idx,
                file_size=self.file_size,
                piece_length=self.torrent_info.piece_length(),
                num_pieces=self.torrent_info.num_pieces(),
                file_offset_in_torrent=self.torrent_info.files().file_offset(
                    self.file_idx
                ),
            )
        except Exception as e:
            log.error("geometry.configure: %s", e)
            self._fail("Не удалось сконфигурировать геометрию")
            return False

        log.info(
            "Torrent configured: %s (%.1f MB), piece=%d, offset=%d",
            os.path.basename(self.file_path),
            self.file_size / 1024 / 1024,
            self.torrent_info.piece_length(),
            self.torrent_info.files().file_offset(self.file_idx),
        )

        self._apply_full_priorities(winner.handle, self.torrent_info,
                                     self.file_idx)
        self._remove_losers(winner.handle)

        # Создаём HTTP Range сервер (запуск — в контроллере через await)
        self.http_server = HttpRangeServer(self)
        return True

    def _apply_full_priorities(self, handle, info, file_idx: int) -> None:
        try:
            n = info.files().num_files()
            for i in range(n):
                handle.file_priority(
                    i, self.PRIORITY_TOP if i == file_idx else 0
                )
        except Exception:
            pass
        first_piece = self._prioritize(handle, info, file_idx, tail=True)
        adaptive = self._adaptive_startup_count()
        self.scheduler.on_startup(first_piece, adaptive)
        log.info("Startup: first_piece=%d adaptive=%d", first_piece, adaptive)

    def _remove_losers(self, winner_handle) -> None:
        """v2.0.22: async_remove_torrent — не блокирует Qt."""
        removed = 0
        kept = 0
        for info in list(self.registry):
            if info.handle is winner_handle:
                kept += 1
                continue
            try:
                if not info.handle.has_metadata():
                    st = info.handle.status()
                    if st.num_peers > 0:
                        kept += 1
                        continue
            except Exception:
                pass
            try:
                self.session.async_remove_torrent(info.handle)
                removed += 1
            except Exception:
                pass
            self.registry.remove(info.handle)
        log.info("Removed %d, kept %d (grace)", removed, kept - 1)
    # ==================================================================
    #  ПРИОРИТЕТЫ
    # ==================================================================
    def _prioritize(self, handle, info, file_idx: int,
                    tail: bool = False) -> int:
        piece_len = info.piece_length()
        if piece_len <= 0:
            return 0
        offset = info.files().file_offset(file_idx)
        first_piece = offset // piece_len
        total = info.num_pieces()

        head_count = 5 if not tail else self.DEADLINE_FIRST_PIECES
        for i in range(head_count):
            p = first_piece + i
            if p >= total:
                break
            try:
                handle.piece_priority(p, self.PRIORITY_TOP)
                handle.set_piece_deadline(p, 2000 + i * 500)
            except Exception:
                pass

        if tail:
            tail_count = getattr(config, "PIECE_SCHEDULER_TAIL_COUNT", 20)
            tail_start = max(0, total - tail_count)
            for p in range(tail_start, total):
                try:
                    handle.piece_priority(p, self.PRIORITY_TOP)
                    handle.set_piece_deadline(p, 1000)
                except Exception:
                    pass
            log.info("Prioritized file_idx=%d first_piece=%d tail=%d..%d",
                     file_idx, first_piece, tail_start, total - 1)
        else:
            log.info("Prioritized file_idx=%d first_piece=%d head=0..%d (probe)",
                     file_idx, first_piece, head_count - 1)
        return first_piece

    def _adaptive_startup_count(self) -> int:
        piece_len = self.geometry.piece_length or 1
        target = getattr(config, "STREAM_SESSION_ADAPTIVE_START_BYTES",
                         8 * 1024 * 1024)
        from_bytes = max(1, target // piece_len)
        min_p = getattr(config, "STREAM_STARTUP_MIN_PIECES", 30)
        max_p = getattr(config, "STREAM_STARTUP_MAX_PIECES", 100)
        return max(min_p, min(max_p, from_bytes))

    def _kill_handle(self, handle) -> None:
        """v2.0.22: callback для ReadyDetector — non-blocking."""
        try:
            self.session.async_remove_torrent(handle)
        except Exception:
            pass

    # ==================================================================
    #  ПУБЛИЧНЫЙ API
    # ==================================================================
    async def wait_for_piece(self, piece: int, is_client_alive=None,
                              timeout: float | None = None) -> bool:
        return await self.piece_streamer.wait_for_piece(
            piece, is_client_alive, timeout
        )

    async def read_piece(self, piece: int) -> bytes | None:
        return await self.piece_streamer.read_piece(piece)

    def is_active(self) -> bool:
        return not self._cancelled and self._ready

    def is_buffering(self) -> bool:
        if not self._ready:
            return True
        return self.piece_streamer.is_buffering

    def buffering_duration(self) -> float:
        return self.piece_streamer.buffering_duration()

    @property
    def current_stream_pos(self) -> int:
        return self.scheduler.current_byte_pos

    @property
    def stats(self):
        return self.monitor.latest

    async def cancel(self):
        self._cancelled = True
        self._ready = False
        self.piece_streamer.cancel_all()
        self.alert_pump.stop()
        if self.monitor:
            try:
                self.monitor.stop()
            except Exception:
                pass
        if self.http_server:
            try:
                await self.http_server.stop()
            except Exception:
                pass
            self.http_server = None
        for info in self.registry:
            try:
                self.session.async_remove_torrent(info.handle)  # non-blocking
            except Exception:
                pass
        self.registry.clear()
        self.handle = None
        await self._cleanup_downloads()
    # ==================================================================
    #  СЛУЖЕБНОЕ
    # ==================================================================
    def _fail(self, msg: str) -> None:
        log.error("StreamSession fail: %s", msg)
        if self.failed_cb:
            try:
                self.failed_cb(msg)
            except Exception as e:
                log.exception("failed_cb: %s", e)

    def _create_session_dir(self) -> str:
        os.makedirs(self.base_downloads_dir, exist_ok=True)
        ts = int(time.time())
        rnd = random.randint(1000, 9999)
        path = os.path.join(self.base_downloads_dir, f"{ts}_{rnd}")
        os.makedirs(path, exist_ok=True)
        return path

    async def _cleanup_downloads(self) -> None:
        if self.downloads_dir and os.path.isdir(self.downloads_dir):
            await asyncio.sleep(0.5)
            try:
                shutil.rmtree(self.downloads_dir, ignore_errors=True)
            except Exception:
                pass
        self.downloads_dir = ""