# Plan: Public Streaming from Internet Archive

**Goal:** клик на карточку → экран деталей → «Запустить трансляцию» →
видео играет из IA → seek работает → закрытие возвращает в ленту.

**Depends on:** None (первый план, база для остальных).

**Out of scope:** P2P streaming (Plan 02), fallback (Plan 03),
Jackett/WebFetcher/nodriver (Plan 04), приватные источники,
скачивание, субтитры, выбор аудиодорожки.

**Estimated:** 4–6 hours для джуна без контекста.

**Key risk:** Internet Archive возвращает файлы в DVD-контейнерах
(mpeg/mpg), которые ломаются при seek. Решается приоритетом формата
в `metadata.py` — но если в элементе только mpeg, придётся использовать
его с риском demux error.

---

## Phase 0: Setup

### T-0.1: Создать скелет проекта

**Время:** 3 min
**Файлы:** директории `ui/`, `ui/widgets/`, `controllers/`,
`controllers/stream/`, `services/`, `services/torrent/`,
`services/torrent/session/`, `search/`, `search/archive_org/`,
`search/aggregator/`, `database/`, `core/`; `__init__.py` в каждом.
**Зависит от:** —

**Шаги:**
1. Создать все директории
2. Создать пустой `__init__.py` в каждой
3. Создать `main.py`, `config.py` в корне

**Проверка:**
```bash
python -c "import ui, controllers, services, search, database, core"
```
без ошибок.

---

### T-0.2: `requirements.txt` — runtime-зависимости

**Время:** 2 min
**Файлы:** `requirements.txt` (create)
**Зависит от:** T-0.1

**Шаги:**
1. Записать версии:
   ```
   PyQt6==6.11.0
   PyQt6-Qt6==6.11.2
   PyQt6-WebEngine==6.11.0
   PyQt6-WebEngine-Qt6==6.11.2
   PyQt6_sip==13.13.0
   aiohttp==3.14.5
   qasync==0.28.0
   ```
2. `pip install -r requirements.txt`

**Проверка:**
```bash
python -c "from PyQt6.QtWidgets import QApplication; import aiohttp, qasync; print('ok')"
```
→ `ok`.

---

### T-0.3: `config.py` — базовые константы

**Время:** 4 min
**Файлы:** `config.py` (append)
**Зависит от:** T-0.1

**Шаги:**
1. `BASE_DIR = Path(__file__).resolve().parent`
2. `DATA_DIR = BASE_DIR / "data"`, `CACHE_DIR = DATA_DIR / "cache"`,
   `DB_PATH = DATA_DIR / "app_data.db"`,
   `WHITELIST_DB_PATH = DATA_DIR / "whitelist.db"`,
   `DOWNLOADS_DIR = DATA_DIR / "downloads"`, `LOGS_DIR = BASE_DIR / "logs"`
3. `CACHE_SHORT_DIR`, `CACHE_FULL_DIR`, `CACHE_LISTS_DIR` — подпапки `CACHE_DIR`
4. `NETWORK_TIMEOUT = 15`, `USER_AGENT = "AmagiPlayer/2.0"`
5. `os.makedirs` для всех директорий (exist_ok=True)

**Проверка:**
```bash
python -c "import config; print(config.DATA_DIR.exists(), config.CACHE_SHORT_DIR.exists())"
```
→ `True True`.

---

### T-0.4: `core/logging_setup.py`

**Время:** 3 min
**Файлы:** `core/logging_setup.py` (create)
**Зависит от:** T-0.3

**Шаги:**
1. `setup_logging(level=INFO)` — очистить root handlers, добавить
   StreamHandler с форматом
   `[%(asctime)s] %(levelname)-7s %(name)-20s | %(message)s`
2. `get_logger(name) -> Logger` — вызывает `setup_logging()`, возвращает logger
3. Подавить `aiohttp.access`, `asyncio`, `urllib3` → `WARNING`

**Проверка:**
```python
from core.logging_setup import get_logger
get_logger("test").info("hello")
# stdout: [12:00:00] INFO    test                 | hello
```

---

### T-0.5: `main.py` — минимальное окно

**Время:** 4 min
**Файлы:** `main.py` (create)
**Зависит от:** T-0.2, T-0.4

**Шаги:**
1. `app = QApplication(sys.argv)`
2. `loop = qasync.QEventLoop(app)`
3. `asyncio.set_event_loop(loop)`
4. `loop.run_forever()`

**Проверка:**
```bash
python main.py
```
Пустое окно открывается, `Ctrl+C` в консоли завершает.

---

## Phase 1: Data layer

### T-1.1: `database/connection.py` — app_data.db

**Время:** 5 min
**Файлы:** `database/connection.py` (create)
**Зависит от:** T-0.3

**Шаги:**
1. `get_connection()` — `sqlite3.connect(config.DB_PATH)`, WAL,
   `row_factory = sqlite3.Row`
2. `@contextmanager use_connection()` — commit/rollback/close
3. `init_db()` — таблицы:
   - `schema_version(version INTEGER PRIMARY KEY)`
   - `user_history(kp_id INTEGER PRIMARY KEY, movie_title TEXT NOT NULL,
     current_seconds INTEGER NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`
   - индекс `idx_history_updated ON user_history(updated_at DESC)`

**Проверка:**
```python
from database.connection import init_db, use_connection
init_db()
with use_connection() as conn:
    conn.execute("INSERT INTO user_history (kp_id, movie_title, current_seconds) VALUES (1, 'Test', 42)")
with use_connection() as conn:
    row = conn.execute("SELECT current_seconds FROM user_history WHERE kp_id = 1").fetchone()
    assert row["current_seconds"] == 42
```

---

### T-1.2: `database/whitelist_db.py` — whitelist.db + PYNORM

**Время:** 6 min
**Файлы:** `database/whitelist_db.py` (create)
**Зависит от:** T-1.1

**Шаги:**
1. `_pynorm(v)` — `v.lower().replace("ё", "е")` для Unicode-lowercase
   (SQLite `LOWER()` не работает для кириллицы)
2. `_connect()` — WAL, `row_factory = Row`,
   `conn.create_function("PYNORM", 1, _pynorm)`
3. `@contextmanager use_whitelist_connection()`
4. `init_whitelist_db()` — `movie_whitelist(kp_id INTEGER PRIMARY KEY,
   title_ru TEXT NOT NULL, title_en TEXT, year TEXT,
   archive_identifier TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   available INTEGER DEFAULT NULL)` + индексы на `available`, `title_ru`, `title_en`

**Проверка:**
```python
from database.whitelist_db import init_whitelist_db, use_whitelist_connection
init_whitelist_db()
with use_whitelist_connection() as conn:
    conn.execute("INSERT INTO movie_whitelist (kp_id, title_ru, year) VALUES (1, 'Матрица', '1999')")
    rows = conn.execute("SELECT * FROM movie_whitelist WHERE PYNORM(title_ru) LIKE ?", ("%матрица%",)).fetchall()
    assert len(rows) == 1
```

---

### T-1.3: `database/whitelist_repo.py`

**Время:** 6 min
**Файлы:** `database/whitelist_repo.py` (create)
**Зависит от:** T-1.2

**Шаги:**
1. `class WhitelistRepository` — статические методы
2. `search_movies_in_feed(query="", limit=20, offset=0) -> list[int]`:
   - `where = "(available = 1 OR available IS NULL)"`
   - `if query: AND (PYNORM(title_ru) LIKE ? OR PYNORM(title_en) LIKE ? OR year LIKE ?)`
   - `ORDER BY kp_id DESC LIMIT ? OFFSET ?`
   - `qn = query.lower().replace("ё", "е")` для параметров
3. `get_movie(kp_id) -> dict | None`
4. `get_archive_identifier(kp_id) -> str`
5. `count()`, `count_available()`

**Проверка:**
```python
from database.whitelist_repo import WhitelistRepository
assert 1 in WhitelistRepository.search_movies_in_feed("матрица")
assert WhitelistRepository.get_movie(1)["title_ru"] == "Матрица"
```

---

### T-1.4: `database/history_repo.py`

**Время:** 5 min
**Файлы:** `database/history_repo.py` (create)
**Зависит от:** T-1.1

**Шаги:**
1. `save_timestamp(kp_id, movie_title, current_seconds)` — UPSERT с
   `current_seconds = MAX(excluded.current_seconds, user_history.current_seconds)`
   (не сбрасывать больший прогресс меньшим)
2. `get_last_session() -> dict | None` — `ORDER BY updated_at DESC LIMIT 1`
3. `get_seconds_for_movie(kp_id) -> int`
4. `clear_history_entry(kp_id)`
5. `clear_all() -> int`

**Проверка:**
```python
from database.history_repo import HistoryRepository
HistoryRepository.save_timestamp(1, "Test", 42)
HistoryRepository.save_timestamp(1, "Test", 30)
assert HistoryRepository.get_seconds_for_movie(1) == 42
```

---

## Phase 2: IA search

### T-2.1: `search/archive_org/language.py` — `lang_score`

**Время:** 5 min
**Файлы:** `search/archive_org/language.py` (create)
**Зависит от:** T-0.4

**Шаги:**
1. `_PREFERRED_EN_MATCH = ("english", "eng", "american", "british", "usa", "uk", "silent")`
2. `_PREFERRED_RU_MATCH = ("russian", "rus", "soviet", "ussr", "silent")`
3. `_EN_OTHER_LANGS = (...)` — список всех остальных
4. `lang_score(actual, preferred, year="") -> float`:
   - `if year and int(year) < 1930: return 0.9` — silent era, язык ненадёжен
   - `if not actual: return 0.5`
   - `if "silent" in a or "no linguistic" in a: return 0.9`
   - `if preferred == "en"` и match → `1.0`; и other → `0.0`
   - `if preferred == "ru"` и match → `1.0`; и other → `0.0`
   - иначе `0.5`

**Проверка:**
```python
from search.archive_org.language import lang_score
assert lang_score("English", "en") == 1.0
assert lang_score("Russian", "en") == 0.0
assert lang_score("", "en") == 0.5
assert lang_score("Russian", "en", year="1925") == 0.9
```

---

### T-2.2: `search/archive_org/language.py` — `title_score`

**Время:** 4 min
**Файлы:** `search/archive_org/language.py` (append)
**Зависит от:** T-2.1

**Шаги:**
1. `_STOPWORDS = frozenset({"the", "and", "of", "a", "an", "in", "on", "for", "with", "to", "by"})`
2. `title_score(identifier, title, query) -> float`:
   - `q_words = [w for w in query.lower().split() if len(w) >= 3 and w not in _STOPWORDS]`
   - если пусто — fallback `[w for w in query.lower().split() if len(w) >= 2]`
   - `target = (identifier + " " + title).lower()`
   - `return sum(1 for w in q_words if w in target) / len(q_words)`

**Проверка:**
```python
assert title_score("the_kid_1921", "The Kid", "the kid") == 1.0
assert title_score("random", "Random", "the kid") == 0.0
```

---

### T-2.3: `search/archive_org/searcher.py` — каскад запросов

**Время:** 10 min
**Файлы:** `search/archive_org/searcher.py` (create)
**Зависит от:** T-2.1, T-2.2, T-0.3

**Шаги:**
1. `_FETCH_LIMIT = 30`, `_FINAL_LIMIT = 15`
2. `_escape_lucene(s)` — `([+\-&|!(){}\[\]^"~*?:\\/])` → `\\\1`
3. `class ArchiveOrgSearcher`:
   - `_session`, `_metadata` (lazy)
   - `_ensure_session()` — создаёт `aiohttp.ClientSession(timeout=NETWORK_TIMEOUT)`
4. `_search_identifiers(query, year, use_mediatype=True) -> list[dict]`:
   - Lucene: `title:("{escaped}")` + если year — `year:[{y-2} TO {y+2}]`
     (допуск ±2) + если флаг — `mediatype:(movies)`
   - GET `https://archive.org/advancedsearch.php` с
     `fl[]=identifier,title,year,downloads,language,creator`,
     `sort[]=downloads desc`, `rows={_FETCH_LIMIT}`, `output=json`
5. `search(query, year="") -> list[dict]`:
   - каскад: `docs = await _search_identifiers(q, year, True)`
   - `if not docs and year: docs = await _search_identifiers(q, year, False)`
   - `if not docs and year: docs = await _search_identifiers(q, "", True)`
   - `if not docs: docs = await _search_identifiers(q, "", False)`
   - score: `ls * 100 + ts * 50 + ds * 20`, sort desc, top 15
6. `close()` — закрыть session

**Проверка:**
```python
import asyncio
async def test():
    s = ArchiveOrgSearcher()
    docs = await s._search_identifiers("The Kid", "1921")
    assert len(docs) > 0
    assert any("kid" in d["identifier"].lower() for d in docs)
    await s.close()
asyncio.run(test())
```
(требует интернет).

---

### T-2.4: `search/archive_org/metadata.py` — выбор файла

**Время:** 10 min
**Файлы:** `search/archive_org/metadata.py` (create)
**Зависит от:** T-0.3

**Шаги:**
1. Константы:
   - `_VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ogv", ".mpg", ".mpeg", ".wmv")`
   - `_FORMAT_PRIORITY = {".mp4": 100, ".webm": 95, ".mkv": 90, ".m4v": 85, ".ogv": 50, ".mov": 40, ".avi": 20, ".wmv": 15, ".mpg": 5, ".mpeg": 3}`
   - `_STREAMING_UNFRIENDLY = {".mpeg", ".mpg", ".wmv"}`
   - `_TRAILER_SIZE_BYTES = 50 * 1024 * 1024`
   - `_MIN_FULL_MOVIE_BYTES = config.ARCHIVE_ORG_MIN_MOVIE_SIZE` (30 MB)
   - `_MAX_FILE_SIZE = config.ARCHIVE_ORG_MAX_FILE_SIZE` (4 GB)
2. `_LRUCache(maxsize=500, ttl=86400)` — из config `ARCHIVE_ORG_METADATA_CACHE_MAX`, `_TTL`
3. `class MetadataFetcher(session)`:
   - `find_video_file(identifier) -> dict | None`:
     - кэш → return
     - GET `https://archive.org/metadata/{identifier}`
     - parse `data["files"]`
     - для каждого: video ext, `30 MB ≤ size ≤ 4 GB`, не trailer
       (`_TRAILER_RE.search(normalized)` AND size < 50 MB → skip)
     - `friendly = [c for c in candidates if c[0] >= 40]` (mp4/webm/mkv/m4v/ogv/mov)
     - `pool = friendly or candidates` (если friendly нет — fallback на mpeg/wmv)
     - sort `(priority, size)` desc, `pool[0]`
     - return `{"url", "size", "format", "filename", "ext", "priority"}`
   - `find_videos_parallel(identifiers)` — `asyncio.gather`

**Проверка:**
```python
import asyncio
async def test():
    fetcher = MetadataFetcher(aiohttp.ClientSession())
    r = await fetcher.find_video_file("the_kid_1921")
    assert r and r["url"].startswith("https://archive.org/download/")
    assert r["size"] > 30 * 1024 * 1024
asyncio.run(test())
```

---

## Phase 3: StreamController

### T-3.1: `controllers/stream/cascade.py`

**Время:** 8 min
**Файлы:** `controllers/stream/cascade.py` (create)
**Зависит от:** T-2.3, T-2.4

**Шаги:**
1. `class CascadeExecutor(controller)` — хранит `loop`, `main_window`,
   `playback`
2. `async execute(meta, movie_id, movie_title, year)`:
   - `archive_query = title_en or title_ru`
   - `archive_results = await safe_archive_org(searcher, archive_query, year)`
     (timeout 30s)
   - `if not archive_results and archive_query != title_ru:
     archive_results = await safe_archive_org(searcher, title_ru, year)`
   - `unique = dedup_by_url(archive_results)`
   - `if not unique: loader_label.setText("ФИЛЬМ НЕ НАЙДЕН В INTERNET ARCHIVE"); return`
   - `await _dispatch(unique, movie_id, movie_title, year)`
3. `_dispatch` для public:
   - `direct = [s for s in sources if s["type"] == "direct_url"]`
   - sort `(priority, size)` desc
   - `chosen = direct[0]`
   - `playback.play_url(chosen["url"], movie_id, movie_title)`
   - `stream_in_progress = False`

**Проверка:** в логах `archive.org: N direct_url`, `PUBLIC: https://...`.

---

### T-3.2: `controllers/stream/stream_controller.py`

**Время:** 12 min
**Файлы:** `controllers/stream/stream_controller.py` (create)
**Зависит от:** T-3.1

**Шаги:**
1. Константы: `_CLOSE_STOP_TIMEOUT_SEC = 25.0`,
   `_CLOSING_WATCHDOG_MS = 30000`, `_PLAYER_RELEASE_DELAY_MS = 200`
2. `class StreamController(app)` — `loop`, `main_window`, `playback`,
   `session`, `archive_org`, `cascade`, `fallback`, `buffer`
3. `handle_stream_start(kp_id)`:
   - `if _closing_in_progress: _pending_start_kp_id = kp_id; return`
   - `if stream_in_progress: return`
   - `stream_in_progress = True`, `_current_movie_id/Title/Year`
   - `fallback.reset()`, сброс fallback-списков
   - `screen_stack.setCurrentIndex(2)`, `show_loader`,
     `loader_label.setText("ПОИСК ПОТОКОВ...")`
   - `create_task(cascade.execute(meta, ...))`
4. `handle_close_player(_seconds)`:
   - `_closing_in_progress = True`
   - `QTimer.singleShot(_CLOSING_WATCHDOG_MS, self._closing_watchdog)`
   - `playback.stop_and_save()`
   - `QTimer.singleShot(_PLAYER_RELEASE_DELAY_MS, self._start_close_async)`
5. `async _close_player_async()` — `wait_for(_stop_resources(), timeout=25.0)`,
   finally: сбросы, `screen_stack.setCurrentIndex(0)`,
   `check_resume_island()`, `_closing_in_progress = False`,
   запуск `_pending_start_kp_id`
6. `_try_next_direct()` — `_direct_index += 1`, если `>= len(_direct_fallback)`
   → loader «Все испробованы», иначе `play_url`
7. `_stop_resources()` — `session = self.stream_session;
   self.stream_session = None; await session.cancel()` (идемпотентно)
8. `_connect_signals()` — `close_player_requested` → `handle_close_player`,
   `skip_requested` → `_on_skip`

**Проверка:** клик → loader → видео; close → возврат в ленту.

---

### T-3.3: `services/playback_controller.py`

**Время:** 10 min
**Файлы:** `services/playback_controller.py` (create)
**Зависит от:** T-0.5

**Шаги:**
1. `class PlaybackController(QObject)` с `demux_error = pyqtSignal()`
2. `__init__` — `QMediaPlayer()`, `QAudioOutput()`,
   `player.setAudioOutput`, `_timer` (QTimer 500ms → `_tick_ui`),
   `_error_emit_pending = False`
3. `play_url(stream_url, movie_id, title)`:
   - `_resume_seconds = HistoryRepository.get_seconds_for_movie(movie_id)`
   - `show_video()`, `player.setVideoOutput(video_widget)`
   - `if _resume_seconds > 5: player.mediaStatusChanged.connect(_on_media_status_seek)`
   - `player.setSource(QUrl(stream_url))`, `player.play()`, `_timer.start()`
4. `_on_media_status_seek(status)` — на `LoadedMedia`:
   `setPosition(_resume_seconds * 1000)`, disconnect
5. `stop_stream(save=False)`:
   - `_timer.stop()`, `real_seconds = position() // 1000`
   - **1.** `player.setSource(QUrl())` — отпускаем file handle
   - **2.** `player.stop()` — после, не до
   - `if save and real_seconds > 5: save_timestamp(...)`
6. `_on_player_error(error, error_string)` — **не эмитить синхронно** из MF
   callback: `if _error_emit_pending: return; _error_emit_pending = True;
   QTimer.singleShot(0, self._emit_demux_error)`

**Проверка:** видео играет, seek работает, close отпускает file handle.

---

## Phase 4: UI

### T-4.1: `ui/widgets/player_widget.py`

**Время:** 8 min
**Файлы:** `ui/widgets/player_widget.py` (create)
**Зависит от:** T-0.5

**Шаги:**
1. `class MoviePlayerWidget(QWidget)`, signals: `close_player_requested`,
   `seek_requested`, `skip_requested`
2. `QStackedLayout`: `video_widget` (QVideoWidget) / `loader_container`
3. Controls bar: `timeline_slider`, `play_pause_button`, `time_label`,
   `skip_button`, `fullscreen_button`
4. `show_loader()`, `show_video()`, `set_buffering_progress(percent)`
5. `_on_slider_pressed/released` — `_slider_moving` flag, `seek_requested.emit`

**Проверка:** виджет рендерится, кнопки кликабельны.

---

### T-4.2: `ui/widgets/details_widget.py`

**Время:** 8 min
**Файлы:** `ui/widgets/details_widget.py` (create)
**Зависит от:** T-0.5

**Шаги:**
1. `class MovieDetailsWidget(QWidget)`, signals:
   `start_streaming_requested`, `back_to_feed_requested`
2. `_init_details_layout` — `back_btn` + `QHBoxLayout`:
   - `big_cover` 300×450 (AlignTop)
   - text_layout: `title_label` (detailsTitle), `year_label` (detailsYear),
     `desc_label` (detailsDescription, `setMaximumHeight(220)`), `play_btn`
3. `update_movie_details(metadata)` — title upper, year,
   `update_description`, `update_cover`
4. `update_description(text)` — `_truncate_for_display(text, 450)`,
   badge `(English)` для не-кириллицы
5. `_on_play_clicked` — `start_streaming_requested.emit(_current_kp_id)`

**Проверка:** title/year/desc/cover отображаются, клик эмитит kp_id.

---

### T-4.3: `ui/widgets/card_widget.py`

**Время:** 5 min
**Файлы:** `ui/widgets/card_widget.py` (create)
**Зависит от:** T-0.5

**Шаги:**
1. `_CARD_W = 220, _CARD_H = 340, _POSTER_H = 260, _BAR_H = 80`
2. `class MovieCardWidget(QWidget)`, `play_requested = pyqtSignal(int)`
3. `cover_label` (0, 0, 220, 260), `info_bar` (0, 260, 220, 80) с
   `title_label` + `year_label`
4. `mousePressEvent` — LeftButton → `play_requested.emit(kp_id)`
5. `update_poster(path)`

**Проверка:** карточка с постером, клик эмитит kp_id.

---

### T-4.4: `ui/widgets/feed_widget.py`

**Время:** 8 min
**Файлы:** `ui/widgets/feed_widget.py` (create)
**Зависит от:** T-4.3

**Шаги:**
1. `class MovieFeedWidget(QWidget)`, `next_page_requested = pyqtSignal()`
2. `QScrollArea` + `QGridLayout` внутри (`grid_container`)
3. `_on_scroll_moved(value)`:
   - `if _end_reached: return`
   - `if _is_loading_next: if max_scroll != _last_max_scroll:
     _is_loading_next = False; _last_max_scroll = max_scroll; return`
   - `if max_scroll > 0 and (max_scroll - value) < 300:
     _is_loading_next = True; next_page_requested.emit()`
4. `begin_batch()` — `blockSignals(True)` на scrollbar + `setUpdatesEnabled(False)`
5. `end_batch()` — `adjustSize()` → `setUpdatesEnabled(True)` → `blockSignals(False)`
6. `mark_end_reached()`, `mark_end_not_reached()`, `reset_loading_state()`,
   `reset_loading_flag()`
7. `add_card_to_grid(card) -> bool` — dedup по `kp_id` через `_rendered_kp_ids`,
   grid `(idx // 4, idx % 4)`
8. `clear_grid()` — clear grid, сброс `_rendered_kp_ids`, scrollbar `setValue(0)`

**Проверка:** скролл до низа эмитит `next_page_requested`, дубликатов нет.

---

### T-4.5: `ui/main_window.py` — минимальный

**Время:** 12 min
**Файлы:** `ui/main_window.py` (create)
**Зависит от:** T-4.1, T-4.2, T-4.4

**Шаги:**
1. `class MainWindow(QMainWindow)` 1150×820
2. Signals: `theme_toggle_requested`, `resume_movie_requested`,
   `resume_dismiss_requested`, `language_changed`
3. `_init_ui_core`:
   - Header (75px): logoLabel, `searchBar`, `languageButton`
   - `QStackedWidget`: `feed_page`, `details_page`, `player_page`,
     `settings_page_placeholder`
   - Bottom bar: `theme_btn`, `settings_btn`
4. `resume_island` (QFrame 420×96) — `resume_label`, `resume_action_btn`,
   `resume_close_btn`, `hide()` по умолчанию
5. `_load_stylesheet()` — читает `ui/styles.qss`, `setStyleSheet`
6. `show_resume_bar(movie_id, title)` — `_reposition_resume_island`,
   `_animate_resume_island_in` (opacity + slide-up через QPropertyAnimation)
7. `_on_language_btn_clicked` — EN↔RU, emit `language_changed`

**Проверка:** окно открывается, три экрана переключаются, header виден.

---

### T-4.6: `ui/styles.qss`

**Время:** 8 min
**Файлы:** `ui/styles.qss` (create)
**Зависит от:** T-4.5

**Шаги:**
1. `QMainWindow, QStackedWidget, QScrollArea, QWidget#gridContainer { background-color: #000000; }`
2. `QLineEdit#searchBar` — `background: #000`, `color: #FFF`, border 1px
   `rgba(255,255,255,0.25)`, border-radius 12px, padding 10/16
3. `MovieCardWidget` — `background: rgba(255,255,255,0.03)`, border
   `rgba(255,255,255,0.06)`, border-radius 20px
4. `QPushButton#actionButton` — `#FFFFFF` bg, `#000000` text,
   border-radius 12px, font-weight 700

**Проверка:** тёмная тема, белый текст, скруглённые карточки.

---

## Phase 5: Wiring

### T-5.1: `controllers/feed_controller.py`

**Время:** 12 min
**Файлы:** `controllers/feed_controller.py` (create)
**Зависит от:** T-1.3, T-4.4

**Шаги:**
1. `PAGE_SIZE = 20`, `_MIN_POSTER_BYTES = 2000`,
   `_KP_MIN_INTERVAL = 1.5`, `_KP_COOLDOWN_429_SEC = 60.0`
2. `class FeedController(app)` — `loop`, `main_window`, `session`, `kp_service`
3. `async load_feed(clear_grid=False)`:
   - если `clear_grid: clear_grid()`, `reset_loading_state()`
   - `query = search_bar.text().strip()`
   - `if config.DISABLE_WHITELIST: kp_service...` (private)
   - `else: offset = (page-1) * PAGE_SIZE;
     ids = WhitelistRepository.search_movies_in_feed(query, limit=PAGE_SIZE, offset=offset)`
   - `begin_batch()`, для каждого `kp_id`: `get_movie` → `MovieCardWidget` →
     `add_card_to_grid` → `card.play_requested.connect(self._on_card_clicked)`
   - `if not data.get("cover_path"): create_task(_load_poster_cascade(...))`
   - `end_batch()`, `if not has_more: mark_end_reached()`
4. `_load_poster_cascade(kp_id, card, title, title_en, year)`:
   cache → seed → IA thumbnail → KP
5. `run_search()` — `_search_generation += 1`, `current_page = 1`,
   `mark_end_not_reached`, `reset_loading_state`,
   `create_task(load_feed(clear_grid=True))`
6. `load_next_page()` — `create_task(_load_next_page_async())` с lock
7. `_on_card_clicked(kp_id)` → `app.details.open(kp_id)`

**Проверка:** 20 карточек при старте, поиск фильтрует, скролл грузит.

---

### T-5.2: `controllers/details_controller.py`

**Время:** 10 min
**Файлы:** `controllers/details_controller.py` (create)
**Зависит от:** T-1.3, T-4.2

**Шаги:**
1. `_MIN_POSTER_BYTES = 500`, `_IA_MIN_BYTES = 500`,
   `_MAX_DESCRIPTION_LEN = 500`
2. `class DetailsController(app)` — `loop`, `main_window`, `session`, `kp_service`
3. `open(kp_id)` → `create_task(_open_details_page(kp_id))`
4. `_open_details_page(kp_id)`:
   - `resume_island.hide()`
   - `cover_path = cache/{kp_id}.jpg` если размер > 500
   - `metadata = _metadata_from_whitelist(kp_id, cover_path)` (public)
   - `details_page.set_movie_id(kp_id)`, `update_movie_details(metadata)`,
     `screen_stack.setCurrentIndex(1)`
   - `if not cover_path: create_task(_load_cover_for_details(...))`
   - `if not description and not will_lazy_resolve:
     create_task(_load_description_for_details(...))`
5. `_load_description_for_details(kp_id, title_en, title_ru, year)`:
   - `archive_id = get_archive_identifier(kp_id)`
   - `if not archive_id: _search_archive_identifier(title_en or title_ru, year)`
   - `_fetch_ia_description(archive_id)` → `_apply_description_to_ui`
6. `_fetch_ia_description(archive_id)` — GET `metadata/{id}`, `_clean_ia_description`
7. `_search_archive_identifier(title, year)` — Lucene escape,
   `title:("{safe}") AND year:[{y-1} TO {y+1}] AND mediatype:(movies)`, rows=5
8. `handle_resume_dismiss(movie_id)` — `QMessageBox.question` →
   `clear_history_entry` → `resume_island.hide()`
9. `check_resume_island()` — `get_last_session()`, если > 5 → `show_resume_bar`

**Проверка:** карточка → детали с title/year, описание через 5s если нет в БД.

---

### T-5.3: `controllers/orchestrator.py`

**Время:** 12 min
**Файлы:** `controllers/orchestrator.py` (create)
**Зависит от:** T-3.2, T-5.1, T-5.2

**Шаги:**
1. `class AmagiApplicationOrchestrator(loop)`:
   - `web_fetcher = WebFetcher()`, `archive_org = ArchiveOrgSearcher()`,
     `kp_service = KPService()`, `balancer_client = BalancerClient()`
   - `cleanup_startup()`, `init_db()`, `init_whitelist_db()`
2. `start_orchestration()`:
   - `LegalGateDialog` → `if not Accepted: QApplication.quit(); return`
   - `if config.LEGAL_ONLY_MODE: QTimer.singleShot(0, _on_public_boot); return`
   - (private — wizard, в этом плане не реализуем)
3. `_on_success_setup(manager)`:
   - `session = aiohttp.ClientSession()`
   - `main_window = MainWindow()`
   - `playback = PlaybackController(main_window.player_page, main_window)`
   - `feed = FeedController(self)`, `details = DetailsController(self)`,
     `stream = StreamController(self)`
   - Connect signals (см. код)
   - `search_debounce = QTimer(main_window)` — singleShot 400ms,
     `timeout` → `feed.run_search`
   - `search_bar.textChanged` → `feed.on_search_text_changed`
   - `main_window.show()`
   - `_start_periodic_cleanup()` — QTimer 60s
   - `create_task(_async_boot())` — `await feed.load_feed(clear_grid=True)`,
     `details.check_resume_island()`
4. `async shutdown_async()` — закрытие session, cleanup_all

**Проверка:** полный флоу — карточка → детали → стрим → play → close → feed.

---

## Phase 6: Verify

### T-6.1: E2E smoke test

**Время:** 5 min
**Файлы:** —

**Шаги:**
1. `python main.py` — карточки + постеры видны
2. Клик на карточку → детали с title/year/desc
3. «Запустить трансляцию» → loader → видео играет
4. Seek на 5:00 → прыжок
5. Close → feed → островок «Продолжить» появился
6. Клик на островок → возобновление с 5:00

**Проверка:** все 6 шагов работают без ошибок.

---

### T-6.2: Failure modes

**Время:** 5 min
**Файлы:** —

**Шаги:**
1. Поиск `nonexistent_xyz_12345` → пусто / «НИЧЕГО НЕ НАЙДЕНО»
2. Отключить сеть → поиск «The Kid» → «ФИЛЬМ НЕ НАЙДЕН», без крэша
3. Восстановить сеть → стрим работает
4. Закрыть приложение → открыть → история сохранилась

**Проверка:** ни один сценарий не крэшит, все дают понятное сообщение.

---

### T-6.3: No zombies

**Время:** 2 min
**Файлы:** —

**Шаги:**
1. Открыть фильм, воспроизвести, закрыть приложение
2. `tasklist | findstr amagi-player` — пусто
3. `tasklist | findstr python` — пусто (кроме текущего терминала)

**Проверка:** нет висящих процессов.

---

## Phase 7: Docs

### T-7.1: `README.md`

**Время:** 10 min
**Файлы:** `README.md` (create)

**Шаги:**
1. Tagline: «Stream public-domain cinema from Internet Archive»
2. Features (5–6 bullet'ов): curated catalog, HTTP Range streaming,
   two themes, async architecture, no telemetry
3. Quick start (3 шага: download → unpack → run)
4. Requirements (Windows 10/11, Python 3.10+ для source)
5. License (GPLv3)

**Проверка:** README рендерится на GitHub, ссылки работают.

---

### T-7.2: `LICENSE`

**Время:** 2 min
**Файлы:** `LICENSE` (create)

**Шаги:**
1. Скопировать полный текст GPLv3 с
   `https://www.gnu.org/licenses/gpl-3.0.txt`

**Проверка:** файл существует, текст полный.

---

## Phase 8: CI

### T-8.1: `.github/workflows/tests.yml`

**Время:** 8 min
**Файлы:** `.github/workflows/tests.yml` (create)

**Шаги:**
1. `on: [push, pull_request]`
2. `runs-on: windows-latest`
3. `strategy.matrix.python-version: ["3.11", "3.12", "3.13"]`
4. Steps: checkout → setup-python → `pip install -r requirements.txt` →
   `python -c "import PyQt6.QtWidgets; print('ok')"` → `pytest`

**Проверка:** CI green на push.

---

### T-8.2: `.github/workflows/release.yml`

**Время:** 10 min
**Файлы:** `.github/workflows/release.yml` (create)

**Шаги:**
1. `on: push: tags: ["v*"]`
2. Job `build-windows`:
   - checkout, setup-python 3.13
   - `pip install -r requirements.txt nuitka ordered-set zstandard`
   - `python -m nuitka --standalone --enable-plugin=pyqt6
     --include-qt-plugins=multimedia --include-data-dir=data=data
     --include-data-dir=ui=ui --windows-icon-from-ico=assets/icon.ico
     --output-dir=dist main.py`
   - `Compress-Archive`
   - `upload-artifact`
3. Job `create-release`: `softprops/action-gh-release@v2` с артефактами

**Проверка:** push tag → релиз с ZIP.

---

### T-8.3: Локальный build

**Время:** 10 min
**Файлы:** —

**Шаги:**
1. `python -m nuitka --standalone --enable-plugin=pyqt6
   --include-data-dir=data=data --include-data-dir=ui=ui main.py`
2. Запустить `main.dist/main.exe`
3. Убедиться, что `main.dist/data/` и `main.dist/ui/` существуют

**Проверка:** exe запускается, окно открывается, лента грузится.

---

## Чек-лист готовности плана

- [x] Все `<!-- -->` удалены
- [x] Все placeholder'ы заменены
- [x] Каждая задача ≤ 12 минут (максимум в T-3.2, T-4.5, T-5.3)
- [x] Каждая задача имеет конкретную проверку
- [x] Фазы идут от фундамента к UI
- [x] Phase Verify покрывает E2E + failure + zombies
- [x] Out of scope заполнен
- [x] Estimated реалистичен (4–6 часов для джуна, с запасом)
- [x] Key risk назван честно (DVD-контейнеры)
