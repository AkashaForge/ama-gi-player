# Plan 02: P2P Streaming via libtorrent + HTTP Range

> **Цель:** клик «Start streaming» в private → 12 магнитов добавлены →
> выбран победитель → HTTP Range сервер запущен → QMediaPlayer играет →
> seek работает → закрытие освобождает handles за ≤ 15s.
>
> **Зависимости:** Plan 01 (UI, StreamController skeleton, PlaybackController,
> config с базовыми путями).
>
> **Вне рамок:** fallback (Plan 03), Jackett/WebFetcher/nodriver (Plan 04),
> switch_mode (Plan 05).
>
> **Оценка:** 8–12 часов для джуна.
>
> **Главный риск:** libtorrent на Windows. QMediaPlayer держит file handle,
> libtorrent не может удалить torrent. Решается в `cancel()` через 15s polling
> + sync fallback (T-5.4).

---

## Содержание

- [Phase -1: Contracts & Stubs](#phase--1-contracts--stubs) — 1 задача
- [Phase 0: libtorrent session + geometry](#phase-0-libtorrent-session--geometry) — 3 задачи
- [Phase 1: Scheduler + PieceStreamer + AlertPump](#phase-1-scheduler--piecestreamer--alertpump) — 3 задачи
- [Phase 2: Selection](#phase-2-selection) — 4 задачи
- [Phase 3: Session components](#phase-3-session-components) — 5 задач
- [Phase 4: HTTP Range Server](#phase-4-http-range-server) — 2 задачи
- [Phase 5: StreamSession](#phase-5-streamsession) — 4 задачи
- [Phase 6: Integration](#phase-6-integration) — 3 задачи
- [Phase 7: Verify](#phase-7-verify) — 3 задачи

**Итого:** 28 задач, ~8–12 часов.

---

## Как читать этот план

Формат тот же, что в Plan 01: **Что делать** — шаги, **Проверка** — конкретная
команда или assert, **Инвариант** — что нельзя нарушить.

**Если застрял** — смотри T--1.1 (все константы), или Plan 01 (там stubs и
UI-skeleton). P2P зависит от Plan 01 — сначала выполни его.

---

## Phase -1: Contracts & Stubs

**Зачем:** добавить константы `config.py` для P2P и зависимость `libtorrent`.
Без этого `import libtorrent` падает, а `config.STREAM_MAX_SOURCES` —
`AttributeError`.

---

### T--1.1: `config.py` — все константы P2P

**Время:** 15 min
**Файлы:** `config.py` (append), `requirements.txt` (append)
**Зависит от:** T-0.3 (Plan 01)

**Что делать:**

1. **libtorrent в requirements:**
   ```
   libtorrent==2.1.1
   ```
   `pip install libtorrent==2.1.1`

2. **libtorrent session:**
   ```
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
   ```

3. **Piece scheduler:**
   ```
   PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS = 100
   PIECE_SCHEDULER_LOOKAHEAD_PIECES = 10
   PIECE_SCHEDULER_DEADLINE_STEP_MS = 150
   PIECE_SCHEDULER_TRAILING_RETENTION = 3
   PIECE_SCHEDULER_TAIL_DEADLINE_MS = 1000
   PIECE_SCHEDULER_DEADLINE_REFRESH_SEC = 5.0
   PIECE_SCHEDULER_TAIL_COUNT = 20
   ```

4. **Peer monitor + HTTP Range:**
   ```
   PEER_MONITOR_INTERVAL_SEC = 2.0
   PEER_MONITOR_TOP_N = 5
   HTTP_RANGE_CACHE_PIECES = 8
   HTTP_RANGE_POLL_SEC = 0.05
   HTTP_RANGE_CHUNK_SIZE = 1024 * 1024
   ```

5. **Stream session:**
   ```
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

6. **Source selector:**
   ```
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

7. **Tracker balancer:**
   ```
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
python -c "import libtorrent as lt; print(lt.__version__)"
python -c "import config; print(config.STREAM_MAX_SOURCES, config.PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS)"
# → 12 100
```

**Инвариант:** `PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS = 100`, не `0`.
`set_piece_deadline(piece, 0)` = «no deadline», libtorrent его игнорирует.

---

## Phase 0: libtorrent session + geometry

**Зачем:** создать session libtorrent и геометрию piece↔byte. После этой
фазы можно добавить торрент и узнать, какой piece нужен для байта X.

---

### T-0.1: `services/torrent/lt_session.py`

**Время:** 6 min
**Файлы:** `services/torrent/lt_session.py` (create)
**Зависит от:** T--1.1

**Что делать:**

1. `create_session(listen_port: int) -> lt.session`
2. `settings` dict из `config.LIBTORRENT_*`:
   - `listen_interfaces = f'0.0.0.0:{port},[::]:{port}'`
   - `enable_dht/lsd/upnp/natpmp = True`
   - `alert_mask = error | status | storage`
   - `smooth_connects`, `connection_speed`, `torrent_connect_boost`,
     `min_reconnect_time`, `peer_connect_timeout`, `piece_timeout`,
     `request_timeout`, `peer_timeout`, `cache_size`, `cache_expiry`
3. DHT routers: `router.bittorrent.com`, `router.utorrent.com`,
   `dht.transmissionbt.com`, `dht.libtorrent.org` — `add_dht_router(host, 6881)`
   в try/except (не падать, если недоступен)
4. return `ses`

**Проверка:**

```bash
python -c "from services.torrent.lt_session import create_session; s = create_session(6881); print(len(s.get_torrents()))"
# → 0
```

**Инвариант:** DHT routers — не критичны. Если `add_dht_router` бросает —
log + continue. Без DHT торрент может работать через трекеры, но хуже.

---

### T-0.2: `services/torrent/piece_map.py`

**Время:** 6 min
**Файлы:** `services/torrent/piece_map.py` (create)
**Зависит от:** —

**Что делать:**

1. `class PieceGeometry` с полями: `handle`, `file_idx`, `file_size`,
   `piece_length`, `num_pieces`, `file_offset_in_torrent`, `current_piece`
2. `configure(handle, file_idx, file_size, piece_length, num_pieces,
   file_offset_in_torrent)` — присваивание, `current_piece = -1`
3. `piece_for_byte(byte_pos) -> int`:
   - `if not handle or piece_length <= 0: return -1`
   - `absolute_byte = file_offset_in_torrent + byte_pos`
   - `if absolute_byte < 0: return -1`
   - `piece = absolute_byte // piece_length`
   - `if piece < 0 or piece >= num_pieces: return -1`
   - return piece
4. `byte_range_for_piece(piece) -> (int, int)`:
   - `piece_start_in_torrent = piece * piece_length`
   - `piece_end_in_torrent = piece_start_in_torrent + piece_length`
   - `file_start = file_offset_in_torrent`, `file_end = file_start + file_size`
   - `overlap_start = max(piece_start_in_torrent, file_start)`
   - `overlap_end = min(piece_end_in_torrent, file_end)`
   - `if overlap_start >= overlap_end: return -1, -1`
   - `return (overlap_start - file_start, overlap_end - file_start)`
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
assert g.byte_range_for_piece(3) == (768, 1000)
```

**Инвариант:** `piece_for_byte` — **арифметика**, не
`handle.torrent_file().map_file()`. `map_file` — C++ вызов на hot path
(HTTP Range), тормоза. Формула эквивалентна, но без перехода в C++.

---

### T-0.3: `services/torrent/__init__.py` + `session/__init__.py`

**Время:** 2 min
**Файлы:** `services/torrent/__init__.py`, `services/torrent/session/__init__.py`
**Зависит от:** T-0.1

**Что делать:**

1. `services/torrent/__init__.py` — пустой
2. `services/torrent/session/__init__.py` — пустой (заполнится в T-5.5)

**Проверка:**

```bash
python -c "import services.torrent, services.torrent.session; print('ok')"
```

---

## Phase 1: Scheduler + PieceStreamer + AlertPump

**Зачем:** три компонента, которые обеспечивают «скачать piece N и отдать
его». Scheduler — приоритизация. PieceStreamer — ожидание и чтение.
AlertPump — фоновый цикл `pop_alerts`.

---

### T-1.1: `services/torrent/piece_scheduler.py`

**Время:** 15 min
**Файлы:** `services/torrent/piece_scheduler.py` (create)
**Зависит от:** T--1.1, T-0.2

**Что делать:**

1. `class PieceScheduler(geometry)`:
   - `_current_piece = -1`, `_current_byte_pos = 0`
   - `DEADLINE_HEAD_MS = max(100, config.PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS)`
   - `LOOKAHEAD`, `DEADLINE_STEP_MS`, `TRAILING_RETENTION`,
     `TAIL_DEADLINE_MS` — из config
   - `PRIORITY_TOP = 7`
2. `_set_high_priority(piece, deadline_ms)`:
   - `piece_priority(piece, 7)`
   - `if deadline_ms <= 0: deadline_ms = DEADLINE_HEAD_MS`
   - `set_piece_deadline(piece, deadline_ms)`
   - **оба вызова** в try/except
3. `_apply_deadlines(start_piece)` — для `i in range(LOOKAHEAD)`:
   `deadline = DEADLINE_HEAD_MS + i * DEADLINE_STEP_MS`, `_set_high_priority`
4. `on_position(byte_pos)`:
   - `piece = geometry.piece_for_byte(byte_pos)`
   - `if piece < 0 or piece == _current_piece: return`
   - `_current_piece = piece`, `geometry.current_piece = piece`
   - `_apply_deadlines(piece)`
   - trailing: `for i in range(1, TRAILING_RETENTION + 1):
     _set_high_priority(piece - i, TAIL_DEADLINE_MS)`
5. `on_seek(byte_pos)`:
   - `handle.clear_piece_deadlines()` в try/except
   - `_current_piece = -1`
   - `on_position(byte_pos)`
6. `force_deadline(piece, lookahead=None)`:
   - `la = lookahead if not None else LOOKAHEAD`
   - `for i in range(la): deadline = DEADLINE_HEAD_MS + i * DEADLINE_STEP_MS`
   - `_set_high_priority(piece + i, deadline)`
7. `on_startup(first_piece, adaptive_count)`:
   - `clear_piece_deadlines`
   - head: `for i in range(adaptive_count):
     _set_high_priority(first_piece + i, DEADLINE_HEAD_MS + i * DEADLINE_STEP_MS)`
   - tail: `tail_start = max(0, num_pieces - TAIL_COUNT)`,
     `for p in range(tail_start, num_pieces): _set_high_priority(p, TAIL_DEADLINE_MS)`

**Проверка:**

```python
from unittest.mock import MagicMock
from services.torrent.piece_map import PieceGeometry
from services.torrent.piece_scheduler import PieceScheduler

g = PieceGeometry()
h = MagicMock()
g.configure(h, 0, 10_000_000, 1_048_576, 10, 0)
s = PieceScheduler(g)
s.force_deadline(5, lookahead=3)
calls = [c.args for c in h.set_piece_deadline.call_args_list]
assert len(calls) == 3
assert calls[0][0] == 5 and calls[0][1] >= 100
```

**Инварианты:**
- `set_piece_deadline(piece, 0)` = «no deadline» — libtorrent игнорирует.
  Всегда положительный, минимум 100.
- `piece_priority` **и** `set_piece_deadline` — оба. Deadline без priority
  игнорируется, priority без deadline — не time-critical.
- `force_deadline` вызывается из `wait_for_piece` при **каждом** HTTP Range
  запросе. FFmpeg probe в середине файла не попадает в `on_position`, но
  deadline должен быть.

---

### T-1.2: `services/torrent/session/piece_streamer.py`

**Время:** 15 min
**Файлы:** `services/torrent/session/piece_streamer.py` (create)
**Зависит от:** T-1.1

**Что делать:**

1. `class PieceStreamer(geometry, scheduler, handle_getter, file_path_getter)`:
   - `_pending: dict[int, list[asyncio.Future]]`
   - `_buffering = False`, `_buffering_since = 0.0`
2. `is_buffering` property, `buffering_duration() -> float`
3. `async wait_for_piece(piece, is_client_alive=None, timeout=None) -> bool`:
   - `timeout = timeout or config.STREAM_WAIT_PIECE_TIMEOUT_SEC`
   - `refresh = config.PIECE_SCHEDULER_DEADLINE_REFRESH_SEC`
   - `scheduler.force_deadline(piece, lookahead=scheduler.LOOKAHEAD)` в try
   - `start = time.time(); last_force = start`
   - loop:
     - `if is_client_alive and not is_client_alive(): return False`
     - `if geometry.have_piece(piece): _buffering = False; return True`
     - `if not _buffering: _buffering = True; _buffering_since = time.time()`
     - `now = time.time()`
     - `if now - last_force > refresh: force_deadline; last_force = now`
     - `if now - start > timeout: return False`
     - `await asyncio.sleep(0.05)`
4. `async read_piece(piece) -> bytes | None`:
   - `start, end = geometry.byte_range_for_piece(piece)`
   - `if start < 0: return b""`
   - `handle = _handle_getter()`
   - `if handle: data = await _read_via_alert(handle, piece);
     if data is not None: return data`
   - `return await _read_file_fallback(start, size, piece)`
5. `async _read_via_alert(handle, piece)`:
   - `future = asyncio.get_event_loop().create_future()`
   - `lst = _pending.setdefault(piece, [])`
   - `if len(lst) >= PENDING_READS_MAX_PER_PIECE:
     old = lst.pop(0); old.cancel()`
   - `lst.append(future)`
   - `handle.read_piece(piece)` — sync, ~мкс, в try/except
   - `return await asyncio.wait_for(future, timeout=STREAM_READ_PIECE_TIMEOUT_SEC)`
   - finally: убрать future из `_pending[piece]`, если пусто — удалить
6. `async _read_file_fallback(start, size, piece)`:
   - `file_path = _file_path_getter(); if not file_path: return None`
   - `await run_in_executor(None, self._read_sync, file_path, start, size)`
   - `if data[:1024] == b"\x00" * 1024: return None`
7. `_read_sync(path, start, size) -> bytes | None` — sync `open/seek/read`
8. `on_read_piece_alert(alert)`:
   - `piece = alert.piece`, `lst = _pending.pop(piece, None)`
   - `if not lst: return`
   - `if alert.error and alert.error.value() != 0: data = None
     else: data = bytes(alert.buffer) if alert.buffer else None`
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
    assert result is False

asyncio.run(test())
```

**Инварианты:**
- `wait_for_piece` polling **50ms**, не 100ms. Отклик на появление piece
  быстрее в 2 раза.
- `handle.read_piece()` — sync вызов, но быстрый (ставит в очередь).
  Не блокирует event loop.
- `_read_file_fallback` через `run_in_executor` — иначе sync I/O
  блокирует loop.

---

### T-1.3: `services/torrent/session/alert_pump.py`

**Время:** 10 min
**Файлы:** `services/torrent/session/alert_pump.py` (create)
**Зависит от:** T-1.2

**Что делать:**

1. `class AlertPump(lt_session, on_read_piece)`:
   - `session`, `_on_read_piece`, `_task=None`, `_cancelled=False`
2. `start()`:
   - `if _task and not done: return`
   - `_cancelled = False; _task = asyncio.create_task(_loop())`
3. `async _loop()`:
   - `while not _cancelled and session:`
     - `alerts = session.pop_alerts()`
     - для каждого: `read_piece_alert` → `_on_read_piece`,
       `torrent_error_alert` → log
     - `except Exception: pass`
     - `await asyncio.sleep(0.1)`
4. `async stop()` — **async, не sync**:
   - `_cancelled = True`
   - `await asyncio.sleep(0.05)` — дать pump финальный `pop_alerts`
   - `if _task and not done: _task.cancel(); await _task`
   - `_task = None`

**Проверка:**

```python
import asyncio, libtorrent as lt
from services.torrent.session.alert_pump import AlertPump

async def test():
    ses = lt.session()
    pump = AlertPump(ses, lambda a: None)
    pump.start()
    await asyncio.sleep(0.2)
    await pump.stop()
    assert pump._task is None

asyncio.run(test())
```

**Инвариант:** `stop()` — **async**, с `sleep(0.05)` перед `cancel()`.
Если сразу `task.cancel()`, pump не успеет обработать pending removals,
они останутся в очереди libtorrent. Это критично для `cancel()` в T-5.4.

---

## Phase 2: Selection

**Зачем:** выбрать лучший источник из N, сгруппировать магниты по info_hash,
подгрузить трекеры, выбрать видеофайл в торренте.

---

### T-2.1: `services/torrent/source_selector.py`

**Время:** 20 min
**Файлы:** `services/torrent/source_selector.py` (create)
**Зависит от:** T--1.1, Plan 01 T-2.1 (`is_safe_release`)

**Что делать:**

1. `_HARD_REJECT_RE` — regex `\b(?:camrip|cam-rip|hdcam|hdts|tsrip|ts-rip|
   telesync|telecine|screener|scr|dvdscr)\b`, IGNORECASE
2. `_health_component(seeders, peers) -> float`:
   - `if seeders <= 0: return 0.0`
   - `ratio = seeders / max(1, peers)`
   - `norm_ratio = min(ratio / 5.0, 1.0)`
   - `norm_seeds = min(seeders / 200.0, 1.0)`
   - `return norm_ratio * 0.4 + norm_seeds * 0.6`
3. `_resolution_component(title)` — 2160p/4k → `SCORE_BONUS_2160P`,
   1080p → `SCORE_BONUS_1080P`, 720p → `SCORE_BONUS_720P`, else 0
4. `_source_component(title)` — bluray/bdremux → `SCORE_BONUS_BLURAY`,
   web-dl → `SCORE_BONUS_WEB_DL`, webrip/bdrip → 0.05, hdrip → -0.05
5. `_codec_component(title)` — hevc/h265/x265 → `SCORE_BONUS_HEVC`
6. `_trusted_component(source)` — indexer in (yts, rarbg, eztv, torrentapi)
   → 0.10
7. `_is_hard_reject(title, size) -> bool`:
   - `if not title: return True`
   - `if _HARD_REJECT_RE.search(title): return True`
   - `if not is_safe_release(title, size): return True`
   - return False
8. `class SourceSelector(year, language)`:
   - `_score(source) -> float`:
     - `score = health * W_HEALTH + res * W_RESOLUTION + src * W_SOURCE
       + codec * W_CODEC + trusted * W_TRUSTED` (веса из config)
     - penalties: telesync, cam, ts (без telesync), screener/dvdscr
     - `round(score, 4)`
   - `rank(sources) -> list[dict]`:
     - filter `_is_hard_reject`, `s["_score"] = _score(s)`
     - sort desc, log top 15
   - `select(sources) -> (dict | None, list[dict])`:
     - `ranked = rank(sources)`
     - `if not ranked: return None, []`
     - `return ranked[0], ranked[1:1 + MAX_ALTERNATIVES]`

**Проверка:**

```python
from services.torrent.source_selector import SourceSelector
s = SourceSelector(year="2023", language="en")
ranked = s.rank([
    {"title": "Movie 1080p BluRay x265", "seeders": 500, "leechers": 10},
    {"title": "Movie CAM", "seeders": 5000, "leechers": 0},
])
assert len(ranked) == 1
assert ranked[0]["_score"] > 0
```

**Инвариант:** hard-reject **до** скоринга. CAM с 5000 сидов не должен
обогнать 1080p BluRay с 500 — regex отбрасывает его раньше, чем считается
score.

---

### T-2.2: `services/torrent/swarm_grouper.py`

**Время:** 12 min
**Файлы:** `services/torrent/swarm_grouper.py` (create)
**Зависит от:** T--1.1

**Что делать:**

1. `_BTIH_RE` — regex `btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})`, IGNORECASE
2. `_TR_RE` — `[?&]tr=([^&]+)`
3. `_HASH_IN_URL_RE` — `\b([a-fA-F0-9]{40})\b`
4. `_TORRENT_URL_HINTS = (".torrent", "/download/", "/dl/", "/torrent/")`
5. `DEFAULT_TRACKERS_FALLBACK` — 7 UDP/HTTP-трекеров (opentrackr,
   open.demonii, openbittorrent, exodus.desync, torrent.eu.org, coppersurfer,
   leechers-paradise)
6. `extract_info_hash(url) -> str | None`:
   - magnet → `_BTIH_RE.search`, если 40 → lower, если 32 → `b32decode().hex()`
   - torrent URL с hints → `_HASH_IN_URL_RE.search`
7. `extract_trackers(url) -> list[str]` — `_TR_RE.findall`
8. `_merge_trackers(existing, extra)` — union, dedup (порядок: existing + new)
9. `enrich_magnet_with_default_trackers(url, extra)` — если trackers < 5,
   добавить до 5
10. `group_sources_by_hash(sources, extra_trackers) -> dict[str, list[dict]]`:
    - `__orphan_N` для без hash
    - log multi-swarm groups (top 5 по размеру)
11. `merge_magnets_in_group(sources, extra_trackers) -> str`:
    - base magnet — первый
    - union trackers, добавить до 5 fallback

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
**Зависит от:** T--1.1

**Что делать:**

1. `DEFAULT_TRACKERS_FALLBACK` — тот же, что в T-2.2 (можно импортировать
   из `swarm_grouper`)
2. `_is_safe_balancer_url(url) -> bool`:
   - `url.startswith(("http://", "https://"))`
   - `host = urlparse(url).hostname`
   - блок: localhost, 127.0.0.1, 0.0.0.0, ::1, `10.*`, `192.168.*`,
     `172.16-31.*`
3. `_is_valid_tracker(t)` — scheme in (udp, http, https, wss)
4. `class TrackerBalancer`:
   - `_trackers = []`, `_loaded_at = 0.0`,
     `_ttl = config.TRACKER_BALANCER_TTL_HOURS * 3600`
   - `async get_trackers() -> list[str]`:
     - TTL in memory → return
     - cache file TTL → return
     - `_load_urls()` → `_download_all()` → `_write_file()` → return
     - если пусто — `DEFAULT_TRACKERS_FALLBACK`
   - `_load_urls() -> list[str]` — читает `TRACKER_BALANCERS_FILE`,
     `_is_safe_balancer_url`, cap `MAX_URLS`
   - `async _download_one(url)` — aiohttp GET, timeout 10, cap bytes,
     SSL verify
   - `async _download_all(urls)` — `asyncio.gather`, union, filter
     `_is_valid_tracker`, cap `MAX_TRACKERS`
   - `_read_file`, `_write_file`, `reload()`

**Проверка:**

```python
import asyncio
from services.torrent.tracker_balancer import TrackerBalancer

async def test():
    tb = TrackerBalancer()
    trackers = await tb.get_trackers()
    assert len(trackers) >= 7

asyncio.run(test())
```

**Инвариант:** `_is_safe_balancer_url` блокирует RFC1918 — иначе
`tracker_balancers.txt` с `http://127.0.0.1:8080/secret` сделает запрос
к внутреннему сервису (SSRF).

---

### T-2.4: `services/torrent/session/file_picker.py`

**Время:** 12 min
**Файлы:** `services/torrent/session/file_picker.py` (create)
**Зависит от:** T--1.1

**Что делать:**

1. `RETRY = -2` (metadata неполная), `NO_VIDEO = -1`
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
   - `num_files = info.files().num_files()`
   - `if num_files == 0: return RETRY` — metadata не готова, попробовать
     позже
   - `min_size = 20 MB`, `max_size = 100 GB`, `big_threshold = 5 GB`
   - цикл по файлам:
     - `size < min_size or size > max_size: continue`
     - `is_ts`: append в `ts_candidates`, continue (если `_allow_ts`)
     - `is_reject_ext`: continue
     - `not is_video`: append в `any_big_files`, continue
     - year check (preference): если year в имени совпадает → `candidates`,
       иначе → `candidates_wrong_year`
     - `size > big_threshold: big_count += 1`
   - `if big_count > MULTI_FILE_MAX_COUNT: return NO_VIDEO` — collection
   - priority: `candidates` (правильный год) → `candidates_wrong_year` →
     `ts_candidates` → `any_big_files` → `NO_VIDEO`

**Проверка:**

```python
from unittest.mock import MagicMock
from services.torrent.session.file_picker import FilePicker, NO_VIDEO

info = MagicMock()
info.files().num_files.return_value = 1
info.files().file_path.return_value = "movie.mp4"
info.files().file_size.return_value = 2 * 1024**3
fp = FilePicker(year="2023")
assert fp.pick(info) == 0

info.files().file_size.return_value = 10 * 1024**2  # < 20 MB
assert fp.pick(info) == NO_VIDEO
```

**Инвариант:** `RETRY` — не «нет видео», а «metadata не готова, попробовать
позже». `ReadyDetector` отличает: RETRY → skip (попробует в следующем
раунде), NO_VIDEO → mark_rejected (не пробует).

---

## Phase 3: Session components

**Зачем:** пять компонентов, из которых соберётся `StreamSession`. Каждый
отвечает за одно: состояние handle, реестр, загрузка источника, выбор
победителя, статистика пиров.

---

### T-3.1: `services/torrent/session/handle_info.py`

**Время:** 4 min
**Файлы:** `services/torrent/session/handle_info.py` (create)
**Зависит от:** —

**Что делать:**

1. `@dataclass(slots=True) class HandleInfo`:
   - `handle`, `save_dir`, `title`, `source_type`, `seeders_declared`,
     `size_declared`
   - `first_seen = 0.0`, `first_piece_seen = 0.0`
   - `file_idx = -1`, `first_piece = -1`, `piece_length = 0`
   - `last_rate = 0`, `last_peers = 0`, `last_has_first = False`
2. `key` property — `id(self.handle)`
3. `is_rejected` property — `file_idx < 0 and first_piece == -2`
4. `mark_rejected()` — `file_idx = -1`, `first_piece = -2`

**Проверка:**

```python
from unittest.mock import MagicMock
from services.torrent.session.handle_info import HandleInfo
h = MagicMock()
info = HandleInfo(handle=h, save_dir="/tmp", title="X",
                  source_type="magnet", seeders_declared=10,
                  size_declared=1024**3)
assert info.is_rejected is False
info.mark_rejected()
assert info.is_rejected is True
```

---

### T-3.2: `services/torrent/session/handle_registry.py`

**Время:** 6 min
**Файлы:** `services/torrent/session/handle_registry.py` (create)
**Зависит от:** T-3.1

**Что делать:**

1. `class HandleRegistry`:
   - `_handles: dict[int, HandleInfo] = {}`
   - `_by_hash: dict[str, lt.torrent_handle] = {}`
2. `add(handle, save_dir, title, source_type, seeders, size) -> HandleInfo`:
   - `HandleInfo(..., first_seen=time.time())`
   - `_handles[info.key] = info`
   - `_by_hash[str(handle.info_hash())] = handle` в try
3. `register_hash`, `find_by_hash`
4. `all() -> list[HandleInfo]` — `list(values())`
5. `get(handle)`, `get_by_key(key)`
6. `__len__`, `__iter__` — iter list (копия, не live)
7. `remove(handle)`, `clear()`

**Проверка:**

```python
from unittest.mock import MagicMock
from services.torrent.session.handle_registry import HandleRegistry

r = HandleRegistry()
h = MagicMock()
h.info_hash.return_value = "abc" * 13
r.add(h, "/tmp", "X", "magnet", 10, 1024**3)
assert len(r) == 1
assert r.find_by_hash("abc" * 13) is h
```

**Инвариант:** `__iter__` возвращает **копию** (`iter(list(values()))`).
Иначе `for info in registry` во время `registry.remove()` в цикле —
`RuntimeError: dict changed size during iteration`.

---

### T-3.3: `services/torrent/session/source_loader.py`

**Время:** 15 min
**Файлы:** `services/torrent/session/source_loader.py` (create)
**Зависит от:** T-3.2, T-2.2, T-2.4

**Что делать:**

1. `class SourceLoader(http_session, lt_session, registry, file_picker,
   on_prioritize)`
2. `async load(source, save_dir, is_primary=False) -> (HandleInfo, bool) | None`:
   - `is_magnet = url.startswith("magnet:")`
   - `params = await _parse_source(url, is_magnet)`, если None — return None
   - `pre = _pre_merge(params, is_magnet, url)`, если не None —
     `return (pre, False)`
   - `handle = _add_torrent(params, save_dir)`, если None — return None
   - `if not is_magnet and params.ti: if not _initial_pick(handle, params.ti):
     async_remove_torrent(handle); return None`
   - `info = registry.add(handle, save_dir, title, "magnet"/"torrent_url",
     seeders, size)`
   - `if is_magnet: for tr in extract_trackers(url):
     handle.add_tracker({"url": tr, "tier": 0})` в try
   - return `(info, True)`
3. `async _parse_source(url, is_magnet)`:
   - magnet → `lt.parse_magnet_uri(url)`
   - torrent_url → `_download_torrent(url)`:
     - `data[:7] == b"magnet:"` → parse_magnet_uri
     - `data[:1] != b"d"` → None (не bencode)
     - else → `params = lt.add_torrent_params();
       params.ti = lt.torrent_info(data)`
4. `async _download_torrent(url)` — aiohttp GET, `allow_redirects=False`,
   301/302 → Location, 200 → read
5. `_pre_merge(params, is_magnet, url) -> HandleInfo | None`:
   - `pre_hash = str(params.info_hash) если magnet, иначе
     str(params.ti.info_hash())`
   - `existing = registry.find_by_hash(pre_hash)`
   - `if not existing or not existing.is_valid(): return None`
   - `trackers = extract_trackers(url) если magnet, иначе
     [tr.url for tr in params.ti.trackers()]`
   - `for tr in trackers: existing.add_tracker(...)` в try
   - return existing
6. `_add_torrent(params, save_dir) -> handle | None`:
   - `params.save_path = save_dir`
   - `params.storage_mode = lt.storage_mode_t.storage_mode_sparse`
   - `params.flags |= lt.torrent_flags.auto_managed`
   - `params.flags &= ~lt.torrent_flags.paused`
   - `lt_session.add_torrent(params)` в try
7. `_initial_pick(handle, ti) -> bool`:
   - `file_idx = file_picker.pick(ti)`
   - `RETRY` → return True (попробует в ReadyDetector)
   - `NO_VIDEO` или `< 0` → return False
   - else: `info = registry.get(handle); info.file_idx = file_idx;
     info.piece_length = ti.piece_length();
     info.first_piece = on_prioritize(handle, ti, file_idx)`
   - return True

**Проверка:** с локальным `.torrent` файлом — `load` возвращает
`(HandleInfo, True)`. Повторный `load` того же hash → `(HandleInfo, False)`.

**Инварианты:**
- `storage_mode_sparse` — не преаллоцировать файл. Для 25 GB торрента
  преаллокация = 25 GB записи на диск.
- `flags &= ~paused` — не ставить на паузу. libtorrent по умолчанию
  может ставить paused.
- `pre_merge` — если hash уже есть, добавить trackers к существующему,
  не `add_torrent`. Иначе libtorrent вернёт «тень» существующего handle.

---

### T-3.4: `services/torrent/session/ready_detector.py`

**Время:** 15 min
**Файлы:** `services/torrent/session/ready_detector.py` (create)
**Зависит от:** T-3.2, T-2.4

**Что делать:**

1. `class ReadyDetector(registry, file_picker, on_prioritize, on_kill)`:
   - `grace = config.STREAM_READY_GRACE_PERIOD_SEC` (10.0)
   - `margin = config.STREAM_READY_BEST_SCORE_MARGIN` (2.0)
   - `kill_dead = config.STREAM_KILL_DEAD_HANDLE_SEC` (10.0)
   - `kill_meta = config.STREAM_KILL_DEAD_META_SEC` (60.0)
   - `kill_no_first = config.STREAM_KILL_NO_FIRST_PIECE_SEC` (45.0)
   - `min_rate = config.PROBE_MIN_RATE_MB * 1024 * 1024` (0.2 MB/s)
   - `min_peers = config.PROBE_MIN_PEERS` (10)
   - `poll_sec = 1.0`
2. `async detect(timeout=30, cancelled_check) -> HandleInfo | None`:
   - `start = time.time()`, `first_ready_ts = None`, `best_info = None`,
     `best_score = -1.0`, `best_key = -1`
   - loop `while time - start < timeout and not cancelled_check()`:
     - `await asyncio.sleep(1.0)`
     - `_kill_dead(now)`
     - `winner = _score_round(); if None: continue`
     - `info, score = winner`
     - `if first_ready_ts is None:` — запомнить как best
     - `elif score > best_score * margin:` — переключиться если лучше
       в `margin` раз
     - `elapsed = now - first_ready_ts`
     - `if elapsed >= grace and _pending_no_meta() == 0: return best_info`
     - `elif elapsed >= grace * 2: return best_info`
   - return `best_info`
3. `_score_round() -> (HandleInfo, float) | None`:
   - для каждого info: skip rejected, `handle.is_valid()`,
     `handle.has_metadata()`
   - `if info.file_idx == -1 or info.piece_length == 0:`
     - `ti = handle.get_torrent_info()`
     - `file_idx = file_picker.pick(ti)`
     - `RETRY`: continue; `NO_VIDEO` или `< 0`: mark_rejected
     - else: `info.file_idx = file_idx;
       info.first_piece = on_prioritize(handle, ti, file_idx);
       info.piece_length = ti.piece_length()`
   - `st = handle.status(); peers = st.num_peers;
     rate = int(st.download_payload_rate or 0)`
   - `if peers < 1: continue`
   - `has_first = handle.have_piece(info.first_piece) if
     info.first_piece >= 0 else False`
   - `is_ready = has_first or (rate > min_rate and peers >= min_peers)`
   - `piece_mult = _piece_multiplier(piece_length)`
   - `score = (rate / 1024.0) * (1.0 + log10(max(1, peers))) *
     (1.5 if is_ready else 1.0) * piece_mult`
   - запомнить best
4. `_piece_multiplier(piece_len)` — `<=1MB: 1.2`, `<=2MB: 1.0`, `<=4MB: 0.7`,
   `<=8MB: 0.4`, else `0.2`
5. `_kill_dead(now)`:
   - `has_meta and not rejected`:
     - `peers == 0 and total_done == 0 and age > kill_dead` → remove
     - `fp_age > kill_no_first` → remove
   - `not has_meta and age > kill_meta` → remove
   - `on_kill(info.handle); registry.remove(info.handle)`
6. `_pending_no_meta() -> int` — count handles без metadata но с peers > 0

**Проверка:** с одним magnet и пирами → `detect(30)` возвращает `HandleInfo`.
С 12 мёртвыми → через 30s `None`.

**Инварианты:**
- Grace **10s** — не выбираем мгновенно. Хороший торрент может быть
  медленным в первые секунды (DHT discovery), потом вырывается.
- Margin **×2** — переключение только если новый в 2 раза лучше. Иначе
  «дёргается» между двумя похожими.
- `RETRY` (metadata не готова) ≠ `NO_VIDEO` (точно нет видео). Первый —
  skip, второй — reject.

---

### T-3.5: `services/torrent/peer_monitor.py`

**Время:** 8 min
**Файлы:** `services/torrent/peer_monitor.py` (create)
**Зависит от:** T-0.2

**Что делать:**

1. `@dataclass class PeerStats`: `total_peers`, `connected_peers`,
   `peers_with_piece`, `top_peer_rates`, `sum_top_rates`, `payload_rate`,
   `total_done`, `timestamp`
2. `class PeerMonitor(geometry, interval=None)`:
   - `interval = interval or config.PEER_MONITOR_INTERVAL_SEC`
   - `latest = PeerStats()`, `_task = None`, `_running = False`
3. `start()` — `create_task(_loop())`
4. `async _loop()`:
   - `while _running and geometry.handle:
     await asyncio.sleep(interval); latest = _collect()`
5. `_collect() -> PeerStats`:
   - `st = handle.status()` — `total_peers`, `payload_rate`, `total_done`
   - `peer_info = handle.get_peer_info()`
   - фильтр `connecting/handshake`, `connected += 1`,
     `rate = p.payload_down_speed`
   - `peers_with_piece` — `p.pieces.get_bit(current_piece)` если current >= 0
   - top N rates (`PEER_MONITOR_TOP_N=5`), `sum_top_rates = sum(top)`
6. `stop()` — `_running = False; _task.cancel()`

**Проверка:** после старта с активным торрентом
`monitor.latest.connected_peers >= 0`.

---

## Phase 4: HTTP Range Server

**Зачем:** маскировать торрент под обычный HTTP-поток для QMediaPlayer.
QMediaPlayer не умеет торренты, но умеет HTTP Range.

---

### T-4.1: `services/torrent/http_range_server.py` — setup + range

**Время:** 12 min
**Файлы:** `services/torrent/http_range_server.py` (create)
**Зависит от:** T--1.1, T-1.2

**Что делать:**

1. `_RANGE_RE` — regex `bytes=(\d*)-(\d*)`
2. `class HttpRangeServer(session)`:
   - `host = "127.0.0.1"`, `port = 0`
   - `_runner = None`, `_site = None`, `_allowed_hosts = set()`
   - `_cache: OrderedDict[int, bytes] = OrderedDict()`
   - `_cache_limit = config.HTTP_RANGE_CACHE_PIECES` (8)
   - `chunk_size = config.HTTP_RANGE_CHUNK_SIZE` (1 MB)
   - `poll_sec = config.HTTP_RANGE_POLL_SEC` (0.05)
3. `async start() -> str`:
   - `app = web.Application()`, `add_get("/stream", _handle_stream)`,
     `add_get("/health", _handle_health)`
   - `_runner = web.AppRunner(app)`, `setup()`
   - `_site = web.TCPSite(_runner, "127.0.0.1", 0)`, `start()`
   - `port = socks[0].getsockname()[1]`
   - `_allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}",
     f"[::1]:{port}"}`
   - return `f"http://127.0.0.1:{port}/stream"`
4. `_check_host(request) -> bool`:
   - `host = request.headers.get("Host", "")`
   - **`if not host: return False`** — пустой Host = чужой
   - `return host in _allowed_hosts`
5. `_parse_range(header, file_size) -> (int, int) | (None, None)`:
   - `m = _RANGE_RE.match(header.strip())`
   - suffix `bytes=-N`: `start = max(0, file_size - N), end = file_size - 1`
   - start-end: `start = int(start_s),
     end = int(end_s) if end_s else file_size - 1`
   - `end = min(end, file_size - 1)`
   - `if start > end or start >= file_size: return None, None`
6. `_cache_get(piece)`, `_cache_put(piece, data)` — `OrderedDict`,
   `move_to_end`, `popitem(last=False)` при превышении лимита

**Проверка:**

```python
from services.torrent.http_range_server import HttpRangeServer

assert HttpRangeServer._parse_range("bytes=0-99", 1000) == (0, 99)
assert HttpRangeServer._parse_range("bytes=-100", 1000) == (900, 999)
assert HttpRangeServer._parse_range("bytes=2000-", 1000) == (None, None)
```

**Инварианты:**
- `127.0.0.1`, не `0.0.0.0` — сервер доступен только локально.
- `port = 0` — auto, ОС выдаёт свободный порт. Не фиксированный 8080.
- `_check_host` отвергает **пустой** Host. Иначе DNS rebinding: браузер
  жертвы обращается к `evil.com`, но DNS резолвит в `127.0.0.1:port`.

---

### T-4.2: `services/torrent/http_range_server.py` — `_handle_stream`

**Время:** 15 min
**Файлы:** `services/torrent/http_range_server.py` (append)
**Зависит от:** T-4.1

**Что делать:**

1. `if not _check_host(request): return web.Response(status=403)`
2. `session = self.session; if not session.is_active(): return 503`
3. `file_size = session.file_size`
4. `if range_header: start, end = _parse_range(...); if start is None:
   raise HTTPRequestRangeNotSatisfiable(headers={"Content-Range":
   f"bytes */{file_size}"}); status = 206`
5. `else: start, end = 0, file_size - 1; status = 200`
6. `headers = {"Content-Type": session.content_type, "Accept-Ranges": "bytes",
   "X-Content-Type-Options": "nosniff"}` + `Content-Range` если 206
7. `response = web.StreamResponse(status, headers)`, `prepare(request)`
8. `if start > 0: session.scheduler.on_seek(start)`
9. loop `while bytes_left > 0`:
   - `if not session.is_active(): break`
   - `if not is_client_alive(): break`
   - `piece = current_piece if current в диапазоне, иначе
     session.geometry.piece_for_byte(current)`
   - `if piece < 0: sleep(poll_sec); continue`
   - `if piece != current_piece:`
     - `session.scheduler.on_position(current)`
     - `ok = await session.wait_for_piece(piece, is_client_alive)`
     - `if not ok: break`
     - `data = _cache_get(piece) or await session.read_piece(piece)`
     - `if data is None: sleep(poll_sec); continue`
     - `_cache_put(piece, data)`
     - `current_piece = piece; data_offset = max(0, current - piece_start)`
   - `available = len(current_data) - data_offset`
   - `if available <= 0: current_piece = -1; continue`
   - `this_chunk = min(chunk_size, bytes_left, available)`
   - `await response.write(data_out)` в try
   - `current += len; bytes_left -= len`
10. `if bytes_left == 0: await response.write_eof()` в try
11. catch `ConnectionReset/Aborted/CancelledError` → break
12. `async stop()` — `await _runner.cleanup()`, `_cache.clear()`

**Проверка:** с реальным магнитом — `curl -r 0-1048575
http://127.0.0.1:PORT/stream` → 206 + 1 MB данных.

**Инварианты:**
- `on_seek(start)` перед циклом — сброс deadline для старой позиции.
- `X-Content-Type-Options: nosniff` — браузер не будет «угадывать» тип.
- `current_piece` кэшируется — не пересчитывается `piece_for_byte` для
  каждого байта. `piece_for_byte` — арифметика, но лишний вызов на
  каждом chunk не нужен.

---

## Phase 5: StreamSession

**Зачем:** координатор, который связывает все компоненты. Самая большая
задача — но она **только связывает**, логика в компонентах.

---

### T-5.1: `services/torrent/session/stream_session.py` — `__init__`

**Время:** 10 min
**Файлы:** `services/torrent/session/stream_session.py` (create)
**Зависит от:** Phase 3, Phase 4

**Что делать:**

1. `class StreamSession`:
   - Константы класса:
     `MAX_SOURCES = config.STREAM_MAX_SOURCES` (12),
     `READY_TIMEOUT = 30.0`,
     `PRIORITY_TOP = 7`,
     `DEADLINE_FIRST_PIECES = 3`,
     `HANDLE_REMOVAL_TIMEOUT = 15.0`,
     `HANDLE_REMOVAL_POLL = 0.02`
2. `__init__(http_session, downloads_dir, libtorrent_session,
   progress_cb=None, finished_cb=None, failed_cb=None)`:
   - `if libtorrent_session is None: raise ValueError(...)`
   - поля: `http_session`, `session`, `base_downloads_dir`,
     `downloads_dir=""`, `_year=""`, `progress_cb/finished_cb/failed_cb`
   - состояние: `_cancelled=False`, `_ready=False`, `handle=None`,
     `torrent_info=None`, `file_idx=-1`, `file_size=0`, `file_path=""`,
     `content_type="video/mp4"`, `alternatives=[]`
   - **компоненты:**
     - `registry = HandleRegistry()`
     - `file_picker = FilePicker()`
     - `geometry = PieceGeometry()`
     - `scheduler = PieceScheduler(geometry)`
     - `monitor = PeerMonitor(geometry)`
     - `http_server = None`
     - `piece_streamer = PieceStreamer(geometry, scheduler,
       lambda: self.handle, lambda: self.file_path)`
     - `alert_pump = AlertPump(self.session,
       piece_streamer.on_read_piece_alert)`
     - `_loader = None`

**Проверка:** `StreamSession(...)` создаётся без ошибок.

---

### T-5.2: `stream_session.py` — `start()` + `_load_trackers` +
`_dedup_and_merge` + `_load_sources`

**Время:** 15 min
**Файлы:** `stream_session.py` (append)
**Зависит от:** T-5.1

**Что делать:**

1. `async start(sources, year="")`:
   - `if not sources: _fail("Список источников пуст"); return`
   - `_year = year.strip()`
   - `downloads_dir = _create_session_dir()`
   - `file_picker = FilePicker(_year)`
   - `_loader = SourceLoader(http_session, session, registry, file_picker,
     _prioritize)`
   - `alert_pump.start()`
   - `dynamic_trackers = await _load_trackers()`
   - `selector = SourceSelector(year, language=config.SEARCH_LANGUAGE)`
   - `primary, alternatives = selector.select(sources)`
   - `alternatives` сохраняем
   - `if primary is None: _fail("Нет подходящих источников"); return`
   - `candidates = ([primary] + alternatives)[:MAX_SOURCES]`
   - `groups = group_sources_by_hash(candidates,
     extra_trackers=dynamic_trackers)`
   - `unique = _dedup_and_merge(groups, dynamic_trackers)`
   - **диагностика:** `before_count = len(session.get_torrents())`,
     log
   - `await _load_sources(unique)`
   - `after_count = len(session.get_torrents())`, log
   - `if len(registry) == 0: _fail("Не удалось добавить ни один источник");
     return`
   - sequential download on (`if config.STREAM_SEQUENTIAL_DOWNLOAD`)
   - `detector = ReadyDetector(registry, file_picker, _prioritize,
     _kill_handle)`
   - `winner = await detector.detect(READY_TIMEOUT,
     cancelled_check=lambda: _cancelled)`
   - `if winner is None: if not _cancelled: _fail(f"Ни один из N не начал
     качать"); return`
   - `if not _activate_winner(winner): return`
   - `_ready = True`, `monitor.start()`
   - `finished_cb(self)` в try
2. `async _load_trackers() -> list[str]` — `TrackerBalancer().get_trackers()`,
   log, в try
3. `_dedup_and_merge(groups, dynamic_trackers) -> list[dict]`:
   - `__`-prefixed key → append `srcs[0]`
   - иначе: `merged_url = merge_magnets_in_group(srcs,
     extra=dynamic_trackers)`, `merged = dict(srcs[0]);
     merged["url"] = merged_url`
4. `_load_sources(unique)`:
   - для каждого с индексом `i`: `save_dir = downloads_dir / f"h{i:02d}"`,
     `os.makedirs`, `result = await _loader.load(src, save_dir,
     is_primary=(i==0))`, log

**Проверка:** в логах `Taking N candidates`, `Session state before add: 0
torrents`, `Added [N/12] magnet → hXX`, `StreamSession ready`.

**Инварианты:**
- `Before add: 0 torrents` — если не 0, значит предыдущий `cancel()` не
  доработал. См. T-5.4.
- `alert_pump.start()` **до** `_load_sources` — иначе первые alerts
  (metadata_received) потеряются.

---

### T-5.3: `stream_session.py` — `_activate_winner` + `_prioritize` +
`_adaptive_startup_count` + `_remove_losers` + `_kill_handle`

**Время:** 15 min
**Файлы:** `stream_session.py` (append)
**Зависит от:** T-5.2

**Что делать:**

1. `_activate_winner(winner) -> bool`:
   - `handle = winner.handle`, `downloads_dir = winner.save_dir`
   - `torrent_info = handle.get_torrent_info()` в try
   - `file_idx = winner.file_idx`
   - `file_size = files.file_size(idx)`, `rel_path = files.file_path(idx)`
   - **path traversal:**
     - `candidate = normpath(join(downloads_dir, rel_path))`
     - `real_base = realpath(downloads_dir)`
     - `real_target = realpath(candidate)`
     - `if not (real_target == real_base or
       real_target.startswith(real_base + os.sep)): fail`
   - `file_path = real_target`
   - `content_type` по ext — mp4, mkv, webm, avi, mov, wmv, flv, ts, m2ts,
     mts → соответствующие MIME, else `application/octet-stream`
   - `geometry.configure(handle, file_idx, file_size, piece_length,
     num_pieces, file_offset_in_torrent)`
   - `_apply_full_priorities(handle, info, file_idx)`
   - `_remove_losers(winner.handle)`
   - `http_server = HttpRangeServer(self)`
   - return True
2. `_apply_full_priorities(handle, info, file_idx)`:
   - `n = info.files().num_files()`
   - `for i in range(n): file_priority(i, PRIORITY_TOP if i == file_idx
     else 0)` в try
   - `first_piece = _prioritize(handle, info, file_idx, tail=True)`
   - `adaptive = _adaptive_startup_count()`
   - `scheduler.on_startup(first_piece, adaptive)`
3. `_prioritize(handle, info, file_idx, tail=False) -> int`:
   - `piece_len`, `offset = info.files().file_offset(file_idx)`
   - `first_piece = offset // piece_len`, `total = info.num_pieces()`
   - `head_count = 5 if not tail else DEADLINE_FIRST_PIECES`
   - head: `for i in range(head_count): piece_priority(7);
     set_piece_deadline(2000 + i * 500)`
   - tail: `tail_count = PIECE_SCHEDULER_TAIL_COUNT (20);
     tail_start = max(0, total - 20); for p: piece_priority(7);
     set_piece_deadline(1000)`
   - return `first_piece`
4. `_adaptive_startup_count() -> int`:
   - `piece_len = geometry.piece_length or 1`
   - `target = config.STREAM_SESSION_ADAPTIVE_START_BYTES (8 MB)`
   - `from_bytes = max(1, target // piece_len)`
   - `min_p = config.STREAM_STARTUP_MIN_PIECES (30)`
   - `max_p = config.STREAM_STARTUP_MAX_PIECES (100)`
   - `return max(min_p, min(max_p, from_bytes))`
5. `_remove_losers(winner_handle)`:
   - для каждого info в registry:
     - `if info.handle is winner_handle: kept += 1; continue`
     - `if not has_metadata and st.num_peers > 0: kept += 1; continue`
     - `async_remove_torrent(info.handle)` в try, `registry.remove`
6. `_kill_handle(handle)` — `async_remove_torrent(handle)` в try

**Проверка:** `Torrent configured: file.mkv (X MB), piece=Y, offset=Z`,
`Startup: first_piece=N adaptive=M`.

**Инвариант:** tail priority — 20 последних pieces с deadline 1000ms.
`moov`-атом в MKV/MP4 в конце файла. Без него FFmpeg не может определить
duration и seek.

---

### T-5.4: `stream_session.py` — `cancel()` + `_wait_handles_removed` +
`_cleanup_downloads` + public API

**Время:** 20 min
**Файлы:** `stream_session.py` (append)
**Зависит от:** T-5.3

**Что делать:**

1. `async cancel()`:
   - `_cancelled = True`, `_ready = False`
   - `piece_streamer.cancel_all()`
   - **pump НЕ стопаем** — обрабатывает removals
   - `monitor.stop()` в try
   - `if http_server: await http_server.stop(); http_server = None`
   - `for info in registry: async_remove_torrent(info.handle)` в try
   - `registry.clear()`, `handle = None`
   - `await _wait_handles_removed()`
   - `await alert_pump.stop()` в try
   - `await _cleanup_downloads()`
2. `async _wait_handles_removed()`:
   - `deadline = time + HANDLE_REMOVAL_TIMEOUT (15.0)`
   - `while time < deadline: if len(session.get_torrents()) == 0: return;
     await asyncio.sleep(0.02)`
   - **sync fallback:** `remaining = list(session.get_torrents())`
   - `if not remaining: return`
   - `log.warning("cancel: async_remove_torrent не удалил за 15.0s —
     sync remove для N handles")`
   - `for h in remaining: session.remove_torrent(h)` в try
3. `async _cleanup_downloads()`:
   - `if not downloads_dir or not isdir: downloads_dir = ""; return`
   - `path = downloads_dir; downloads_dir = ""`
   - `await asyncio.sleep(0.5)`
   - `await loop.run_in_executor(None, shutil.rmtree, path, True)` в try
4. `_fail(msg)` — `log.error`, `failed_cb(msg)` в try
5. `_create_session_dir() -> str` — `os.makedirs(base, exist_ok=True)`,
   `{ts}_{rnd}`
6. **Public API:** `wait_for_piece`, `read_piece`, `is_active`
   (`not _cancelled and _ready`), `is_buffering`, `buffering_duration`,
   `current_stream_pos` (property → `scheduler.current_byte_pos`),
   `stats` (property → `monitor.latest`)

**Проверка:** после close — либо `cancel: async_remove_torrent не удалил
за 15.0s`, либо ничего (успел); следующий start →
`Session state before add: 0 torrents`.

**Инварианты:**
- `alert_pump` **остаётся живым** во время polling — обрабатывает removals.
  Остановка **после** polling, не до.
- `alert_pump.stop()` — async, с `sleep(0.05)` перед `cancel()`.
- `_wait_handles_removed` — polling `get_torrents() == 0`, до 15s. Если
  не помогло — **sync fallback** `remove_torrent(h)`.
- `rmtree` — в executor, не sync. Иначе 25 GB папка блокирует UI на секунды.

---

### T-5.5: `services/torrent/session/__init__.py`

**Время:** 2 min
**Файлы:** `services/torrent/session/__init__.py` (append)
**Зависит от:** T-5.4

**Что делать:**

1. `from .stream_session import StreamSession`
2. `__all__ = ["StreamSession"]`

**Проверка:**

```bash
python -c "from services.torrent.session import StreamSession; print('ok')"
```

---

## Phase 6: Integration

**Зачем:** подключить P2P к существующему StreamController (Plan 01).
После этой фазы клик «Start streaming» в private запускает StreamSession.

---

### T-6.1: `cascade._dispatch` — P2P branch

**Время:** 10 min
**Файлы:** `controllers/stream/cascade.py` (append)
**Зависит от:** T-5.5

**Что делать:**

1. В `_dispatch` после public-ветки:
   - `p2p = [s for s in sources if s.get("type") in
     ("magnet", "torrent_url")]`
   - `direct = [s for s in sources if s.get("type") == "direct_url"
     and s.get("indexer") not in ("balancer", "videocdn", "bwa")]`
   - `c._p2p_fallback = p2p`, `c._direct_fallback = direct`
   - `if p2p:`
     - `await c._stop_resources()`
     - `if not c.libtorrent_session: c.on_failed("Libtorrent session не
       инициализирован"); return`
     - `c.stream_session = StreamSession(http_session=c.session,
       downloads_dir=str(config.DOWNLOADS_DIR),
       libtorrent_session=c.libtorrent_session, progress_cb=c._update_bar,
       finished_cb=c.on_ready, failed_cb=c.on_failed)`
     - `await c.stream_session.start(p2p, year=year)`
     - `return`

**Проверка:** клик «Start streaming» в private → `StreamSession.start`
вызывается, в логах `Taking N candidates`.

---

### T-6.2: `stream_controller.on_ready` + `_start_http_and_play`

**Время:** 8 min
**Файлы:** `controllers/stream/stream_controller.py` (append)
**Зависит от:** T-6.1

**Что делать:**

1. `on_ready(session)`:
   - `if not session.http_server: on_failed("HTTP server не создан"); return`
   - `create_task(_start_http_and_play(session))`
2. `async _start_http_and_play(session)`:
   - `url = await session.http_server.start()`
   - `session._ready = True`, `session.monitor.start()`
   - `playback.play_url(url, _current_movie_id, _current_movie_title)`
   - `buffer.start_p2p(lambda: self.stream_session)`

**Проверка:** в логах `Стрим готов: http://127.0.0.1:PORT/stream`,
потом `wait_piece 0: X.Xs`.

---

### T-6.3: `BufferMonitor` — `start_p2p` + `_check_p2p`

**Время:** 12 min
**Файлы:** `controllers/stream/buffer_monitor.py` (create — полный)
**Зависит от:** T-6.2

**Что делать:**

1. `class BufferMonitor(main_window, playback, on_fallback)`:
   - `INTERVAL_MS = config.STREAM_MONITOR_INTERVAL_MS` (1000)
   - `STOP_DELAY = config.STREAM_BUFFER_STOP_DELAY_SEC` (30)
   - `WATCHDOG_SEC = config.STREAM_BUFFERING_WATCHDOG_SEC` (25)
   - `WATCHDOG_RATE = config.STREAM_BUFFERING_WATCHDOG_RATE_MB` (0.3)
2. `start_p2p(stream_session_getter)`:
   - `_timer = QTimer(main_window)`, `setInterval(1000)`,
     `timeout.connect(lambda: _check_p2p(getter))`, `start()`
3. `_check_p2p(getter)`:
   - `session = getter(); if not session or not playback: return`
   - `buffering = session.is_buffering()`, `stats = session.stats`,
     `buf_dur = session.buffering_duration()`
   - **watchdog:** `if buffering and buf_dur > 25 and
     stats.payload_rate / 1024 / 1024 < 0.3:
     QTimer.singleShot(0, _safe_stop_player); on_fallback(force=True); return`
   - **stop:** `if buffering and not _stopped: if _pending_since is None:
     _pending_since = time.time(); if time - _pending_since > 30:
     QTimer.singleShot(0, _safe_stop_player); _stopped = True`
   - **reload:** `elif not buffering and _stopped:
     playback.reload_url(); _stopped = False`
4. `_safe_stop_player()` — `playback.player.setSource(QUrl())` (без stop)
5. `stop()`, `mark_stopped()`

**Проверка:** `WATCHDOG: 25.0s, rate=0.1, peers=3 → fallback` при зависании;
`Buffer 30s — stop` при долгой буферизации.

**Инвариант:** `player.stop()` через `QTimer.singleShot(0, ...)` — не sync
в QTimer callback. Иначе UI замирает на время stop.

---

## Phase 7: Verify

**Зачем:** проверить P2P end-to-end. Plan 01 покрыл public, Plan 02 —
P2P. Всё вместе — полный сценарий.

---

### T-7.1: E2E P2P test

**Время:** 10 min
**Файлы:** —

**Шаги:**
1. `switch_mode.py private` (или вручную `data/mode.txt` = `private`)
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
**Файлы:** —

**Шаги:**
1. Мёртвый магнит (0 сидов) → `meta=N peers=0` 30s →
   `FAILED: Ни один из N не начал качать`
2. Отключить сеть во время стрима → watchdog или demux → fallback
3. Закрыть во время `wait_ready` → `cancel()` → handles удалены за 15s

**Проверка:** ни один не крэшит.

---

### T-7.3: No zombies

**Время:** 2 min
**Файлы:** —

**Шаги:**
1. После close — `tasklist | findstr amagi-player` — пусто
2. `tasklist | findstr python` — пусто (кроме терминала)

**Проверка:** процессы завершены.

---

## Чек-лист готовности

- [ ] Phase -1: `libtorrent` установлен, все константы в config
- [ ] Phase 0: `create_session(6881)` возвращает session
- [ ] Phase 1: `force_deadline(5, 3)` → 3 вызова `set_piece_deadline`
- [ ] Phase 2: `SourceSelector.rank()` отбрасывает CAM
- [ ] Phase 3: `ReadyDetector.detect(30)` с живым магнитом → HandleInfo
- [ ] Phase 4: `curl -r 0-1048575` → 206 + 1 MB
- [ ] Phase 5: `cancel()` → `Session state before add: 0 torrents` при
      следующем start
- [ ] Phase 6: клик «Start streaming» в private → видео играет
- [ ] Phase 7: E2E, failure modes, no zombies

**Все ✅ → P2P работает.**
