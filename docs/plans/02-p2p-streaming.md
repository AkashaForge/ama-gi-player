# Plan: P2P Streaming via libtorrent + HTTP Range

**Goal:** клик «Start streaming» в private → 12 магнитов добавлены →
выбран победитель → HTTP Range сервер запущен → QMediaPlayer играет →
seek работает → закрытие освобождает handles за ≤ 15s.

**Depends on:** Plan 01 (UI, StreamController skeleton, PlaybackController).

**Out of scope:** fallback (Plan 03), Jackett/WebFetcher/nodriver (Plan 04),
switch_mode (Plan 05).

**Estimated:** 8–12 hours для джуна.

**Key risk:** libtorrent на Windows. QMediaPlayer держит file handle,
libtorrent не может удалить torrent. Решается в `cancel()` через
15s polling + sync fallback (T-5.4).

---

## Phase -1: Contracts & Stubs

Цель: создать все зависимости, которые Plan 01 использовал, но не
создавал. И добавить константы config, которых в T-0.3 Plan 01 нет.

### T--1.1: Все stubs-классы и функции

**Время:** 20 min
**Файлы:**
- `core/utils.py` (create)
- `search/aggregator/tasks/__init__.py` (create)
- `search/aggregator/tasks/archive_org.py` (create)
- `search/aggregator/tasks/balancers.py` (create)
- `search/aggregator/tasks/jackett.py` (create)
- `search/aggregator/tasks/web_fetcher.py` (create)
- `search/aggregator/tasks/yts.py` (create)
- `search/aggregator/tasks/torapi.py` (create)
- `services/kp_service.py` (create — stub)
- `services/balancer_client.py` (create — stub)
- `search/web_fetcher/fetcher.py` (create — stub)
- `search/jackett_client.py` (create — stub)
- `search/prowlarr_client.py` (create — stub)
- `legal_gate.py` (create — stub)
- `legal_texts.py` (create — stub)
- `services/process_cleaner.py` (create — stub)
- `services/torrent/lt_session.py` (create — stub)

**Зависит от:** T-0.1 (директории)

**Шаги:**
1. `core/utils.py`: `dedup_by_url(items) -> list[dict]`, `sanitize_query(s) -> str`
2. `search/aggregator/tasks/archive_org.py`:
   ```python
   async def safe_archive_org(searcher, query, year):
       import asyncio
       try:
           return await asyncio.wait_for(
               searcher.search(query, year), timeout=30.0
           )
       except Exception:
           return []
   ```
3. Остальные `safe_*` — аналогично, stub возвращает `[]` или `([], {})`
4. `KPService` — stub с методами `get_movie_data`, `search_movies_by_keyword`,
   `get_popular_movies`, `log_stats` (все возвращают `{}`/`[]`)
5. `BalancerClient` — stub с `search()` → `[]`
6. `WebFetcher` — stub с `is_disabled()` → `True`, `search_all()` → `[]`, `close()`
7. `JackettClient`, `ProwlarrClient` — stub с `diagnose()` → `{}`,
   `search_all()` → `[]`
8. `LegalGateDialog` — `QDialog` с кнопкой «Принять», возвращает `Accepted`
9. `cleanup_startup()`, `cleanup_all(kill_browsers=True)` — `pass`
10. `create_session(listen_port)` — stub с `import libtorrent as lt;
    return lt.session()`

**Проверка:**
```bash
python -c "import core.utils, legal_gate, services.kp_service; print('ok')"
python -c "from search.aggregator.tasks.archive_org import safe_archive_org; print('ok')"
```

---

### T--1.2: config.py — ВСЕ константы плана

**Время:** 15 min
**Файлы:** `config.py` (append)
**Зависит от:** T-0.3

**Шаги:**
1. Mode:
   ```python
   _MODE_FILE = DATA_DIR / "mode.txt"
   _runtime_mode = "public"
   if _MODE_FILE.exists():
       _c = _MODE_FILE.read_text(encoding="utf-8").strip().lower()
       if _c in ("public", "private"):
           _runtime_mode = _c
   MODE = _runtime_mode
   if _runtime_mode == "private":
       LEGAL_ONLY_MODE = False
       LEGAL_TRACKERS_TAG = ""
       LEGAL_FEED_ONLY_AVAILABLE = False
       DISABLE_WHITELIST = True
       SEARCH_LANGUAGE = "ru"
   else:
       LEGAL_ONLY_MODE = True
       LEGAL_TRACKERS_TAG = "legal"
       LEGAL_FEED_ONLY_AVAILABLE = True
       DISABLE_WHITELIST = False
       SEARCH_LANGUAGE = "en"
   LAZY_RESOLVE = True
   USE_WHITELIST = not DISABLE_WHITELIST
   ```
2. IA / cache:
   ```python
   ARCHIVE_ORG_ENABLED = True
   ARCHIVE_ORG_MAX_RESULTS = 10
   ARCHIVE_ORG_MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
   ARCHIVE_ORG_MAX_METADATA_CHECKS = 8
   ARCHIVE_ORG_METADATA_CACHE_TTL = 24 * 3600
   ARCHIVE_ORG_METADATA_CACHE_MAX = 500
   ARCHIVE_ORG_MIN_MOVIE_SIZE = 30 * 1024 * 1024
   POPULAR_CACHE_TTL_HOURS = 24
   SEARCH_CACHE_TTL_HOURS = 6
   SHORT_CACHE_TTL_HOURS = 24 * 30
   LEGAL_DISCLAIMER_ACCEPTED = False
   DOWNLOADS_MAX_GB = 50
   DOWNLOADS_CLEANUP_ON_START = True
   ```
3. libtorrent / P2P:
   ```python
   LIBTORRENT_PORT = 6881
   LIBTORRENT_CONNECTION_SPEED = 200
   LIBTORRENT_TORRENT_CONNECT_BOOST = 100
   LIBTORRENT_PEER_CONNECT_TIMEOUT = 3
   LIBTORRENT_PIECE_TIMEOUT = 10
   LIBTORRENT_REQUEST_TIMEOUT = 10
   LIBTORRENT_PEER_TIMEOUT = 10
   LIBTORRENT_MIN_RECONNECT_TIME = 1
   LIBTORRENT_SMOOTH_CONNECTS = False
   LIBTORRENT_CACHE_SIZE = 0
   LIBTORRENT_CACHE_EXPIRY = 0
   LIBTORRENT_STREAMABLE_EXTS = (".mp4", ".mkv", ".webm", ".m4v", ".mov", ".wmv", ".flv")
   LIBTORRENT_REJECT_EXTS = (".vob", ".ifo", ".bup", ".ts", ".m2ts", ".mts",
                             ".mpg", ".mpeg", ".rmvb", ".divx", ".asf", ".3gp",
                             ".ogv", ".f4v", ".avi")
   LIBTORRENT_ALLOW_TS_FALLBACK = True
   DEBUG_PICK_FILE = False
   ```
4. Piece scheduler:
   ```python
   PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS = 100
   PIECE_SCHEDULER_LOOKAHEAD_PIECES = 10
   PIECE_SCHEDULER_DEADLINE_STEP_MS = 150
   PIECE_SCHEDULER_TRAILING_RETENTION = 3
   PIECE_SCHEDULER_TAIL_DEADLINE_MS = 1000
   PIECE_SCHEDULER_DEADLINE_REFRESH_SEC = 5.0
   PIECE_SCHEDULER_TAIL_COUNT = 20
   ```
5. HTTP Range / stream session:
   ```python
   PEER_MONITOR_INTERVAL_SEC = 2.0
   PEER_MONITOR_TOP_N = 5
   HTTP_RANGE_CACHE_PIECES = 8
   HTTP_RANGE_POLL_SEC = 0.05
   HTTP_RANGE_CHUNK_SIZE = 1024 * 1024
   STREAM_SESSION_READY_MIN_CONNECTED_PEERS = 3
   STREAM_SESSION_READY_MIN_PIECES = 1
   STREAM_SESSION_STARTUP_TIMEOUT_SEC = 60.0
   STREAM_SESSION_ADAPTIVE_START_BYTES = 8 * 1024 * 1024
   STREAM_STARTUP_MIN_PIECES = 30
   STREAM_STARTUP_MAX_PIECES = 100
   STREAM_READY_GRACE_PERIOD_SEC = 10.0
   STREAM_READY_BEST_SCORE_MARGIN = 2.0
   STREAM_KILL_DEAD_HANDLE_SEC = 10.0
   STREAM_KILL_DEAD_META_SEC = 60.0
   STREAM_KILL_NO_FIRST_PIECE_SEC = 45.0
   STREAM_SEQUENTIAL_DOWNLOAD = True
   STREAM_WAIT_PIECE_TIMEOUT_SEC = 25.0
   STREAM_READ_PIECE_TIMEOUT_SEC = 8.0
   PENDING_READS_MAX_PER_PIECE = 5
   STREAM_BUFFERING_WATCHDOG_SEC = 25.0
   STREAM_BUFFERING_WATCHDOG_RATE_MB = 0.3
   STREAM_AUTO_FALLBACK_ON_DEMUX_ERROR = True
   STREAM_DEMUX_RELOAD_DELAY_SEC = 5.0
   STREAM_MAX_RELOADS_BEFORE_FALLBACK = 1
   STREAM_BUFFER_STOP_DELAY_SEC = 30.0
   STREAM_DEMUX_ERROR_COOLDOWN_SEC = 1.0
   STREAM_MONITOR_INTERVAL_MS = 1000
   STREAM_MAX_SOURCES = 12
   MULTI_FILE_THRESHOLD_GB = 5
   MULTI_FILE_MAX_COUNT = 2
   MAX_STREAMABLE_FILE_GB = 100
   PROBE_HEAD_PIECES = 5
   PROBE_MIN_RATE_MB = 0.2
   PROBE_MIN_PEERS = 10
   ```
6. Source selector:
   ```python
   SOURCE_SELECTOR_MAX_ALTERNATIVES = 15
   SOURCE_SELECTOR_MIN_SEEDERS = 1
   SCORE_WEIGHT_HEALTH = 0.30
   SCORE_WEIGHT_RESOLUTION = 0.25
   SCORE_WEIGHT_SOURCE = 0.20
   SCORE_WEIGHT_CODEC = 0.15
   SCORE_WEIGHT_TRUSTED = 0.10
   SCORE_PENALTY_TELESYNC = -0.80
   SCORE_PENALTY_CAM = -1.00
   SCORE_PENALTY_TS = -0.80
   SCORE_PENALTY_SCREENER = -0.60
   SCORE_BONUS_2160P = 0.25
   SCORE_BONUS_1080P = 0.20
   SCORE_BONUS_720P = 0.10
   SCORE_BONUS_BLURAY = 0.15
   SCORE_BONUS_WEB_DL = 0.15
   SCORE_BONUS_HEVC = 0.10
   ```
7. Tracker balancer:
   ```python
   TRACKER_BALANCERS_FILE = DATA_DIR / "tracker_balancers.txt"
   TRACKER_CACHE_FILE = DATA_DIR / "trackers_cache.txt"
   TRACKER_BALANCER_TTL_HOURS = 12
   TRACKER_BALANCER_TIMEOUT_SEC = 10.0
   TRACKER_BALANCER_MAX_URLS = 10
   TRACKER_BALANCER_MAX_TRACKERS = 200
   TRACKER_BALANCER_MAX_RESPONSE_BYTES = 1024 * 1024
   TRACKER_BALANCER_VERIFY_SSL = True
   ```

**Проверка:**
```bash
python -c "import config; print(config.LEGAL_ONLY_MODE, config.STREAM_MAX_SOURCES, config.PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS)"
# → True 12 100
```

---

## Phase 0: libtorrent session + geometry

### T-0.1: `requirements.txt` + libtorrent

**Время:** 2 min
**Файлы:** `requirements.txt` (append)

**Шаги:**
1. Добавить `libtorrent==2.1.1`
2. `pip install libtorrent==2.1.1`

**Проверка:**
```bash
python -c "import libtorrent as lt; print(lt.__version__)"
```

---

### T-0.2: `services/torrent/lt_session.py`

**Время:** 6 min
**Файлы:** `services/torrent/lt_session.py` (replace stub from T--1.1)
**Зависит от:** T-0.1, T--1.2

**Шаги:**
1. `import libtorrent as lt`, `import config`
2. `create_session(listen_port: int) -> lt.session`:
   ```python
   settings = {
       'listen_interfaces': f'0.0.0.0:{listen_port},[::]:{listen_port}',
       'enable_dht': True, 'enable_lsd': True,
       'enable_upnp': True, 'enable_natpmp': True,
       'download_rate_limit': 0, 'upload_rate_limit': 0,
       'alert_mask': (lt.alert.category_t.error_notification
                      | lt.alert.category_t.status_notification
                      | lt.alert.category_t.storage_notification),
       'smooth_connects': config.LIBTORRENT_SMOOTH_CONNECTS,
       'connection_speed': config.LIBTORRENT_CONNECTION_SPEED,
       'torrent_connect_boost': config.LIBTORRENT_TORRENT_CONNECT_BOOST,
       'min_reconnect_time': config.LIBTORRENT_MIN_RECONNECT_TIME,
       'peer_connect_timeout': config.LIBTORRENT_PEER_CONNECT_TIMEOUT,
       'piece_timeout': config.LIBTORRENT_PIECE_TIMEOUT,
       'request_timeout': config.LIBTORRENT_REQUEST_TIMEOUT,
       'peer_timeout': config.LIBTORRENT_PEER_TIMEOUT,
       'cache_size': config.LIBTORRENT_CACHE_SIZE,
       'cache_expiry': config.LIBTORRENT_CACHE_EXPIRY,
   }
   ses = lt.session(settings)
   for host in ("router.bittorrent.com", "router.utorrent.com",
                "dht.transmissionbt.com", "dht.libtorrent.org"):
       try:
           ses.add_dht_router(host, 6881)
       except Exception:
           pass
   return ses
   ```

**Проверка:**
```bash
python -c "from services.torrent.lt_session import create_session; s = create_session(6881); print(len(s.get_torrents()))"
# → 0
```

---

### T-0.3: `services/torrent/piece_map.py`

**Время:** 6 min
**Файлы:** `services/torrent/piece_map.py` (create)
**Зависит от:** —

**Шаги:**
1. `class PieceGeometry` с полями:
   ```python
   self.handle = None
   self.file_idx = -1
   self.file_size = 0
   self.piece_length = 0
   self.num_pieces = 0
   self.file_offset_in_torrent = 0
   self.current_piece = -1
   ```
2. `configure(handle, file_idx, file_size, piece_length, num_pieces,
   file_offset_in_torrent)` — просто присваивание полей
3. `piece_for_byte(byte_pos) -> int`:
   ```python
   if not self.handle or self.piece_length <= 0:
       return -1
   absolute_byte = self.file_offset_in_torrent + byte_pos
   if absolute_byte < 0:
       return -1
   piece = absolute_byte // self.piece_length
   if piece < 0 or piece >= self.num_pieces:
       return -1
   return piece
   ```
4. `byte_range_for_piece(piece) -> (int, int)`:
   ```python
   piece_start_in_torrent = piece * self.piece_length
   piece_end_in_torrent = piece_start_in_torrent + self.piece_length
   file_start = self.file_offset_in_torrent
   file_end = file_start + self.file_size
   overlap_start = max(piece_start_in_torrent, file_start)
   overlap_end = min(piece_end_in_torrent, file_end)
   if overlap_start >= overlap_end:
       return -1, -1
   return (overlap_start - file_start, overlap_end - file_start)
   ```
5. `have_piece(piece) -> bool` — `handle.have_piece(piece)` в try/except

**Проверка:**
```python
from services.torrent.piece_map import PieceGeometry
g = PieceGeometry()
g.configure(None, 0, 1000, 256, 4, 0)
assert g.piece_for_byte(0) == 0
assert g.piece_for_byte(255) == 0
assert g.piece_for_byte(256) == 1
assert g.byte_range_for_piece(0) == (0, 256)
```

---

## Phase 1: Scheduler + PieceStreamer + AlertPump

### T-1.1: `services/torrent/piece_scheduler.py`

**Время:** 15 min
**Файлы:** `services/torrent/piece_scheduler.py` (create)
**Зависит от:** T--1.2, T-0.3

**Шаги:**
1. `class PieceScheduler(geometry)` — `_current_piece = -1`, `_current_byte_pos = 0`
2. Константы из config:
   ```python
   self.DEADLINE_HEAD_MS = max(100, config.PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS)
   self.LOOKAHEAD = config.PIECE_SCHEDULER_LOOKAHEAD_PIECES
   self.DEADLINE_STEP_MS = config.PIECE_SCHEDULER_DEADLINE_STEP_MS
   self.TRAILING_RETENTION = config.PIECE_SCHEDULER_TRAILING_RETENTION
   self.TAIL_DEADLINE_MS = config.PIECE_SCHEDULER_TAIL_DEADLINE_MS
   self.PRIORITY_TOP = 7
   ```
3. `_set_high_priority(piece, deadline_ms)`:
   ```python
   handle = self.geometry.handle
   if not handle or piece < 0 or piece >= self.geometry.num_pieces:
       return
   try:
       handle.piece_priority(piece, self.PRIORITY_TOP)
   except Exception:
       pass
   if deadline_ms <= 0:
       deadline_ms = self.DEADLINE_HEAD_MS
   try:
       handle.set_piece_deadline(piece, deadline_ms)
   except Exception:
       pass
   ```
4. `_apply_deadlines(start_piece)` — для `i in range(LOOKAHEAD)`:
   `deadline = DEADLINE_HEAD_MS + i * DEADLINE_STEP_MS`,
   `_set_high_priority(start_piece + i, deadline)`
5. `on_position(byte_pos)`:
   - `piece = geometry.piece_for_byte(byte_pos)`
   - `if piece < 0 or piece == _current_piece: return`
   - `_current_piece = piece; geometry.current_piece = piece`
   - `_apply_deadlines(piece)`
   - для `i in range(1, TRAILING_RETENTION + 1): _set_high_priority(piece - i, TAIL_DEADLINE_MS)`
6. `on_seek(byte_pos)`:
   - `handle.clear_piece_deadlines()` в try/except
   - `_current_piece = -1`
   - `on_position(byte_pos)`
7. `force_deadline(piece, lookahead=None)`:
   - `la = lookahead if lookahead is not None else LOOKAHEAD`
   - `for i in range(la): deadline = DEADLINE_HEAD_MS + i * DEADLINE_STEP_MS;
      _set_high_priority(piece + i, deadline)`
8. `on_startup(first_piece, adaptive_count)`:
   - `handle.clear_piece_deadlines()`
   - head: `for i in range(adaptive_count): _set_high_priority(first_piece + i, DEADLINE_HEAD_MS + i * DEADLINE_STEP_MS)`
   - tail: `tail_start = max(0, num_pieces - PIECE_SCHEDULER_TAIL_COUNT)`,
     `for p in range(tail_start, num_pieces): _set_high_priority(p, TAIL_DEADLINE_MS)`
9. Properties: `current_piece`, `current_byte_pos`

**Проверка:**
```python
from unittest.mock import MagicMock
from services.torrent.piece_map import PieceGeometry
from services.torrent.piece_scheduler import PieceScheduler

g = PieceGeometry()
mock_handle = MagicMock()
g.configure(mock_handle, 0, 10_000_000, 1_048_576, 10, 0)
s = PieceScheduler(g)
s.force_deadline(5, lookahead=3)
calls = [c.args for c in mock_handle.set_piece_deadline.call_args_list]
assert len(calls) == 3
assert calls[0][0] == 5 and calls[0][1] >= 100
```

---

### T-1.2: `services/torrent/session/piece_streamer.py`

**Время:** 15 min
**Файлы:** `services/torrent/session/piece_streamer.py` (create)
**Зависит от:** T-1.1

**Шаги:**
1. `class PieceStreamer(geometry, scheduler, handle_getter, file_path_getter)`:
   ```python
   self.geometry = geometry
   self.scheduler = scheduler
   self._handle_getter = handle_getter
   self._file_path_getter = file_path_getter
   self._pending: dict[int, list[asyncio.Future]] = {}
   self._buffering = False
   self._buffering_since = 0.0
   ```
2. `is_buffering` (property), `buffering_duration() -> float`
3. `async wait_for_piece(piece, is_client_alive=None, timeout=None) -> bool`:
   - `timeout = timeout or config.STREAM_WAIT_PIECE_TIMEOUT_SEC`
   - `refresh = config.PIECE_SCHEDULER_DEADLINE_REFRESH_SEC`
   - `scheduler.force_deadline(piece, lookahead=scheduler.LOOKAHEAD)` в try/except
   - `start = time.time(); last_force = start`
   - loop:
     - `if is_client_alive and not is_client_alive(): return False`
     - `if geometry.have_piece(piece): _buffering = False; return True`
     - `if not _buffering: _buffering = True; _buffering_since = time.time()`
     - `now = time.time()`
     - `if now - last_force > refresh: scheduler.force_deadline(...); last_force = now`
     - `if now - start > timeout: return False`
     - `await asyncio.sleep(0.05)`
4. `async read_piece(piece) -> bytes | None`:
   - `start, end = geometry.byte_range_for_piece(piece)`
   - `if start < 0: return b""`
   - `handle = _handle_getter()`
   - `if handle: data = await _read_via_alert(handle, piece); if data is not None: return data`
   - `return await _read_file_fallback(start, size, piece)`
5. `async _read_via_alert(handle, piece) -> bytes | None`:
   - `future = asyncio.get_event_loop().create_future()`
   - `lst = self._pending.setdefault(piece, [])`
   - `max_per = config.PENDING_READS_MAX_PER_PIECE`
   - `if len(lst) >= max_per: old = lst.pop(0); if not old.done(): old.cancel()`
   - `lst.append(future)`
   - `handle.read_piece(piece)` в try/except
   - `return await asyncio.wait_for(future, timeout=config.STREAM_READ_PIECE_TIMEOUT_SEC)`
   - finally: убрать future из `_pending[piece]`, если пусто — удалить piece
6. `async _read_file_fallback(start, size, piece)`:
   - `file_path = _file_path_getter(); if not file_path: return None`
   - `loop.run_in_executor(None, self._read_sync, file_path, start, size)`
   - `if data[:1024] == b"\x00" * 1024: return None`
7. `_read_sync(path, start, size) -> bytes | None` — sync `open/seek/read`
8. `on_read_piece_alert(alert) -> None`:
   - `piece = alert.piece`, `lst = self._pending.pop(piece, None)`
   - `if not lst: return`
   - `if alert.error and alert.error.value() != 0: data = None else: bytes(alert.buffer)`
   - `for fut in lst: if not fut.done(): fut.set_result(data)`
9. `cancel_all()` — `fut.cancel()` для всех, `_pending.clear()`

**Проверка:**
```python
import asyncio
from unittest.mock import MagicMock
from services.torrent.piece_map import PieceGeometry
from services.torrent.piece_scheduler import PieceScheduler
from services.torrent.session.piece_streamer import PieceStreamer

async def test():
    g = PieceGeometry()
    h = MagicMock()
    h.have_piece.return_value = False
    g.configure(h, 0, 10_000_000, 1_048_576, 10, 0)
    s = PieceScheduler(g)
    ps = PieceStreamer(g, s, lambda: h, lambda: "/tmp/x")
    result = await ps.wait_for_piece(0, timeout=0.1)
    assert result is False  # timeout, piece не готов
asyncio.run(test())
```

---

### T-1.3: `services/torrent/session/alert_pump.py`

**Время:** 10 min
**Файлы:** `services/torrent/session/alert_pump.py` (create)
**Зависит от:** T-1.2

**Шаги:**
1. `class AlertPump(lt_session, on_read_piece)`:
   - `self.session = lt_session`
   - `self._on_read_piece = on_read_piece`
   - `self._task: asyncio.Task | None = None`
   - `self._cancelled = False`
2. `start()`:
   - `if _task and not done: return`
   - `_cancelled = False; _task = asyncio.create_task(_loop())`
3. `async _loop()`:
   ```python
   while not self._cancelled and self.session:
       try:
           alerts = self.session.pop_alerts()
           for alert in alerts:
               if isinstance(alert, lt.read_piece_alert):
                   self._on_read_piece(alert)
               elif isinstance(alert, lt.torrent_error_alert):
                   log.error("ALERT: torrent_error: %s", alert.message())
       except Exception:
           pass
       await asyncio.sleep(0.1)
   ```
4. `async stop()` — **async, не sync:**
   ```python
   self._cancelled = True
   await asyncio.sleep(0.05)   # дать pump финальный pop_alerts
   if self._task and not self._task.done():
       self._task.cancel()
       try:
           await self._task
       except Exception:
           pass
       self._task = None
   ```

**Проверка:**
```python
import asyncio, libtorrent as lt
from services.torrent.session.alert_pump import AlertPump

async def test():
    ses = lt.session()
    called = []
    pump = AlertPump(ses, lambda a: called.append(a))
    pump.start()
    await asyncio.sleep(0.2)
    await pump.stop()
    assert pump._task is None
asyncio.run(test())
```

---

## Phase 2: Selection

### T-2.1: `services/torrent/source_selector.py`

**Время:** 20 min
**Файлы:** `services/torrent/source_selector.py` (create)
**Зависит от:** T--1.2

**Шаги:**
1. `_HARD_REJECT_RE = re.compile(r'\b(?:camrip|cam-rip|hdcam|hdts|tsrip|ts-rip|telesync|telecine|screener|scr|dvdscr)\b', re.IGNORECASE)`
2. `_health_component(seeders, peers) -> float`:
   ```python
   if seeders <= 0: return 0.0
   ratio = seeders / max(1, peers)
   norm_ratio = min(ratio / 5.0, 1.0)
   norm_seeds = min(seeders / 200.0, 1.0)
   return (norm_ratio * 0.4) + (norm_seeds * 0.6)
   ```
3. `_resolution_component(title) -> float` — 2160p/4k → `SCORE_BONUS_2160P`,
   1080p → `SCORE_BONUS_1080P`, 720p → `SCORE_BONUS_720P`, else 0.0
4. `_source_component(title) -> float` — bluray/bdremux → `SCORE_BONUS_BLURAY`,
   web-dl → `SCORE_BONUS_WEB_DL`, webrip/bdrip → 0.05, hdrip → -0.05
5. `_codec_component(title) -> float` — hevc/h265/x265 → `SCORE_BONUS_HEVC`
6. `_trusted_component(source) -> float` — indexer in (yts, rarbg, eztv,
   torrentapi) → 0.10
7. `_is_hard_reject(title, size) -> bool`:
   - `if not title: return True`
   - `if _HARD_REJECT_RE.search(title): return True`
   - `if not is_safe_release(title, size): return True`
   - `return False`
8. `class SourceSelector(year="", language="")`:
   - `_score(source) -> float`:
     ```python
     health = _health_component(seeders, peers)
     res = _resolution_component(title)
     src = _source_component(title)
     codec = _codec_component(title)
     trusted = _trusted_component(source)
     score = (health * config.SCORE_WEIGHT_HEALTH
              + res * config.SCORE_WEIGHT_RESOLUTION
              + src * config.SCORE_WEIGHT_SOURCE
              + codec * config.SCORE_WEIGHT_CODEC
              + trusted * config.SCORE_WEIGHT_TRUSTED)
     low = title.lower()
     if "telesync" in low: score += config.SCORE_PENALTY_TELESYNC
     if "cam" in low: score += config.SCORE_PENALTY_CAM
     if "ts" in low and "telesync" not in low: score += config.SCORE_PENALTY_TS
     if "screener" in low or "dvdscr" in low: score += config.SCORE_PENALTY_SCREENER
     return round(score, 4)
     ```
   - `rank(sources) -> list[dict]`:
     - filter `_is_hard_reject`, `s["_score"] = self._score(s)`
     - sort desc, log top 15
   - `select(sources) -> (dict | None, list[dict])`:
     - `ranked = self.rank(sources)`
     - `if not ranked: return None, []`
     - `return ranked[0], ranked[1:1 + config.SOURCE_SELECTOR_MAX_ALTERNATIVES]`

**Проверка:**
```python
from services.torrent.source_selector import SourceSelector
s = SourceSelector(year="2023", language="en")
ranked = s.rank([
    {"title": "Movie 1080p BluRay x265", "seeders": 500, "leechers": 10},
    {"title": "Movie CAM", "seeders": 5000, "leechers": 0},
])
assert len(ranked) == 1  # CAM отброшен
assert ranked[0]["_score"] > 0
```

---

### T-2.2: `services/torrent/swarm_grouper.py`

**Время:** 12 min
**Файлы:** `services/torrent/swarm_grouper.py` (create)
**Зависит от:** T--1.2

**Шаги:**
1. Регулярки:
   ```python
   _BTIH_RE = re.compile(r'btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})', re.IGNORECASE)
   _TR_RE = re.compile(r'[?&]tr=([^&]+)')
   _HASH_IN_URL_RE = re.compile(r'\b([a-fA-F0-9]{40})\b')
   _TORRENT_URL_HINTS = (".torrent", "/download/", "/dl/", "/torrent/")
   ```
2. `extract_info_hash(url) -> str | None`:
   - magnet → `_BTIH_RE.search`, если 40 — lower, если 32 — `base64.b32decode().hex()`
   - torrent URL с hints → `_HASH_IN_URL_RE.search`
3. `extract_trackers(url) -> list[str]` — `_TR_RE.findall`
4. `DEFAULT_TRACKERS_FALLBACK = ("udp://tracker.opentrackr.org:1337/announce", ...)` — 7 штук
5. `_merge_trackers(existing, extra)` — union, dedup
6. `enrich_magnet_with_default_trackers(url, extra)` — если < 5 trackers,
   добавить до 5
7. `group_sources_by_hash(sources, extra_trackers) -> dict[str, list[dict]]`
8. `merge_magnets_in_group(sources, extra_trackers) -> str`

**Проверка:**
```python
from services.torrent.swarm_grouper import extract_info_hash, group_sources_by_hash
h = extract_info_hash("magnet:?xt=urn:btih:" + "a"*40)
assert h == "a"*40
groups = group_sources_by_hash([
    {"url": f"magnet:?xt=urn:btih:{'a'*40}"},
    {"url": f"magnet:?xt=urn:btih:{'a'*40}&tr=udp://x:1337"},
])
assert len([g for g in groups if not g.startswith("__")]) == 1
```

---

### T-2.3: `services/torrent/tracker_balancer.py`

**Время:** 12 min
**Файлы:** `services/torrent/tracker_balancer.py` (create)
**Зависит от:** T--1.2

**Шаги:**
1. `DEFAULT_TRACKERS_FALLBACK` — тот же, что в T-2.2 (можно импортировать)
2. `_is_safe_balancer_url(url) -> bool`:
   - `url.startswith(("http://", "https://"))`
   - `host = urlparse(url).hostname`
   - блок: localhost, 127.0.0.1, 0.0.0.0, ::1, `10.*`, `192.168.*`, `172.16-31.*`
3. `_is_valid_tracker(t)` — scheme in (udp, http, https, wss)
4. `class TrackerBalancer`:
   - `_trackers = []`, `_loaded_at = 0.0`,
     `_ttl = config.TRACKER_BALANCER_TTL_HOURS * 3600`
   - `async get_trackers() -> list[str]`:
     - TTL in memory → return
     - cache file TTL → return
     - `_load_urls()` → `_download_all()` → `_write_file()` → return
     - если пусто — `DEFAULT_TRACKERS_FALLBACK`
   - `_load_urls() -> list[str]` — читает `config.TRACKER_BALANCERS_FILE`,
     `_is_safe_balancer_url`, cap `TRACKER_BALANCER_MAX_URLS`
   - `async _download_one(url)` — aiohttp GET, timeout 10, cap bytes
   - `async _download_all(urls)` — `asyncio.gather`, union, cap
     `TRACKER_BALANCER_MAX_TRACKERS`
   - `_read_file`, `_write_file`, `reload()`

**Проверка:**
```python
import asyncio
from services.torrent.tracker_balancer import TrackerBalancer
async def test():
    tb = TrackerBalancer()
    trackers = await tb.get_trackers()
    assert len(trackers) >= 7  # fallback
asyncio.run(test())
```

---

### T-2.4: `services/torrent/session/file_picker.py`

**Время:** 12 min
**Файлы:** `services/torrent/session/file_picker.py` (create)
**Зависит от:** T--1.2

**Шаги:**
1. `RETRY = -2`, `NO_VIDEO = -1`
2. `class FilePicker(year="")`:
   - `_exts = config.LIBTORRENT_STREAMABLE_EXTS`
   - `_reject = config.LIBTORRENT_REJECT_EXTS`
   - `_allow_ts = config.LIBTORRENT_ALLOW_TS_FALLBACK`
   - `_ts_exts = (".ts", ".m2ts", ".mts")`
   - `MIN_FILE_MB = 20`
   - `MULTI_FILE_THRESHOLD_GB = config.MULTI_FILE_THRESHOLD_GB`
   - `MULTI_FILE_MAX_COUNT = config.MULTI_FILE_MAX_COUNT`
   - `MAX_STREAMABLE_FILE_GB = config.MAX_STREAMABLE_FILE_GB`
3. `pick(info) -> int`:
   - `num_files = info.files().num_files()`, `if 0: return RETRY`
   - `min_size = MIN_FILE_MB * 1024 * 1024`, `max_size = MAX_STREAMABLE_FILE_GB * 1024**3`
   - цикл по файлам:
     - `size < min_size or size > max_size: continue`
     - `is_ts`: append в `ts_candidates`, continue (если `_allow_ts`)
     - `is_reject_ext`: continue
     - `not is_video`: append в `any_big_files`, continue
     - year check (preference)
     - `year_ok: candidates.append`, `wrong_year: candidates_wrong_year.append`
     - `size > big_threshold: big_count += 1`
   - `if big_count > MULTI_FILE_MAX_COUNT: return NO_VIDEO`
   - priority: `candidates` → `candidates_wrong_year` → `ts_candidates` → `any_big_files` → `NO_VIDEO`

**Проверка:** см. stub — тест с фейковым `torrent_info`:
```python
from unittest.mock import MagicMock
from services.torrent.session.file_picker import FilePicker, NO_VIDEO

info = MagicMock()
info.files().num_files.return_value = 1
info.files().file_path.return_value = "movie.mp4"
info.files().file_size.return_value = 2 * 1024**3
fp = FilePicker(year="2023")
assert fp.pick(info) == 0

info.files().file_size.return_value = 100 * 1024**2  # < 20 MB? нет, 100 MB ok
assert fp.pick(info) == 0

info.files().file_size.return_value = 10 * 1024**2  # < 20 MB
assert fp.pick(info) == NO_VIDEO
```

---

## Phase 3: Session components

### T-3.1: `services/torrent/session/handle_info.py`

**Время:** 4 min
**Файлы:** `services/torrent/session/handle_info.py` (create)
**Зависит от:** —

**Шаги:**
1. `@dataclass(slots=True) class HandleInfo` с полями:
   ```python
   handle: lt.torrent_handle
   save_dir: str
   title: str
   source_type: str
   seeders_declared: int
   size_declared: int
   first_seen: float = 0.0
   first_piece_seen: float = 0.0
   file_idx: int = -1
   first_piece: int = -1
   piece_length: int = 0
   last_rate: int = 0
   last_peers: int = 0
   last_has_first: bool = False
   ```
2. `key` property — `id(self.handle)`
3. `is_rejected` property — `file_idx < 0 and first_piece == -2`
4. `mark_rejected()` — `file_idx = -1; first_piece = -2`

**Проверка:**
```python
from unittest.mock import MagicMock
from services.torrent.session.handle_info import HandleInfo
h = MagicMock()
info = HandleInfo(handle=h, save_dir="/tmp", title="X", source_type="magnet",
                  seeders_declared=10, size_declared=1024**3)
assert info.is_rejected is False
info.mark_rejected()
assert info.is_rejected is True
```

---

### T-3.2: `services/torrent/session/handle_registry.py`

**Время:** 6 min
**Файлы:** `services/torrent/session/handle_registry.py` (create)
**Зависит от:** T-3.1

**Шаги:**
1. `class HandleRegistry`:
   - `_handles: dict[int, HandleInfo] = {}`
   - `_by_hash: dict[str, lt.torrent_handle] = {}`
2. `add(handle, save_dir, title, source_type, seeders, size) -> HandleInfo`:
   - создать `HandleInfo` с `first_seen=time.time()`
   - `_handles[info.key] = info`
   - `_by_hash[str(handle.info_hash())] = handle` в try/except
3. `register_hash(hash_str, handle)`, `find_by_hash(hash_str)`
4. `all() -> list[HandleInfo]` — `list(self._handles.values())`
5. `get(handle)`, `get_by_key(key)`, `__len__`, `__iter__` (iter list)
6. `remove(handle)`, `clear()`

**Проверка:**
```python
from unittest.mock import MagicMock
from services.torrent.session.handle_registry import HandleRegistry
r = HandleRegistry()
h = MagicMock()
h.info_hash.return_value = "abc"*13  # строка
r.add(h, "/tmp", "X", "magnet", 10, 1024**3)
assert len(r) == 1
assert r.find_by_hash("abc"*13) is h
```

---

### T-3.3: `services/torrent/session/source_loader.py`

**Время:** 15 min
**Файлы:** `services/torrent/session/source_loader.py` (create)
**Зависит от:** T-3.2, T-2.4, T-2.2

**Шаги:**
1. `class SourceLoader(http_session, lt_session, registry, file_picker, on_prioritize)`:
   - сохранить все в self
2. `async load(source, save_dir, is_primary=False) -> (HandleInfo, bool) | None`:
   - `is_magnet = url.startswith("magnet:")`
   - `params = await _parse_source(url, is_magnet)`, если None — return None
   - `pre = _pre_merge(params, is_magnet, url)`, если не None — return `(pre, False)`
   - `handle = _add_torrent(params, save_dir)`, если None — return None
   - `if not is_magnet and params.ti: if not _initial_pick(handle, params.ti):
     async_remove_torrent(handle); return None`
   - `info = registry.add(handle, save_dir, title, "magnet"/"torrent_url", seeders, size)`
   - `if is_magnet: for tr in extract_trackers(url): handle.add_tracker({"url": tr, "tier": 0})` в try/except
   - return `(info, True)`
3. `async _parse_source(url, is_magnet)`:
   - magnet: `lt.parse_magnet_uri(url)` в try/except
   - torrent_url: `_download_torrent(url)`, если `data[:7] == b"magnet:"` — decode → parse_magnet_uri; если `data[:1] != b"d"` — None; else `params = lt.add_torrent_params(); params.ti = lt.torrent_info(data)`
4. `async _download_torrent(url) -> bytes | None` — aiohttp GET, `allow_redirects=False`, 301/302 → Location; 200 → read
5. `_pre_merge(params, is_magnet, url) -> HandleInfo | None`:
   - `pre_hash = str(params.info_hash) если magnet, иначе str(params.ti.info_hash())`
   - `existing = registry.find_by_hash(pre_hash)`
   - `if not existing or not existing.is_valid(): return None`
   - `trackers = extract_trackers(url) если magnet, иначе [tr.url for tr in params.ti.trackers()]`
   - `for tr in trackers: existing.add_tracker({"url": tr, "tier": 0})` (если у existing есть метод — а handle имеет)
   - return existing
6. `_add_torrent(params, save_dir) -> handle | None`:
   - `params.save_path = save_dir`
   - `params.storage_mode = lt.storage_mode_t.storage_mode_sparse`
   - `params.flags |= lt.torrent_flags.auto_managed`
   - `params.flags &= ~lt.torrent_flags.paused`
   - `lt_session.add_torrent(params)` в try/except
7. `_initial_pick(handle, ti) -> bool`:
   - `file_idx = file_picker.pick(ti)`
   - `if RETRY: return True`
   - `if NO_VIDEO or < 0: return False`
   - `info = registry.get(handle); info.file_idx = file_idx;
      info.piece_length = ti.piece_length();
      info.first_piece = on_prioritize(handle, ti, file_idx)`
   - return True

**Проверка:** с реальным `.torrent` файлом (локальный magnet) — load возвращает `(HandleInfo, True)`. Без сети — `(None)`.

---

### T-3.4: `services/torrent/session/ready_detector.py`

**Время:** 15 min
**Файлы:** `services/torrent/session/ready_detector.py` (create)
**Зависит от:** T-3.2, T-2.4

**Шаги:**
1. `class ReadyDetector(registry, file_picker, on_prioritize, on_kill)`:
   - `grace = config.STREAM_READY_GRACE_PERIOD_SEC` (10.0)
   - `margin = config.STREAM_READY_BEST_SCORE_MARGIN` (2.0)
   - `kill_dead = config.STREAM_KILL_DEAD_HANDLE_SEC` (10.0)
   - `kill_meta = config.STREAM_KILL_DEAD_META_SEC` (60.0)
   - `kill_no_first = config.STREAM_KILL_NO_FIRST_PIECE_SEC` (45.0)
   - `min_rate = config.PROBE_MIN_RATE_MB * 1024 * 1024` (0.2 MB)
   - `min_peers = config.PROBE_MIN_PEERS` (10)
   - `poll_sec = 1.0`
2. `async detect(timeout=30, cancelled_check) -> HandleInfo | None`:
   - `start = time.time()`
   - `first_ready_ts = None`, `best_info = None`, `best_score = -1.0`, `best_key = -1`
   - loop `while time - start < timeout and not cancelled_check()`:
     - `await asyncio.sleep(poll_sec)`
     - `_kill_dead(now)`
     - `winner = _score_round(); if None: continue`
     - `info, score = winner`
     - `if first_ready_ts is None: first_ready_ts = now; best_info = info; best_score = score; best_key = info.key`
     - `elif score > best_score * margin: if info.key != best_key: best_info = info; best_score = score; best_key = info.key; first_ready_ts = now; else: best_score = score`
     - `elapsed = now - first_ready_ts`
     - `if elapsed >= grace and _pending_no_meta() == 0: return best_info`
     - `elif elapsed >= grace * 2: return best_info`
   - return `best_info` (может быть None)
3. `_score_round() -> (HandleInfo, float) | None`:
   - для каждого info: skip rejected, `handle.is_valid()`, `handle.has_metadata()`
   - `if info.file_idx == -1 or info.piece_length == 0:`
     - `ti = handle.get_torrent_info()`
     - `file_idx = file_picker.pick(ti)`
     - RETRY: continue; NO_VIDEO: mark_rejected; negative: mark_rejected
     - else: `info.file_idx = file_idx; info.first_piece = on_prioritize(handle, ti, file_idx); info.piece_length = ti.piece_length()`
   - `st = handle.status(); peers = st.num_peers; rate = int(st.download_payload_rate or 0)`
   - `if peers < 1: continue`
   - `has_first = handle.have_piece(info.first_piece) if info.first_piece >= 0 else False`
   - `is_ready = has_first or (rate > min_rate and peers >= min_peers)`
   - `piece_mult = _piece_multiplier(piece_length)`
   - `score = (rate / 1024.0) * (1.0 + math.log10(max(1, peers))) * (1.5 if is_ready else 1.0) * piece_mult`
   - best
4. `_piece_multiplier(piece_len) -> float` — ≤1MB: 1.2, ≤2MB: 1.0,
   ≤4MB: 0.7, ≤8MB: 0.4, else 0.2
5. `_kill_dead(now)`:
   - `if has_meta and not rejected:` if `peers == 0 and total_done == 0 and age > kill_dead` → remove;
     if `fp_age > kill_no_first` → remove
   - `elif not has_meta: if age > kill_meta: remove`
   - `on_kill(info.handle); registry.remove(info.handle)`
6. `_pending_no_meta() -> int` — count handles без metadata но с peers > 0

**Проверка:** с одним magnet и пирами → detect(30, ...) возвращает HandleInfo; с 12 мёртвыми → через 30s `None`.

---

### T-3.5: `services/torrent/peer_monitor.py`

**Время:** 8 min
**Файлы:** `services/torrent/peer_monitor.py` (create)
**Зависит от:** T-0.3

**Шаги:**
1. `@dataclass class PeerStats` — `total_peers, connected_peers, peers_with_piece,
   top_peer_rates, sum_top_rates, payload_rate, total_done, timestamp`
2. `class PeerMonitor(geometry, interval=None)`:
   - `interval = interval or config.PEER_MONITOR_INTERVAL_SEC`
   - `latest = PeerStats()`, `_task = None`, `_running = False`
3. `start()` — `create_task(_loop())`
4. `async _loop()`:
   - `while _running and geometry.handle: await asyncio.sleep(interval); latest = _collect()`
5. `_collect() -> PeerStats`:
   - `st = handle.status()` — `total_peers`, `payload_rate`, `total_done`
   - `peer_info = handle.get_peer_info()`
   - фильтр `connecting/handshake`, `connected += 1`, `rate = p.payload_down_speed`
   - `peers_with_piece` — `p.pieces.get_bit(current_piece)`
   - top N rates (`PEER_MONITOR_TOP_N=5`)
6. `stop()` — `_running = False`, `_task.cancel()`

**Проверка:** после старта с активным торрентом `monitor.latest.connected_peers >= 0`.

---

## Phase 4: HTTP Range Server

### T-4.1: `services/torrent/http_range_server.py` — setup + range

**Время:** 12 min
**Файлы:** `services/torrent/http_range_server.py` (create)
**Зависит от:** T--1.2, T-3.3

**Шаги:**
1. `_RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)')`
2. `class HttpRangeServer(session)`:
   - `host = "127.0.0.1"`, `port = 0`
   - `_runner = None`, `_site = None`, `_allowed_hosts = set()`
   - `_cache: OrderedDict[int, bytes] = OrderedDict()`
   - `_cache_limit = config.HTTP_RANGE_CACHE_PIECES`
   - `chunk_size = config.HTTP_RANGE_CHUNK_SIZE`
   - `poll_sec = config.HTTP_RANGE_POLL_SEC`
3. `async start() -> str`:
   ```python
   app = web.Application()
   app.router.add_get("/stream", self._handle_stream)
   app.router.add_get("/health", self._handle_health)
   self._runner = web.AppRunner(app)
   await self._runner.setup()
   self._site = web.TCPSite(self._runner, self.host, self.port)
   await self._site.start()
   socks = self._site._server.sockets
   if socks:
       self.port = socks[0].getsockname()[1]
   self._allowed_hosts = {
       f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"[::1]:{self.port}",
   }
   return f"http://{self.host}:{self.port}/stream"
   ```
4. `_check_host(request) -> bool`:
   - `host = request.headers.get("Host", "")`
   - `if not host: return False`
   - `return host in self._allowed_hosts`
5. `_parse_range(header, file_size) -> (int, int) | (None, None)`:
   - `m = _RANGE_RE.match(header.strip())`
   - suffix `bytes=-N`: `start = max(0, file_size - N), end = file_size - 1`
   - start-end: `start = int(start_s)`, `end = int(end_s) if end_s else file_size - 1`
   - `end = min(end, file_size - 1)`
   - `if start > end or start >= file_size: return None, None`
6. `_cache_get(piece)`, `_cache_put(piece, data)` — OrderedDict с move_to_end

**Проверка:**
```python
from services.torrent.http_range_server import HttpRangeServer
assert HttpRangeServer._parse_range("bytes=0-99", 1000) == (0, 99)
assert HttpRangeServer._parse_range("bytes=-100", 1000) == (900, 999)
assert HttpRangeServer._parse_range("bytes=2000-", 1000) == (None, None)
```

---

### T-4.2: `_handle_stream`

**Время:** 15 min
**Файлы:** `services/torrent/http_range_server.py` (append)
**Зависит от:** T-4.1

**Шаги:**
1. `if not _check_host(request): return web.Response(status=403)`
2. `session = self.session; if not session.is_active(): return 503`
3. `file_size = session.file_size`
4. `if range_header: start, end = _parse_range(...); if start is None:
   raise web.HTTPRequestRangeNotSatisfiable(headers={"Content-Range": f"bytes */{file_size}"}); status = 206`
5. `else: start, end = 0, file_size - 1; status = 200`
6. `headers = {"Content-Type": session.content_type, "Accept-Ranges": "bytes",
   "X-Content-Type-Options": "nosniff"}` + `Content-Range` если 206
7. `response = web.StreamResponse(status, headers); await response.prepare(request)`
8. `if start > 0: session.scheduler.on_seek(start)`
9. loop:
   ```python
   transport = request.transport
   current = start
   bytes_left = end - start + 1
   current_piece = -1
   current_data = b""
   data_offset = 0
   current_piece_byte_start = -1
   current_piece_byte_end = -1

   def is_client_alive():
       return transport is not None and not transport.is_closing()

   while bytes_left > 0:
       if not session.is_active(): break
       if not is_client_alive(): break

       if (current_piece >= 0
               and current_piece_byte_start <= current < current_piece_byte_end):
           piece = current_piece
       else:
           piece = session.geometry.piece_for_byte(current)
           if piece < 0:
               await asyncio.sleep(self.poll_sec); continue

       if piece != current_piece:
           session.scheduler.on_position(current)
           ok = await session.wait_for_piece(piece, is_client_alive)
           if not ok: break
           data = self._cache_get(piece)
           if data is None:
               data = await session.read_piece(piece)
               if data is None:
                   await asyncio.sleep(self.poll_sec); continue
               self._cache_put(piece, data)
           current_piece = piece
           current_data = data
           ps, pe = session.geometry.byte_range_for_piece(piece)
           current_piece_byte_start, current_piece_byte_end = ps, pe
           data_offset = max(0, current - ps)

       available = len(current_data) - data_offset
       if available <= 0:
           current_piece = -1; current_piece_byte_start = -1; current_piece_byte_end = -1
           continue

       this_chunk = min(self.chunk_size, bytes_left, available)
       data_out = current_data[data_offset:data_offset + this_chunk]
       try:
           await response.write(data_out)
       except (ConnectionResetError, ConnectionAbortedError):
           break
       current += len(data_out)
       data_offset += len(data_out)
       bytes_left -= len(data_out)

   if bytes_left == 0:
       try: await response.write_eof()
       except Exception: pass
   ```
10. catch `ConnectionReset/Aborted/CancelledError` → break
11. `async stop()` — `await _runner.cleanup()`, clear cache

**Проверка:** с реальным магнитом — `curl -r 0-1048575 http://127.0.0.1:PORT/stream` → 206 + 1 MB.

---

## Phase 5: StreamSession

### T-5.1: `__init__` + `start()` — часть 1

**Время:** 15 min
**Файлы:** `services/torrent/session/stream_session.py` (create)
**Зависит от:** Phase 3, Phase 4

**Шаги:**
1. `class StreamSession`:
   - Константы класса:
     ```python
     MAX_SOURCES = config.STREAM_MAX_SOURCES  # 12
     READY_TIMEOUT = 30.0
     PRIORITY_TOP = 7
     DEADLINE_FIRST_PIECES = 3
     HANDLE_REMOVAL_TIMEOUT = 15.0
     HANDLE_REMOVAL_POLL = 0.02
     ```
2. `__init__(http_session, downloads_dir, libtorrent_session, progress_cb=None, finished_cb=None, failed_cb=None)`:
   ```python
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
   self.registry = HandleRegistry()
   self.file_picker = FilePicker()
   self.geometry = PieceGeometry()
   self.scheduler = PieceScheduler(self.geometry)
   self.monitor = PeerMonitor(self.geometry)
   self.http_server = None
   self.piece_streamer = PieceStreamer(
       geometry=self.geometry, scheduler=self.scheduler,
       handle_getter=lambda: self.handle,
       file_path_getter=lambda: self.file_path,
   )
   self.alert_pump = AlertPump(self.session, self.piece_streamer.on_read_piece_alert)
   self._loader = None
   ```

**Проверка:** `StreamSession(...)` создаётся без ошибок.

---

### T-5.2: `start()` — часть 2

**Время:** 15 min
**Файлы:** `stream_session.py` (append)
**Зависит от:** T-5.1

**Шаги:**
1. `async start(sources, year="")`:
   ```python
   if not sources: self._fail("Список источников пуст"); return
   self._year = (year or "").strip()
   self.downloads_dir = self._create_session_dir()
   self.file_picker = FilePicker(self._year)
   self._loader = SourceLoader(
       self.http_session, self.session, self.registry,
       self.file_picker, self._prioritize,
   )
   self.alert_pump.start()
   dynamic_trackers = await self._load_trackers()
   language = config.SEARCH_LANGUAGE
   selector = SourceSelector(year, language=language)
   primary, alternatives = selector.select(sources)
   self.alternatives = alternatives
   if primary is None: self._fail("Нет подходящих источников"); return
   candidates = ([primary] + alternatives)[:self.MAX_SOURCES]
   groups = group_sources_by_hash(candidates, extra_trackers=dynamic_trackers)
   unique = self._dedup_and_merge(groups, dynamic_trackers)
   log.info("Session state before add: %d torrents", len(self.session.get_torrents()))
   await self._load_sources(unique)
   log.info("Session state after add: %d, registry=%d",
            len(self.session.get_torrents()), len(self.registry))
   if len(self.registry) == 0: self._fail("Не удалось добавить ни один источник"); return
   if config.STREAM_SEQUENTIAL_DOWNLOAD:
       for info in self.registry:
           try: info.handle.set_sequential_download(True)
           except Exception: pass
   detector = ReadyDetector(self.registry, self.file_picker, self._prioritize, self._kill_handle)
   winner = await detector.detect(self.READY_TIMEOUT, cancelled_check=lambda: self._cancelled)
   if winner is None:
       if not self._cancelled: self._fail(f"Ни один из {len(self.registry)} не начал качать")
       return
   if not self._activate_winner(winner): return
   self._ready = True
   self.monitor.start()
   if self.finished_cb:
       try: self.finished_cb(self)
       except Exception as e: log.exception("finished_cb: %s", e)
   ```
2. `_load_trackers() -> list[str]` — `TrackerBalancer().get_trackers()`, log count
3. `_dedup_and_merge(groups, dynamic_trackers) -> list[dict]`:
   - `__`-prefixed key → append `srcs[0]`
   - иначе: merge `merge_magnets_in_group(srcs, extra=dynamic_trackers)`,
     `merged = dict(srcs[0]); merged["url"] = merged_url`
4. `_load_sources(unique)`:
   - для каждого с индексом `i`:
     `save_dir = downloads_dir / f"h{i:02d}"`, `os.makedirs`
     `result = await self._loader.load(src, save_dir, is_primary=(i==0))`
     если результат — log

**Проверка:** в логах `Taking N candidates`, `Session state before add: 0 torrents`, `Added [N/12] magnet → hXX`, `StreamSession ready`.

---

### T-5.3: `_activate_winner` + priorities

**Время:** 15 min
**Файлы:** `stream_session.py` (append)
**Зависит от:** T-5.2

**Шаги:**
1. `_activate_winner(winner) -> bool`:
   - `self.handle = winner.handle; self.downloads_dir = winner.save_dir`
   - `self.torrent_info = winner.handle.get_torrent_info()` в try/except
   - `self.file_idx = winner.file_idx`
   - `self.file_size = files.file_size(idx)`, `rel_path = files.file_path(idx)`
   - **path traversal:**
     ```python
     candidate = os.path.normpath(os.path.join(self.downloads_dir, rel_path))
     real_base = os.path.realpath(self.downloads_dir)
     real_target = os.path.realpath(candidate)
     if not (real_target == real_base or real_target.startswith(real_base + os.sep)):
         self._fail(f"Path traversal: {rel_path!r}"); return False
     self.file_path = real_target
     ```
   - `content_type` по ext
   - `geometry.configure(handle, file_idx, file_size, piece_length, num_pieces, file_offset_in_torrent)` — поля из `torrent_info.files().file_offset(idx)`
   - `_apply_full_priorities(handle, info, file_idx)`
   - `_remove_losers(winner.handle)`
   - `self.http_server = HttpRangeServer(self)`
   - return True
2. `_apply_full_priorities(handle, info, file_idx)`:
   - `n = info.files().num_files()`
   - `for i in range(n): handle.file_priority(i, PRIORITY_TOP if i == file_idx else 0)`
   - `first_piece = _prioritize(handle, info, file_idx, tail=True)`
   - `adaptive = _adaptive_startup_count()`
   - `scheduler.on_startup(first_piece, adaptive)`
3. `_remove_losers(winner_handle)`:
   - для каждого info в registry:
     - если `info.handle is winner_handle` — `kept += 1`, continue
     - если `not has_metadata` и `st.num_peers > 0` — `kept += 1`, continue
     - `session.async_remove_torrent(info.handle)`, `registry.remove`
4. `_prioritize(handle, info, file_idx, tail=False) -> int`:
   - `piece_len`, `offset = info.files().file_offset(file_idx)`
   - `first_piece = offset // piece_len`, `total = info.num_pieces()`
   - `head_count = 5 if not tail else DEADLINE_FIRST_PIECES (3)`
   - head: `piece_priority(7)`, `set_piece_deadline(2000 + i * 500)`
   - tail: `tail_count = PIECE_SCHEDULER_TAIL_COUNT (20)`,
     `tail_start = max(0, total - 20)`, `piece_priority(7)`, `set_piece_deadline(1000)`
   - return `first_piece`
5. `_adaptive_startup_count() -> int`:
   - `piece_len = geometry.piece_length or 1`
   - `target = config.STREAM_SESSION_ADAPTIVE_START_BYTES (8 MB)`
   - `from_bytes = max(1, target // piece_len)`
   - `min_p = config.STREAM_STARTUP_MIN_PIECES (30)`
   - `max_p = config.STREAM_STARTUP_MAX_PIECES (100)`
   - `return max(min_p, min(max_p, from_bytes))`
6. `_kill_handle(handle)` — `session.async_remove_torrent(handle)` в try/except

**Проверка:** `Torrent configured: file.mkv (X MB), piece=Y, offset=Z`,
`Startup: first_piece=N adaptive=M`.

---

### T-5.4: `cancel()` + `_wait_handles_removed` + `_cleanup_downloads`

**Время:** 20 min
**Файлы:** `stream_session.py` (append)
**Зависит от:** T-5.3

**Шаги:**
1. `async cancel()`:
   ```python
   self._cancelled = True
   self._ready = False
   self.piece_streamer.cancel_all()
   # pump НЕ стопаем — обрабатывает removals
   if self.monitor:
       try: self.monitor.stop()
       except Exception: pass
   if self.http_server:
       try: await self.http_server.stop()
       except Exception: pass
       self.http_server = None
   for info in self.registry:
       try: self.session.async_remove_torrent(info.handle)
       except Exception as e: log.debug("async_remove_torrent: %s", e)
   self.registry.clear()
   self.handle = None
   await self._wait_handles_removed()
   try: await self.alert_pump.stop()
   except Exception as e: log.debug("alert_pump.stop: %s", e)
   await self._cleanup_downloads()
   ```
2. `async _wait_handles_removed()`:
   ```python
   deadline = time.time() + self.HANDLE_REMOVAL_TIMEOUT
   while time.time() < deadline:
       try:
           remaining = len(self.session.get_torrents())
       except Exception:
           return
       if remaining == 0: return
       await asyncio.sleep(self.HANDLE_REMOVAL_POLL)
   # Sync fallback
   try: remaining_handles = list(self.session.get_torrents())
   except Exception: return
   if not remaining_handles: return
   log.warning("cancel: async_remove_torrent не удалил за %.1fs — sync remove для %d",
               self.HANDLE_REMOVAL_TIMEOUT, len(remaining_handles))
   for h in remaining_handles:
       try: self.session.remove_torrent(h)
       except Exception as e: log.debug("sync remove_torrent: %s", e)
   ```
3. `async _cleanup_downloads()`:
   ```python
   if not (self.downloads_dir and os.path.isdir(self.downloads_dir)):
       self.downloads_dir = ""; return
   path = self.downloads_dir
   self.downloads_dir = ""
   await asyncio.sleep(0.5)
   loop = asyncio.get_event_loop()
   try: await loop.run_in_executor(None, shutil.rmtree, path, True)
   except Exception as e: log.debug("rmtree %s: %s", path, e)
   ```
4. `_fail(msg)` — `log.error`, `failed_cb(msg)`
5. `_create_session_dir() -> str` — `os.makedirs(base, exist_ok=True)`, `{ts}_{rnd}`
6. Public API: `wait_for_piece`, `read_piece`, `is_active`, `is_buffering`,
   `buffering_duration`, `current_stream_pos`, `stats` — прокси к компонентам

**Проверка:** после close — либо `cancel: async_remove_torrent не удалил за 15.0s — sync remove для N handles` (sync fallback), либо ничего (успел); следующий start → `Session state before add: 0 torrents`.

---

## Phase 6: Integration

### T-6.1: `cascade._dispatch` — P2P branch

**Время:** 10 min
**Файлы:** `controllers/stream/cascade.py` (append)
**Зависит от:** T-5.4

**Шаги:**
1. В `_dispatch`:
   ```python
   p2p = [s for s in sources if s.get("type") in ("magnet", "torrent_url")]
   direct = [s for s in sources if s.get("type") == "direct_url"
             and s.get("indexer") not in ("balancer", "videocdn", "bwa")]
   c._p2p_fallback = p2p
   c._direct_fallback = direct
   if p2p:
       await c._stop_resources()
       if not c.libtorrent_session:
           c.on_failed("Libtorrent session не инициализирован"); return
       c.stream_session = StreamSession(
           http_session=c.session,
           downloads_dir=str(config.DOWNLOADS_DIR),
           libtorrent_session=c.libtorrent_session,
           progress_cb=c._update_bar,
           finished_cb=c.on_ready,
           failed_cb=c.on_failed,
       )
       await c.stream_session.start(p2p, year=year)
       return
   ```

**Проверка:** клик «Start streaming» в private → `StreamSession.start` вызывается.

---

### T-6.2: `stream_controller.on_ready` + `_start_http_and_play`

**Время:** 8 min
**Файлы:** `controllers/stream/stream_controller.py` (append)
**Зависит от:** T-6.1

**Шаги:**
1. `on_ready(session)`:
   - `if not session.http_server: on_failed("HTTP server не создан"); return`
   - `create_task(_start_http_and_play(session))`
2. `async _start_http_and_play(session)`:
   - `url = await session.http_server.start()`
   - `session._ready = True; session.monitor.start()`
   - `playback.play_url(url, _current_movie_id, _current_movie_title)`
   - `buffer.start_p2p(lambda: self.stream_session)`

**Проверка:** в логах `Стрим готов: http://127.0.0.1:PORT/stream`, потом `wait_piece 0: X.Xs`.

---

### T-6.3: `BufferMonitor` — stub + `start_p2p`

**Время:** 12 min
**Файлы:** `controllers/stream/buffer_monitor.py` (create — полный)
**Зависит от:** T-6.2

**Шаги:**
1. `class BufferMonitor(main_window, playback, on_fallback)`:
   - `INTERVAL_MS = config.STREAM_MONITOR_INTERVAL_MS` (1000)
   - `STOP_DELAY = config.STREAM_BUFFER_STOP_DELAY_SEC` (30)
   - `WATCHDOG_SEC = config.STREAM_BUFFERING_WATCHDOG_SEC` (25)
   - `WATCHDOG_RATE = config.STREAM_BUFFERING_WATCHDOG_RATE_MB` (0.3)
2. `start_p2p(stream_session_getter)`:
   - `_timer = QTimer(main_window)`, `setInterval(1000)`,
     `timeout.connect(lambda: self._check_p2p(getter))`, `start()`
3. `_check_p2p(getter)`:
   - `session = getter(); if not session or not playback: return`
   - `buffering = session.is_buffering()`, `stats = session.stats`, `buf_dur = session.buffering_duration()`
   - **Watchdog:**
     ```python
     if (buffering and buf_dur > WATCHDOG_SEC
             and stats.payload_rate / 1024 / 1024 < WATCHDOG_RATE):
         QTimer.singleShot(0, self._safe_stop_player)
         on_fallback(force=True)
         return
     ```
   - **Stop:** `if buffering and not _stopped: if _pending_since is None:
     _pending_since = time.time(); if time - _pending_since > STOP_DELAY:
     QTimer.singleShot(0, _safe_stop_player); _stopped = True`
   - **Reload:** `elif not buffering and _stopped: playback.reload_url();
     _stopped = False`
4. `_safe_stop_player()` — `playback.player.setSource(QUrl())` (без stop)
5. `stop()`, `mark_stopped()`

**Проверка:** `WATCHDOG: 25.0s, rate=0.1, peers=3 → fallback` при зависании; `Buffer 30s — stop` при долгой буферизации.

---

## Phase 7: Verify

### T-7.1: E2E P2P test

**Время:** 10 min

**Шаги:**
1. `python switch_mode.py private` (Plan 05 — если ещё нет, вручную записать `private` в `data/mode.txt`)
2. Запуск приложения
3. Поиск «Oppenheimer» → 50+ источников
4. «Start streaming» → в логах:
   - `Taking 12 candidates`
   - `Added [N/12]`
   - `wait_ready`
   - `First ready`
   - `StreamSession ready`
   - `http://127.0.0.1:PORT/stream`
5. Видео играет
6. Seek 10:00 → играет через 5 сек
7. Close → `Плеер закрыт, ресурсы освобождены`
8. Открыть снова → `Session state before add: 0 torrents`
9. Быстрое переключение (закрыл → сразу другой) → второй стрим запускается

**Проверка:** все 9 шагов.

---

### T-7.2: Failure modes

**Время:** 5 min

**Шаги:**
1. Мёртвый магнит (0 сидов) → `meta=N peers=0` 30s → `FAILED: Ни один из N не начал качать`
2. Отключить сеть во время стрима → watchdog или demux → fallback (Plan 03)
3. Закрыть во время `wait_ready` → `cancel()` → handles удалены за 15s

**Проверка:** ни один не крэшит.

---

### T-7.3: No zombies

**Время:** 2 min

**Шаги:**
1. После close — `tasklist | findstr amagi-player` — пусто
2. `tasklist | findstr python` — пусто (кроме терминала)

**Проверка:** процессы завершены.

---

## Чек-лист готовности плана

- [x] Phase -1 покрывает все зависимости Plan 01 (stubs + константы)
- [x] Все константы из `config.py` перечислены в T--1.2
- [x] Каждая задача ≤ 20 минут
- [x] Каждая задача имеет автономную проверку (команда или Python-тест)
- [x] Сигнатуры методов даны для критичных задач
- [x] Импорты указаны (или вытекают из файла)
- [x] Phase 7 Verify покрывает E2E + failure + zombies
- [x] Out of scope: fallback, Jackett, switch_mode
- [x] Key risk назван (Windows MF + libtorrent)
