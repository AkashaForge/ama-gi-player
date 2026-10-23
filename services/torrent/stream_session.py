"""
StreamSession — единый владелец состояния стрима.

Multi-swarm: magnet'ы с одинаковым info-hash объединяются в один торрент.

Проверка готовности: h.have_piece(first_piece) напрямую через handle.

Методы (проверка findstr):
  __init__, start, _set_file_priority_and_deadlines, _wait_any_ready,
  _add_source, _download_torrent, _configure_torrent, _pick_video_file,
  _configure_file_priorities, _adaptive_startup_count,
  wait_for_piece, read_piece, _read_file_sync,
  is_active, is_buffering, current_stream_pos, stats,
  cancel, _cleanup_downloads, _fail, _alert_loop, _create_session_dir
"""

import asyncio
import os
import random
import re
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
from services.torrent.source_selector import SourceSelector
from services.torrent.swarm_grouper import (
    extract_trackers,
    group_sources_by_hash,
    merge_magnets_in_group,
)

log = get_logger("lt.stream_session")

_YEAR_RE = re.compile(r'\b(19\d{2}|20\d{2})\b')


class StreamSession:
    MAX_SOURCES = 10
    READY_TIMEOUT = 30.0
    MIN_PROGRESS_BYTES = 8 * 1024 * 1024
    KEEP_BACKUP_HANDLES = 1
    MULTI_FILE_THRESHOLD_GB = 3
    MULTI_FILE_MAX_COUNT = 1
    MAX_STREAMABLE_FILE_GB = 25
    PRIORITY_TOP = 7
    DEADLINE_FIRST_PIECES = 3
    READY_FIRST_PIECES = 1

    def __init__(self, http_session: aiohttp.ClientSession,
                 downloads_dir: str,
                 libtorrent_session,
                 progress_cb=None,
                 finished_cb=None,
                 failed_cb=None):
        if libtorrent_session is None:
            raise ValueError("StreamSession requires shared libtorrent_session")

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
        self._buffering = False

        self.handle = None
        self._all_handles: list[lt.torrent_handle] = []
        self._handle_dirs: dict[int, str] = {}
        self._handles_by_hash: dict[str, lt.torrent_handle] = {}
        self._file_cache: dict[int, tuple[int, int]] = {}

        self.geometry = PieceGeometry()
        self.scheduler = PieceScheduler(self.geometry)
        self.monitor = PeerMonitor(self.geometry)
        self.http_server: HttpRangeServer | None = None

        self.torrent_info = None
        self.file_idx = -1
        self.file_size = 0
        self.file_path = ""
        self.content_type = "video/mp4"
        self.alternatives: list[dict] = []

        self._alert_task = None

    # ==================================================================
    #  СТАРТ
    # ==================================================================
    async def start(self, sources: list[dict], year: str = ""):
        if not sources:
            self._fail("Список источников пуст")
            return

        self._year = (year or "").strip()
        self.downloads_dir = self._create_session_dir()
        self._alert_task = asyncio.create_task(self._alert_loop())

        selector = SourceSelector(year)
        primary, alternatives = selector.select(sources)
        self.alternatives = alternatives
        if primary is None:
            self._fail("Нет подходящих источников")
            return

        candidates = [primary] + alternatives[: self.MAX_SOURCES - 1]

        groups = group_sources_by_hash(candidates)
        log.info(
            "Grouped %d candidates into %d unique sources",
            len(candidates), len(groups),
        )

        unique_sources = []
        for hash_key, srcs in groups.items():
            if hash_key.startswith("__"):
                unique_sources.append(srcs[0])
            else:
                best = srcs[0]
                merged_magnet = merge_magnets_in_group(srcs)
                merged_src = dict(best)
                merged_src["url"] = merged_magnet
                if len(srcs) > 1:
                    total_seeders = sum(s.get("seeders", 0) for s in srcs)
                    log.info(
                        "Merged swarm hash=%s... x%d sources "
                        "(%d seeders суммарно) → 1 magnet",
                        hash_key[:12], len(srcs), total_seeders,
                    )
                unique_sources.append(merged_src)

        log.info(
            "Adding %d unique torrents (after multi-swarm grouping)",
            len(unique_sources),
        )

        for i, src in enumerate(unique_sources[: self.MAX_SOURCES]):
            handle_dir = os.path.join(self.downloads_dir, f"h{i:02d}")
            os.makedirs(handle_dir, exist_ok=True)
            handle = await self._add_source(
                src, save_path=handle_dir, is_primary=(i == 0)
            )
            if handle:
                self._all_handles.append(handle)
                self._handle_dirs[id(handle)] = handle_dir
                log.info(
                    "Added [%d/%d] %s seeders=%d size=%.1fMB → h%02d: %s",
                    i + 1, len(unique_sources),
                    src.get("type", "?"),
                    src.get("seeders", 0),
                    (src.get("size", 0) or 0) / 1024 / 1024,
                    i, (src.get("title") or "")[:55],
                )

        if not self._all_handles:
            self._fail("Не удалось добавить ни один источник")
            return

        log.info(
            "Waiting up to %.0fs for any of %d sources to become ready...",
            self.READY_TIMEOUT, len(self._all_handles),
        )
        working_handle = await self._wait_any_ready(self.READY_TIMEOUT)

        if working_handle is None:
            if not self._cancelled:
                self._fail(
                    f"Ни один из {len(self._all_handles)} источников "
                    f"не начал качать за {self.READY_TIMEOUT:.0f}s"
                )
            return

        log.info("Using working handle")
        self.handle = working_handle
        self.downloads_dir = self._handle_dirs.get(
            id(working_handle), self.downloads_dir
        )

        info = working_handle.get_torrent_info()
        if not self._configure_torrent(working_handle, info):
            self._fail("Не удалось сконфигурировать торрент")
            return

        self._configure_file_priorities(working_handle, self.file_idx)
        adaptive = self._adaptive_startup_count()
        first_piece = self.geometry.piece_for_byte(0)
        self.scheduler.on_startup(first_piece, adaptive)
        log.info(
            "Startup deadlines: first_piece=%d adaptive=%d",
            first_piece, adaptive,
        )

        removed = 0
        for h in list(self._all_handles):
            if h == working_handle:
                continue
            try:
                self.session.remove_torrent(h)
                removed += 1
            except Exception:
                pass
        self._all_handles = [working_handle]
        log.info("Removed %d non-working handles", removed)

        self.http_server = HttpRangeServer(self)
        url = await self.http_server.start()
        log.info("HTTP Range: %s", url)

        self._ready = True
        self.monitor.start()

        if self.finished_cb:
            self.finished_cb(self)

    # ==================================================================
    #  ПРИОРИТЕТЫ + ДЕДЛАЙНЫ
    # ==================================================================
    def _set_file_priority_and_deadlines(self, handle: lt.torrent_handle,
                                          info, file_idx: int) -> int:
        try:
            n = info.files().num_files()
            for i in range(n):
                handle.file_priority(
                    i, self.PRIORITY_TOP if i == file_idx else 0
                )
        except Exception as e:
            log.debug("file_priority: %s", e)
            return 0

        piece_len = info.piece_length()
        if piece_len <= 0:
            return 0

        file_offset = info.files().file_offset(file_idx)
        first_piece = file_offset // piece_len

        for i in range(self.DEADLINE_FIRST_PIECES):
            p = first_piece + i
            if p >= info.num_pieces():
                break
            try:
                handle.piece_priority(p, self.PRIORITY_TOP)
            except Exception:
                pass
            try:
                deadline_ms = 100 + i * 200
                handle.set_piece_deadline(p, deadline_ms)
            except Exception as e:
                log.debug("set_piece_deadline(%d): %s", p, e)

        log.info(
            "Prioritized file_idx=%d (first_piece=%d, %d pieces deadline) "
            "for handle %s",
            file_idx, first_piece, self.DEADLINE_FIRST_PIECES, id(handle),
        )
        return first_piece

    # ==================================================================
    #  ОЖИДАНИЕ ГОТОВНОСТИ
    # ==================================================================
    async def _wait_any_ready(self, timeout: float) -> lt.torrent_handle | None:
        start = time.time()
        last_log = 0.0

        while time.time() - start < timeout and not self._cancelled:
            await asyncio.sleep(0.5)
            now = time.time()

            best_handle = None
            best_score = -1.0
            handles_with_meta = 0
            handles_all_rejected = 0

            for h in self._all_handles:
                if not h or not h.is_valid():
                    continue
                if not h.has_metadata():
                    continue

                handles_with_meta += 1
                hk = id(h)

                if hk in self._file_cache:
                    file_idx, first_piece = self._file_cache[hk]
                    if file_idx < 0:
                        handles_all_rejected += 1
                        continue
                else:
                    try:
                        info = h.get_torrent_info()
                        file_idx = self._pick_video_file(info)
                        if file_idx < 0:
                            self._file_cache[hk] = (-1, -1)
                            handles_all_rejected += 1
                            log.info(
                                "Handle %s: no streamable file — skip "
                                "permanently", hk,
                            )
                            continue
                        first_piece = self._set_file_priority_and_deadlines(
                            h, info, file_idx
                        )
                        self._file_cache[hk] = (file_idx, first_piece)
                    except Exception as e:
                        log.debug("pick+prioritize: %s", e)
                        continue

                try:
                    st = h.status()
                    num_peers = st.num_peers
                    rate = int(st.download_payload_rate or 0)
                except Exception:
                    continue

                if num_peers < 1:
                    continue

                has_first = False
                try:
                    has_first = h.have_piece(first_piece)
                except Exception as e:
                    log.debug("have_piece(%d): %s", first_piece, e)

                if has_first:
                    score = num_peers * 1000 + rate / 1024
                    if score > best_score:
                        best_score = score
                        best_handle = h

            if (handles_with_meta > 0
                    and handles_all_rejected == handles_with_meta
                    and best_handle is None):
                log.warning(
                    "All %d handles with metadata rejected by "
                    "_pick_video_file — fail immediately",
                    handles_with_meta,
                )
                return None

            if best_handle is not None:
                try:
                    st = best_handle.status()
                    log.info(
                        "Ready: %d peers, %.1f MB done, rate=%.2f MB/s, "
                        "have_first_piece=yes",
                        st.num_peers, st.total_done / 1024 / 1024,
                        st.download_payload_rate / 1024 / 1024,
                    )
                except Exception:
                    pass
                return best_handle

            if now - last_log > 3.0:
                states = []
                for i, h in enumerate(self._all_handles):
                    try:
                        if h.is_valid():
                            st = h.status()
                            has_meta = "Y" if h.has_metadata() else "N"
                            states.append(
                                f"[{i}] meta={has_meta} peers={st.num_peers} "
                                f"done={st.total_done/1024/1024:.1f}MB"
                            )
                        else:
                            states.append(f"[{i}] invalid")
                    except Exception:
                        states.append(f"[{i}] ?")
                log.info(
                    "wait_ready %.1fs: %s", now - start, " | ".join(states)
                )
                last_log = now

        log.warning(
            "Ready timeout %.0fs: ни один из %d источников не начал качать",
            timeout, len(self._all_handles),
        )
        return None

    # ==================================================================
    #  ДОБАВЛЕНИЕ ИСТОЧНИКА
    # ==================================================================
    async def _add_source(self, source: dict, save_path: str,
                          is_primary: bool = False):
        url = source.get("url", "")
        if not url:
            return None

        is_magnet = url.startswith("magnet:")
        try:
            if is_magnet:
                params = lt.parse_magnet_uri(url)
            else:
                data = await self._download_torrent(url)
                if data is None:
                    return None
                if data[:7] == b"magnet:":
                    magnet = data.decode("utf-8", errors="ignore").strip()
                    params = lt.parse_magnet_uri(magnet)
                    is_magnet = True
                else:
                    params = lt.add_torrent_params()
                    params.ti = lt.torrent_info(data)
        except Exception as e:
            log.warning(
                "parse source (%s): %s: %s",
                "primary" if is_primary else "alt",
                type(e).__name__, e,
            )
            return None

        params.save_path = save_path
        params.storage_mode = lt.storage_mode_t.storage_mode_sparse
        params.flags |= lt.torrent_flags.auto_managed
        params.flags &= ~lt.torrent_flags.paused

        try:
            handle = self.session.add_torrent(params)
        except Exception as e:
            log.warning("add_torrent: %s", e)
            return None

        if handle is None:
            return None

        if not is_magnet and params.ti is not None:
            try:
                info = params.ti
                file_idx = self._pick_video_file(info)
                if file_idx >= 0:
                    first_piece = self._set_file_priority_and_deadlines(
                        handle, info, file_idx
                    )
                    self._file_cache[id(handle)] = (file_idx, first_piece)
                else:
                    self._file_cache[id(handle)] = (-1, -1)
                    log.info(
                        "Handle (torrent) %s: no streamable file "
                        "(rejected immediately)", id(handle),
                    )
            except Exception as e:
                log.debug("initial prioritize: %s", e)

        try:
            new_hash = str(handle.info_hash())
            existing = self._handles_by_hash.get(new_hash)
            if existing is not None and existing != handle:
                log.info(
                    "Duplicate info-hash %s... — merging trackers into "
                    "existing handle",
                    new_hash[:12],
                )
                try:
                    self.session.remove_torrent(handle)
                except Exception:
                    pass
                if hasattr(existing, "add_tracker"):
                    for tr in extract_trackers(url):
                        try:
                            existing.add_tracker({"url": tr, "tier": 0})
                        except Exception:
                            pass
                return existing
            self._handles_by_hash[new_hash] = handle
        except Exception as e:
            log.debug("dedup hash: %s", e)

        if is_magnet:
            for tr in extract_trackers(url):
                try:
                    handle.add_tracker({"url": tr, "tier": 0})
                except Exception:
                    pass

        return handle

    async def _download_torrent(self, url: str) -> bytes | None:
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.http_session.get(
                url, timeout=timeout, allow_redirects=False
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if location.startswith("magnet:"):
                        return location.encode("utf-8")
                    async with self.http_session.get(
                        location, timeout=timeout
                    ) as resp2:
                        if resp2.status == 200:
                            return await resp2.read()
                elif resp.status == 200:
                    return await resp.read()
        except Exception as e:
            log.warning("download .torrent: %s", e)
        return None

    # ==================================================================
    #  КОНФИГУРАЦИЯ
    # ==================================================================
    def _configure_torrent(self, handle: lt.torrent_handle, info) -> bool:
        file_idx = self._pick_video_file(info)
        if file_idx < 0:
            return False

        self.torrent_info = info
        self.file_idx = file_idx
        self.file_size = info.files().file_size(file_idx)
        rel_path = info.files().file_path(file_idx)
        self.file_path = os.path.normpath(
            os.path.join(self.downloads_dir, rel_path)
        )
        ext = os.path.splitext(self.file_path)[1].lower()
        self.content_type = {
            '.mp4': 'video/mp4', '.mkv': 'video/x-matroska',
            '.webm': 'video/webm', '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime', '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv',
        }.get(ext, 'application/octet-stream')

        self.geometry.configure(
            handle=handle,
            file_idx=self.file_idx,
            file_size=self.file_size,
            piece_length=info.piece_length(),
            num_pieces=info.num_pieces(),
            file_offset_in_torrent=info.files().file_offset(self.file_idx),
        )
        log.info(
            "Torrent configured: file=%s (%.1f MB), piece=%d, "
            "file_offset=%d, num_pieces=%d",
            os.path.basename(self.file_path),
            self.file_size / 1024 / 1024,
            info.piece_length(),
            info.files().file_offset(self.file_idx),
            info.num_pieces(),
        )
        return True

    def _pick_video_file(self, info) -> int:
        exts = tuple(getattr(config, "LIBTORRENT_STREAMABLE_EXTS", (
            ".mp4", ".mkv", ".webm", ".m4v", ".mov", ".avi", ".wmv", ".flv"
        )))
        reject = tuple(getattr(config, "LIBTORRENT_REJECT_EXTS", (
            ".vob", ".ifo", ".bup", ".ts", ".m2ts", ".mts", ".mpg",
            ".mpeg", ".rmvb", ".divx", ".asf", ".3gp", ".ogv", ".f4v"
        )))
        min_size = 20 * 1024 * 1024
        big_threshold = self.MULTI_FILE_THRESHOLD_GB * 1024 ** 3
        max_streamable = self.MAX_STREAMABLE_FILE_GB * 1024 ** 3

        candidates = []
        big_count = 0

        for i in range(info.files().num_files()):
            full_path = info.files().file_path(i)
            p = full_path.lower()
            basename = os.path.basename(p)
            s = info.files().file_size(i)

            if s < min_size:
                continue
            if p.endswith(reject):
                continue
            if not p.endswith(exts):
                continue

            if self._year:
                file_years = _YEAR_RE.findall(basename)
                if file_years:
                    try:
                        expected = int(self._year)
                        close = any(abs(int(y) - expected) <= 1
                                    for y in file_years)
                    except ValueError:
                        close = True
                    if not close:
                        continue

            if s > max_streamable:
                continue

            candidates.append((i, s))
            if s > big_threshold:
                big_count += 1

        if not candidates:
            return -1

        if big_count > self.MULTI_FILE_MAX_COUNT:
            log.warning(
                "Torrent содержит %d крупных (>%.0f GB) видеофайлов — "
                "сборник/трилогия. Отбрасываем.",
                big_count, self.MULTI_FILE_THRESHOLD_GB,
            )
            return -1

        best = max(candidates, key=lambda c: c[1])
        return best[0]

    def _configure_file_priorities(self, handle: lt.torrent_handle,
                                    file_idx: int):
        if not handle or file_idx < 0:
            return
        try:
            n = handle.get_torrent_info().files().num_files()
            for i in range(n):
                handle.file_priority(
                    i, self.PRIORITY_TOP if i == file_idx else 0
                )
        except Exception as e:
            log.debug("file_priority: %s", e)

    def _adaptive_startup_count(self) -> int:
        piece_len = self.geometry.piece_length or 1
        target = getattr(config, "STREAM_SESSION_ADAPTIVE_START_BYTES",
                         8 * 1024 * 1024)
        return max(1, min(5, target // piece_len))

    # ==================================================================
    #  ЧТЕНИЕ
    # ==================================================================
    async def wait_for_piece(self, piece: int, is_client_alive=None) -> bool:
        start = time.time()
        last_log = 0.0
        while not self._cancelled:
            if is_client_alive and not is_client_alive():
                return False
            if self.geometry.have_piece(piece):
                return True
            self._buffering = True
            now = time.time()
            if now - last_log > 3.0:
                stats = self.monitor.latest
                log.warning(
                    "wait_piece %d: %.1fs conn=%d rate=%.2f MB/s "
                    "peers_with_piece=%d top=%s",
                    piece, now - start, stats.connected_peers,
                    stats.payload_rate / 1024 / 1024,
                    stats.peers_with_piece,
                    stats.top_peer_rates[:3],
                )
                last_log = now
            await asyncio.sleep(0.1)
        return False

    async def read_piece(self, piece: int) -> bytes | None:
        self._buffering = False
        start, end = self.geometry.byte_range_for_piece(piece)
        if start < 0:
            return b""
        size = end - start
        if size <= 0:
            return b""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._read_file_sync, start, size
        )

    def _read_file_sync(self, start: int, size: int) -> bytes | None:
        try:
            with open(self.file_path, "rb") as f:
                f.seek(start)
                data = f.read(size)
            return data if len(data) == size else None
        except Exception:
            return None

    # ==================================================================
    #  СОСТОЯНИЕ
    # ==================================================================
    def is_active(self) -> bool:
        return not self._cancelled and self._ready

    def is_buffering(self) -> bool:
        if not self._ready:
            return True
        return self._buffering

    @property
    def current_stream_pos(self) -> int:
        return self.scheduler.current_byte_pos

    @property
    def stats(self):
        return self.monitor.latest

    # ==================================================================
    #  ОТМЕНА
    # ==================================================================
    async def cancel(self):
        self._cancelled = True
        self._ready = False
        self._buffering = False
        if self.monitor:
            self.monitor.stop()
        if self.http_server:
            await self.http_server.stop()
            self.http_server = None
        for h in self._all_handles:
            if h and self.session:
                try:
                    self.session.remove_torrent(h)
                except Exception:
                    pass
        self._all_handles.clear()
        self._handles_by_hash.clear()
        self._file_cache.clear()
        self.handle = None
        if self._alert_task and not self._alert_task.done():
            self._alert_task.cancel()
            self._alert_task = None
        await self._cleanup_downloads()

    async def _cleanup_downloads(self):
        if self.downloads_dir and os.path.isdir(self.downloads_dir):
            await asyncio.sleep(0.5)
            try:
                shutil.rmtree(self.downloads_dir, ignore_errors=True)
            except Exception as e:
                log.debug("cleanup_downloads: %s", e)
        self.downloads_dir = ""

    def _fail(self, msg: str):
        log.error("StreamSession fail: %s", msg)
        if self.failed_cb:
            self.failed_cb(msg)

    async def _alert_loop(self):
        while not self._cancelled and self.session:
            try:
                alerts = self.session.pop_alerts()
                for alert in alerts:
                    if isinstance(alert, lt.metadata_received_alert):
                        log.info("ALERT: metadata_received")
                    elif isinstance(alert, lt.metadata_failed_alert):
                        log.warning(
                            "ALERT: metadata_failed: %s", alert.message()
                        )
                    elif isinstance(alert, lt.torrent_error_alert):
                        log.error(
                            "ALERT: torrent_error: %s", alert.message()
                        )
            except Exception:
                pass
            await asyncio.sleep(0.5)

    def _create_session_dir(self) -> str:
        os.makedirs(self.base_downloads_dir, exist_ok=True)
        ts = int(time.time())
        rnd = random.randint(1000, 9999)
        path = os.path.join(self.base_downloads_dir, f"{ts}_{rnd}")
        os.makedirs(path, exist_ok=True)
        return path
