# Plan 01: Public Streaming from Internet Archive

> **Цель:** клик на карточку → экран деталей → «Запустить трансляцию» →
> видео играет из IA → seek работает → закрытие возвращает в ленту.
>
> **Зависимости:** нет (первый план, база).
>
> **Вне рамок:** P2P (Plan 02), fallback (Plan 03), Jackett/WebFetcher
> (Plan 04), switch_mode (Plan 05), скачивание, субтитры.
>
> **Оценка:** 5–7 часов для джуна без контекста.
>
> **Главный риск:** Internet Archive возвращает DVD-контейнеры (mpeg),
> которые ломаются при seek. Решается приоритетом формата (T-2.4), но
> если в элементе только mpeg — придётся его использовать.

---

## Содержание

- [Phase -1: Contracts & Stubs](#phase--1-contracts--stubs) — 2 задачи
- [Phase 0: Setup](#phase-0-setup) — 5 задач
- [Phase 1: Data layer](#phase-1-data-layer) — 4 задачи
- [Phase 2: IA search](#phase-2-ia-search) — 4 задачи
- [Phase 3: StreamController](#phase-3-streamcontroller) — 3 задачи
- [Phase 4: UI](#phase-4-ui) — 6 задач
- [Phase 5: Wiring](#phase-5-wiring) — 3 задачи
- [Phase 6: Verify](#phase-6-verify) — 3 задачи
- [Phase 7: Docs](#phase-7-docs) — 2 задачи
- [Phase 8: CI](#phase-8-ci) — 3 задачи

**Итого:** 35 задач, ~5–7 часов.

---

## Как читать этот план

Каждая задача имеет одинаковую структуру:

```
### T-X.Y: Название задачи

**Время:** сколько минут   **Файлы:** что создать/изменить   **Зависит от:** T-A.B

**Что делать:** 3–6 шагов, каждый — одно действие.

**Проверка:** конкретная команда или assert, который должен пройти.
```

**Инвариант** — правило, которое нельзя нарушить. Если нарушишь — будет
баг, который проявится позже. Инварианты выделены отдельно.

**Если застрял** — не угадывай. Смотри `config.py` (все константы),
`T--1.1` (все stubs), или спроси.

---

## Phase -1: Contracts & Stubs

**Зачем эта фаза:** Plan 01 использует `safe_archive_org`, `KPService`,
`WebFetcher`, `LegalGateDialog` — но они создаются в других планах.
Без stubs джун получит `ImportError` через 10 минут. Эта фаза создаёт
«пустышки» и все константы `config.py`, чтобы дальше всё работало.

---

### T--1.1: Все stubs-классы и функции

**Время:** 20 min
**Файлы:** 11 файлов (см. ниже)
**Зависит от:** T-0.1

**Что создать:**

| Файл | Что | Куда используется |
|---|---|---|
| `core/utils.py` | `dedup_by_url(items)`, `sanitize_query(s)` | T-3.1, T-5.1 |
| `search/aggregator/tasks/archive_org.py` | `safe_archive_org(searcher, query, year)` | T-3.1 |
| `services/kp_service.py` | `KPService` — 4 stub-метода | T-5.1 (private) |
| `services/balancer_client.py` | `BalancerClient.search()` → `[]` | T-5.3 |
| `search/web_fetcher/fetcher.py` | `WebFetcher` — `is_disabled()` → `True` | T-5.3 |
| `search/jackett_client.py` | `JackettClient` — `diagnose()`, `search_all()` | T-5.3 |
| `search/prowlarr_client.py` | `ProwlarrClient` — аналогично | T-5.3 |
| `legal_gate.py` | `LegalGateDialog(QDialog)` — кнопка «Принять» | T-5.3 |
| `legal_texts.py` | Тексты дисклеймера | T-5.3 |
| `services/process_cleaner.py` | `cleanup_startup()`, `cleanup_all()` | T-5.3 |
| `core/__init__.py`, `search/aggregator/tasks/__init__.py` | Пустые | — |

**Шаги:**

1. `core/utils.py`:
   - `dedup_by_url(items) -> list[dict]` — убрать дубликаты по `item["url"]`
   - `sanitize_query(s) -> str` — убрать `:;,!'"()[]{}<>`, сжать пробелы

2. `search/aggregator/tasks/archive_org.py`:
   - `safe_archive_org(searcher, query, year)` — обёртка с `asyncio.wait_for(timeout=30.0)`.
     При timeout/exception → `[]`.

3. `services/kp_service.py` — `class KPService`:
   - `get_movie_data(session, kp_id) -> dict` → `{}`
   - `search_movies_by_keyword(session, query, page=1) -> list` → `[]`
   - `get_popular_movies(session, page=1) -> list` → `[]`
   - `log_stats() -> None` → `pass`

4. Остальные stubs — минимальные классы с методами, возвращающими
   `[]`, `{}`, `True`, `None`.

5. `legal_gate.py` — `QDialog` с кнопкой «Принять». При клике — `self.accept()`.

**Проверка:**

```bash
python -c "import core.utils, legal_gate, services.kp_service, services.balancer_client"
python -c "from search.aggregator.tasks.archive_org import safe_archive_org"
python -c "from search.web_fetcher.fetcher import WebFetcher; print(WebFetcher().is_disabled())"
# → True
```

**Инвариант:** stub-классы должны иметь **те же сигнатуры методов**,
что настоящие (в других планах). Иначе при замене stubs на реализацию
получим `TypeError`.

---

### T--1.2: `config.py` — все константы

**Время:** 15 min
**Файлы:** `config.py` (append)
**Зависит от:** T-0.3

**Что добавить:**

1. **Режим** — читать из `data/mode.txt`, дефолт `public`:
   ```
   MODE, LEGAL_ONLY_MODE, DISABLE_WHITELIST, SEARCH_LANGUAGE,
   LAZY_RESOLVE, USE_WHITELIST, LEGAL_TRACKERS_TAG, LEGAL_FEED_ONLY_AVAILABLE
   ```
   Для `public`: `LEGAL_ONLY_MODE=True`, `DISABLE_WHITELIST=False`,
   `SEARCH_LANGUAGE="en"`.

2. **IA:**
   ```
   ARCHIVE_ORG_ENABLED = True
   ARCHIVE_ORG_MAX_FILE_SIZE = 4 GB
   ARCHIVE_ORG_METADATA_CACHE_TTL = 86400  (24ч)
   ARCHIVE_ORG_METADATA_CACHE_MAX = 500
   ARCHIVE_ORG_MIN_MOVIE_SIZE = 30 MB
   ```

3. **Кэш:** `POPULAR_CACHE_TTL_HOURS=24`, `SEARCH_CACHE_TTL_HOURS=6`,
   `SHORT_CACHE_TTL_HOURS=720`.

4. **Дисклеймер:** `LEGAL_DISCLAIMER_ACCEPTED=False`.

5. **Downloads:** `DOWNLOADS_MAX_GB=50`, `DOWNLOADS_CLEANUP_ON_START=True`.

**Проверка:**

```bash
python -c "import config; print(config.LEGAL_ONLY_MODE, config.ARCHIVE_ORG_MIN_MOVIE_SIZE, config.SEARCH_LANGUAGE)"
# → True 31457280 en
```

---

## Phase 0: Setup

**Зачем:** скелет проекта — директории, зависимости, конфиг, логирование,
минимальное окно. После этой фазы `python main.py` открывает пустое окно.

---

### T-0.1: Директории + `__init__.py`

**Время:** 3 min
**Файлы:** директории + пустые `__init__.py`
**Зависит от:** —

**Что делать:**

1. Создать:
   - `ui/`, `ui/widgets/`
   - `controllers/`, `controllers/stream/`
   - `services/`
   - `search/`, `search/archive_org/`, `search/aggregator/`,
     `search/aggregator/tasks/`, `search/web_fetcher/`
   - `database/`, `core/`
2. `__init__.py` в каждой (пустые)
3. `main.py`, `config.py` в корне

**Проверка:**

```bash
python -c "import ui, controllers, services, search, database, core"
```

---

### T-0.2: `requirements.txt`

**Время:** 2 min
**Файлы:** `requirements.txt` (create)
**Зависит от:** T-0.1

**Что делать:**

1. Записать 7 пакетов (точные версии обязательны — PyQt6 и Qt6
   должны быть из одной серии):
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

---

### T-0.3: `config.py` — базовые пути

**Время:** 4 min
**Файлы:** `config.py` (append)
**Зависит от:** T-0.1

**Что делать:**

1. `BASE_DIR` — директория `config.py`
2. Пути: `DATA_DIR`, `CACHE_DIR`, `DB_PATH`, `WHITELIST_DB_PATH`,
   `DOWNLOADS_DIR`, `LOGS_DIR`
3. Подпапки кэша: `CACHE_SHORT_DIR`, `CACHE_FULL_DIR`, `CACHE_LISTS_DIR`
4. Сеть: `NETWORK_TIMEOUT=15`, `USER_AGENT="AmagiPlayer/2.0"`
5. `os.makedirs(..., exist_ok=True)` для всех директорий

**Проверка:**

```bash
python -c "import config; print(config.DATA_DIR.exists(), config.CACHE_SHORT_DIR.exists())"
# → True True
```

**Инвариант:** все директории существуют **при импорте** `config`,
не при первом использовании. Иначе `FileNotFoundError` в середине стрима.

---

### T-0.4: `core/logging_setup.py`

**Время:** 3 min
**Файлы:** `core/logging_setup.py` (create)
**Зависит от:** T-0.3

**Что делать:**

1. `setup_logging(level=INFO)`:
   - очистить root handlers (защита от двойной инициализации)
   - `StreamHandler` с форматом
     `[%(asctime)s] %(levelname)-7s %(name)-20s | %(message)s`
2. `get_logger(name) -> Logger` — вызывает `setup_logging()`, возвращает logger
3. Подавить шум: `aiohttp.access`, `asyncio`, `urllib3` → `WARNING`

**Проверка:**

```bash
python -c "from core.logging_setup import get_logger; get_logger('test').info('hello')"
# → [HH:MM:SS] INFO    test                 | hello
```

---

### T-0.5: `main.py` — минимальное окно

**Время:** 4 min
**Файлы:** `main.py` (create)
**Зависит от:** T-0.2, T-0.4

**Что делать:**

1. `QApplication(sys.argv)`
2. `qasync.QEventLoop(app)` — единый event loop для Qt и asyncio
3. `asyncio.set_event_loop(loop)`
4. `loop.run_forever()`

**Проверка:**

```bash
python main.py
```
Пустое окно открывается, `Ctrl+C` завершает.

**Инвариант:** без qasync `await` не работает в Qt-слотах. Не использовать
`QThread` — это отдельный поток, гонки с UI.

---

## Phase 1: Data layer

**Зачем:** SQLite-базы. После этой фазы можно читать/писать каталог и историю.

---

### T-1.1: `database/connection.py`

**Время:** 5 min
**Файлы:** `database/connection.py` (create)
**Зависит от:** T-0.3

**Что делать:**

1. `get_connection() -> Connection`:
   - `sqlite3.connect(config.DB_PATH)`
   - `PRAGMA journal_mode=WAL` — параллельное чтение без блокировок
   - `row_factory = sqlite3.Row` — доступ по имени столбца
2. `@contextmanager use_connection()` — commit / rollback / close
3. `init_db()`:
   - `schema_version(version INTEGER PRIMARY KEY)`
   - `user_history(kp_id INTEGER PRIMARY KEY, movie_title TEXT NOT NULL,
     current_seconds INTEGER NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`
   - индекс `idx_history_updated ON user_history(updated_at DESC)`

**Проверка:**

```python
from database.connection import init_db, use_connection
init_db()
with use_connection() as conn:
    conn.execute("INSERT INTO user_history (kp_id, movie_title, current_seconds) VALUES (1, 'X', 42)")
with use_connection() as conn:
    assert conn.execute("SELECT current_seconds FROM user_history WHERE kp_id = 1").fetchone()["current_seconds"] == 42
```

---

### T-1.2: `database/whitelist_db.py`

**Время:** 6 min
**Файлы:** `database/whitelist_db.py` (create)
**Зависит от:** T-1.1

**Что делать:**

1. `_pynorm(v) -> str` — `v.lower().replace("ё", "е")`.
   **Зачем:** SQLite `LOWER()` не работает для кириллицы (только ASCII).
2. `_connect()` — WAL, `Row`, `create_function("PYNORM", 1, _pynorm)`
3. `@contextmanager use_whitelist_connection()`
4. `init_whitelist_db()`:
   - `movie_whitelist(kp_id INTEGER PRIMARY KEY, title_ru TEXT NOT NULL,
     title_en TEXT DEFAULT '', year TEXT DEFAULT '',
     archive_identifier TEXT DEFAULT '',
     added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     available INTEGER DEFAULT NULL)`
   - индексы на `available`, `title_ru`, `title_en`

**Проверка:**

```python
from database.whitelist_db import init_whitelist_db, use_whitelist_connection
init_whitelist_db()
with use_whitelist_connection() as conn:
    conn.execute("INSERT INTO movie_whitelist (kp_id, title_ru, year) VALUES (1, 'Матрица', '1999')")
    rows = conn.execute("SELECT * FROM movie_whitelist WHERE PYNORM(title_ru) LIKE ?", ("%матрица%",)).fetchall()
    assert len(rows) == 1
```

**Инвариант:** `available = NULL` — «не проверен», `= 1` — доступен,
`= 0` — недоступен. В public лента показывает `(available = 1 OR available IS NULL)`.

---

### T-1.3: `database/whitelist_repo.py`

**Время:** 6 min
**Файлы:** `database/whitelist_repo.py` (create)
**Зависит от:** T-1.2

**Что делать:**

1. `class WhitelistRepository` — статические методы
2. `search_movies_in_feed(query="", limit=20, offset=0) -> list[int]`:
   - WHERE: `(available = 1 OR available IS NULL)`
   - если query: `AND (PYNORM(title_ru) LIKE ? OR PYNORM(title_en) LIKE ?
     OR year LIKE ?)`, параметры `f"%{qn}%"`, `qn = query.lower().replace("ё", "е")`
   - ORDER BY `kp_id DESC`, LIMIT, OFFSET
   - возвращает **только `kp_id`**, не все row
3. `get_movie(kp_id) -> dict | None`
4. `get_archive_identifier(kp_id) -> str`
5. `count()`, `count_available()`

**Проверка:**

```python
from database.whitelist_repo import WhitelistRepository
assert 1 in WhitelistRepository.search_movies_in_feed("матрица")
assert WhitelistRepository.get_movie(1)["title_ru"] == "Матрица"
```

**Инвариант:** `search_movies_in_feed` возвращает **только ID**, не row.
`get_movie` отдельно. Это N+1, но для 20 карточек незаметно.

---

### T-1.4: `database/history_repo.py`

**Время:** 5 min
**Файлы:** `database/history_repo.py` (create)
**Зависит от:** T-1.1

**Что делать:**

1. `save_timestamp(kp_id, movie_title, current_seconds)`:
   - UPSERT: `INSERT ... ON CONFLICT(kp_id) DO UPDATE SET
     current_seconds = MAX(excluded.current_seconds, user_history.current_seconds),
     updated_at = CURRENT_TIMESTAMP`
   - **Зачем MAX:** не сбрасывать больший прогресс меньшим (отмотал на 5,
     закрыл на 3 — должно остаться 5)
2. `get_last_session() -> dict | None` — `ORDER BY updated_at DESC LIMIT 1`
3. `get_seconds_for_movie(kp_id) -> int`
4. `clear_history_entry(kp_id)`, `clear_all() -> int`

**Проверка:**

```python
from database.history_repo import HistoryRepository
HistoryRepository.save_timestamp(1, "X", 42)
HistoryRepository.save_timestamp(1, "X", 30)
assert HistoryRepository.get_seconds_for_movie(1) == 42
HistoryRepository.save_timestamp(1, "X", 60)
assert HistoryRepository.get_seconds_for_movie(1) == 60
```

---

## Phase 2: IA search

**Зачем:** поиск в Internet Archive. После этой фазы можно найти фильм
и получить URL файла — без UI.

---

### T-2.1: `search/archive_org/language.py` — `lang_score`

**Время:** 5 min
**Файлы:** `search/archive_org/language.py` (create)
**Зависит от:** T-0.4

**Что делать:**

1. `_PREFERRED_EN_MATCH = ("english", "eng", "american", "british", "usa", "uk", "silent")`
2. `_PREFERRED_RU_MATCH = ("russian", "rus", "soviet", "ussr", "silent")`
3. `_EN_OTHER_LANGS` — список: russian, german, french, polish, czech,
   spanish, italian, japanese, chinese, portuguese, dutch, swedish, danish,
   norwegian, finnish, hungarian, romanian, greek, turkish, hebrew, arabic,
   hindi, korean
4. `lang_score(actual, preferred, year="") -> float`:
   - `if year and int(year) < 1930: return 0.9` — silent era, язык часто
     ошибочен (язык субтитров, а не оригинала)
   - `if not actual: return 0.5` — нет данных, нейтрально
   - `if "silent" in a or "no linguistic" in a or "music only" in a: return 0.9`
   - preferred="en": match → 1.0, other → 0.0, иначе 0.5
   - preferred="ru": match → 1.0, other → 0.0, иначе 0.5

**Проверка:**

```python
from search.archive_org.language import lang_score
assert lang_score("English", "en") == 1.0
assert lang_score("Russian", "en") == 0.0
assert lang_score("", "en") == 0.5
assert lang_score("Russian", "en", year="1925") == 0.9
assert lang_score("Silent film", "en") == 0.9
```

**Инвариант:** для `year < 1930` **не** возвращать 0.0 даже если язык
явно чужой. Иначе отсеем всё раннее кино.

---

### T-2.2: `search/archive_org/language.py` — `title_score`

**Время:** 4 min
**Файлы:** `search/archive_org/language.py` (append)
**Зависит от:** T-2.1

**Что делать:**

1. `_STOPWORDS = frozenset({"the", "and", "of", "a", "an", "in", "on",
   "for", "with", "to", "by"})`
2. `title_score(identifier, title, query) -> float`:
   - `q_words = [w for w in query.lower().split() if len(w) >= 3
     and w not in _STOPWORDS]`
   - если пусто — fallback `[w for w in query.lower().split() if len(w) >= 2]`
   - если всё ещё пусто — `0.5`
   - `target = (identifier + " " + title).lower()`
   - `return sum(1 for w in q_words if w in target) / len(q_words)`

**Проверка:**

```python
assert title_score("the_kid_1921", "The Kid", "the kid") == 1.0
assert title_score("random", "Random", "the kid") == 0.0
assert title_score("the_kid_1921", "The Kid", "the") == 0.5
```

---

### T-2.3: `search/archive_org/searcher.py`

**Время:** 10 min
**Файлы:** `search/archive_org/searcher.py` (create)
**Зависит от:** T-2.1, T-2.2, T-0.3

**Что делать:**

1. `_FETCH_LIMIT = 30`, `_FINAL_LIMIT = 15`
2. `_escape_lucene(s) -> str` — regex `([+\-&|!(){}\[\]^"~*?:\\/])` → `\\\1`.
   **Зачем:** `Spider-Man: Brand New Day` — двоеточие ломает Lucene.
3. `class ArchiveOrgSearcher`:
   - `_session`, `_metadata` (lazy)
   - `_ensure_session()` — `aiohttp.ClientSession(timeout=15)`
4. `_search_identifiers(query, year, use_mediatype=True) -> list[dict]`:
   - Lucene: `title:("{escaped}")`
   - если year: `year:[{y-2} TO {y+2}]` — допуск ±2
   - если флаг: `mediatype:(movies)`
   - GET `https://archive.org/advancedsearch.php` с параметрами:
     `q`, `fl[]=identifier,title,year,downloads,language,creator`,
     `sort[]=downloads desc`, `rows={_FETCH_LIMIT}`, `output=json`
   - ошибка → `[]`
5. `search(query, year="") -> list[dict]`:
   - **каскад:**
     - `docs = _search_identifiers(q, year, True)`
     - `if not docs and year: docs = _search_identifiers(q, year, False)`
     - `if not docs and year: docs = _search_identifiers(q, "", True)`
     - `if not docs: docs = _search_identifiers(q, "", False)`
   - **скоринг:** для каждого `total = lang_score * 100 + title_score * 50
     + downloads_score * 20`, где `downloads_score = min(1.0, downloads / 5000)`
   - sort desc, top 15
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
(нужен интернет)

**Инвариант:** каскад **останавливается** на первом непустом результате.
Не «объединить всё» — раздует пул мусором.

---

### T-2.4: `search/archive_org/metadata.py`

**Время:** 10 min
**Файлы:** `search/archive_org/metadata.py` (create)
**Зависит от:** T-0.3

**Что делать:**

1. Константы:
   - `_VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v",
     ".ogv", ".mpg", ".mpeg", ".wmv")`
   - `_FORMAT_PRIORITY = {".mp4": 100, ".webm": 95, ".mkv": 90, ".m4v": 85,
     ".ogv": 50, ".mov": 40, ".avi": 20, ".wmv": 15, ".mpg": 5, ".mpeg": 3}`
   - `_STREAMING_UNFRIENDLY = {".mpeg", ".mpg", ".wmv"}` (для логов)
   - `_TRAILER_SIZE_BYTES = 50 MB`
   - `_MIN_FULL_MOVIE_BYTES = 30 MB`, `_MAX_FILE_SIZE = 4 GB`
2. `_LRUCache(maxsize=500, ttl=86400)` — `get/put/contains`, `move_to_end`
3. `class MetadataFetcher(session)`:
   - `find_video_file(identifier) -> dict | None`:
     - кэш → return
     - GET `metadata/{identifier}`
     - `files = data["files"]`
     - `_pick_best_video(identifier, files)`
     - `_CACHE.put(identifier, result)`
   - `_pick_best_video(identifier, files) -> dict | None`:
     - для каждого file: video ext, `30 MB ≤ size ≤ 4 GB`,
       `not (trailer_by_name and size < 50 MB)`
     - `friendly = [c for c in candidates if priority >= 40]`
     - `pool = friendly or candidates`
     - sort `(priority, size)` desc, `pool[0]`
     - return `{url, size, format, filename, ext, priority}`
   - `find_videos_parallel(identifiers)` — `asyncio.gather`, фильтр None

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

**Инвариант:** если `friendly` пуст — fallback на mpeg/wmv с логом
`only unfriendly format {ext} available`. Не отбрасывать элемент полностью.
Лучше что-то, чем ничего.

---

## Phase 3: StreamController

**Зачем:** связать поиск и плеер. После этой фазы клик «Запустить
трансляцию» в public находит URL и запускает QMediaPlayer.

---

### T-3.1: `controllers/stream/cascade.py`

**Время:** 8 min
**Файлы:** `controllers/stream/cascade.py` (create)
**Зависит от:** T-2.3, T-2.4

**Что делать:**

1. `class CascadeExecutor(controller)` — `loop`, `main_window`, `playback`
2. `async execute(meta, movie_id, movie_title, year)`:
   - `archive_query = title_en or title_ru`
   - `archive_results = await safe_archive_org(searcher, archive_query, year)`
   - `if not archive_results and archive_query != title_ru:`
     `archive_results = await safe_archive_org(searcher, title_ru, year)`
   - `unique = dedup_by_url(archive_results)`
   - `if not unique: loader_label.setText("ФИЛЬМ НЕ НАЙДЕН"); stream_in_progress=False; return`
   - `await _dispatch(unique, ...)`
3. `_dispatch` для public:
   - `direct = [s for s in sources if s["type"] == "direct_url"]`
   - sort `(priority, size)` desc
   - `chosen = direct[0]`
   - `playback.play_url(chosen["url"], movie_id, movie_title)`
   - `stream_in_progress = False`

**Проверка:** в логах `archive.org: N direct_url`, `PUBLIC: https://...`.

**Инвариант:** вызывать только `safe_archive_org` (timeout 30s), не
`searcher.search` напрямую — рискуем зависнуть на плохой сети.

---

### T-3.2: `controllers/stream/stream_controller.py`

**Время:** 12 min
**Файлы:** `controllers/stream/stream_controller.py` (create)
**Зависит от:** T-3.1

**Что делать:**

1. Константы:
   - `_CLOSE_STOP_TIMEOUT_SEC = 25.0`
   - `_CLOSING_WATCHDOG_MS = 30000`
   - `_PLAYER_RELEASE_DELAY_MS = 200`
2. `class StreamController(app)` — поля:
   - `loop`, `main_window`, `playback`, `session`, `archive_org`
   - `cascade`, `fallback` (stub), `buffer` (stub)
   - **состояние:** `stream_session=None`, `stream_in_progress=False`,
     `_closing_in_progress=False`, `_pending_start_kp_id=None`,
     `_current_movie_id/Title/Year`,
     `_online_sources/_p2p_fallback/_direct_fallback/_direct_index`
3. **Сигналы:**
   - `player_page.close_player_requested` → `handle_close_player`
   - `player_page.skip_requested` → `_on_skip`
   - `playback.demux_error` → `_on_demux_error`
4. `handle_stream_start(kp_id)`:
   - `if _closing_in_progress: _pending_start_kp_id = kp_id; return`
   - `if stream_in_progress: return`
   - `stream_in_progress = True`, `_current_movie_id/Title/Year` из meta
   - `fallback.reset()`, сброс fallback-списков
   - `screen_stack.setCurrentIndex(2)`, `show_loader`,
     `loader_label.setText("ПОИСК ПОТОКОВ...")`
   - `create_task(cascade.execute(meta, ...))`
5. `handle_close_player(_seconds)`:
   - `_closing_in_progress = True`
   - `QTimer.singleShot(_CLOSING_WATCHDOG_MS, self._closing_watchdog)`
   - `playback.stop_and_save()`
   - `QTimer.singleShot(_PLAYER_RELEASE_DELAY_MS, self._start_close_async)`
6. `_start_close_async()` — `create_task(self._close_player_async())`
7. `_closing_watchdog()`:
   - `if not _closing_in_progress: return`
   - `log.warning("WATCHDOG: _closing_in_progress залип")`
   - `_closing_in_progress = False`
   - запустить `_pending_start_kp_id`, если есть
8. `async _close_player_async()`:
   - `try: await wait_for(_stop_resources(), timeout=25.0)`
   - `except TimeoutError: log.warning`
   - `finally: stream_in_progress=False; fallback.reset(); сбросы;
     screen_stack.setCurrentIndex(0); check_resume_island(); _closing_in_progress=False`
   - `if _pending_start_kp_id: pending = ...; _pending_start_kp_id = None;
     handle_stream_start(pending)`
9. `_try_next_direct()`:
   - `if not _player_is_active(): return`
   - `_direct_index += 1`
   - `if _direct_index >= len(_direct_fallback): loader_label.setText("Все испробованы"); return`
   - `fallback.reset(); play_url(chosen, ...)`
10. `_player_is_active()` — `screen_stack.currentIndex() == 2`
11. `async _stop_resources()`:
    - `session = self.stream_session; self.stream_session = None`
    - `if session: await session.cancel()`
12. `_on_demux_error()` — `fallback.on_demux_error()`
13. `_on_buffer_fallback(force)` — `buffer.stop()`, если force —
    `fallback.do_auto_fallback()`, иначе `create_task(_online_to_p2p())`

**Проверка:** клик → loader → видео; close → возврат в ленту; быстрое
переключение (закрыл → сразу другой) → второй стрим запускается.

**Инварианты:**
- `handle_close_player` не блокирует main thread — `stop_and_save` sync,
  но `cancel` через 200ms.
- `_stop_resources` **отвязывает ссылку до await** — иначе два параллельных
  вызова оба вызовут `session.cancel()` на одном объекте.
- `_closing_watchdog` 30s — защита от дедлока.

---

### T-3.3: `services/playback_controller.py`

**Время:** 10 min
**Файлы:** `services/playback_controller.py` (create)
**Зависит от:** T-0.5

**Что делать:**

1. `class PlaybackController(QObject)`, `demux_error = pyqtSignal()`
2. `__init__`:
   - `QMediaPlayer()`, `QAudioOutput()`, `player.setAudioOutput`
   - `_timer = QTimer(500ms)` → `_tick_ui`
   - `_error_emit_pending = False`, `_resume_seconds = 0`
   - connect `player.errorOccurred` → `_on_player_error`
   - connect UI: play/pause, fullscreen, timeline (seek_requested)
3. `play_url(stream_url, movie_id, title)`:
   - `_resume_seconds = HistoryRepository.get_seconds_for_movie(movie_id)`
   - `show_video()`, `setVideoOutput(video_widget)`
   - `if _resume_seconds > 5: mediaStatusChanged.connect(_on_media_status_seek)`
   - `setSource(QUrl(stream_url))`, `play()`, `_timer.start()`
4. `_on_media_status_seek(status)`:
   - на `LoadedMedia`: `setPosition(_resume_seconds * 1000)`, disconnect
5. `stop_stream(save=False)`:
   - `_timer.stop()`, `real_seconds = position() // 1000`
   - **порядок: `setSource(QUrl())` → `stop()` → save**
   - **Почему:** `setSource` деактивирует источник → QMediaPlayer отпускает
     file handle → libtorrent может удалить torrent
   - `if save and real_seconds > 5: save_timestamp(...)`
6. `_on_player_error(error, error_string)`:
   - **не эмитить синхронно** из MF callback:
     `if _error_emit_pending: return; _error_emit_pending = True;
     QTimer.singleShot(0, self._emit_demux_error)`
7. `_tick_ui()` — 500ms: обновить slider (если не двигается) + time_label

**Проверка:** видео играет, seek работает, close отпускает file handle
(в логах libtorrent не «залипает» на 15s).

**Инварианты:**
- `setSource` **до** `stop`, не наоборот.
- `demux_error.emit()` **не синхронно** из `errorOccurred` — MF
  реентерабельный только в определённых состояниях, крешит.

---

## Phase 4: UI

**Зачем:** экраны приложения. После этой фазы есть лента, детали, плеер,
переключение темы.

---

### T-4.1: `ui/widgets/player_widget.py`

**Время:** 8 min
**Файлы:** `ui/widgets/player_widget.py` (create)
**Зависит от:** T-0.5

**Что делать:**

1. `class MoviePlayerWidget(QWidget)`, signals:
   `close_player_requested(int)`, `seek_requested(int)`, `skip_requested()`
2. Layout:
   - `QVBoxLayout`
   - top bar: `exit_btn` («✕ ЗАКРЫТЬ»), connect → `close_player_requested.emit(current_seconds)`
   - `center_stack = QStackedLayout()`: `video_widget` / `loader_container`
   - `loader_container`: `loader_label`, `p2p_progress` (QProgressBar h=2)
   - `controls_bar`: `timeline_slider` (0..1000), `play_pause_button` («⏸»),
     `time_label`, `skip_button` («⏭»), `fullscreen_button` («⛶»)
3. `show_loader()`, `show_video()` — `center_stack.setCurrentIndex`
4. `set_buffering_progress(percent)`
5. `_on_slider_pressed/released` — `_slider_moving` flag,
   на released `seek_requested.emit(value)`

**Проверка:** виджет рендерится, кнопки кликабельны, сигналы эмитят
(проверить `print` в слоте).

**Инвариант:** слайдер `0..1000`, не `0..duration`. Перевод в ms — в
`PlaybackController._handle_manual_seek`. Защита от ситуации, где duration
неизвестен (стрим грузится).

---

### T-4.2: `ui/widgets/details_widget.py`

**Время:** 8 min
**Файлы:** `ui/widgets/details_widget.py` (create)
**Зависит от:** T-0.5

**Что делать:**

1. `class MovieDetailsWidget(QWidget)`, signals:
   `start_streaming_requested(int)`, `back_to_feed_requested()`
2. Layout:
   - nav: `back_btn` («← НАЗАД К ФОНДУ»)
   - `QHBoxLayout`:
     - `big_cover` 300×450, `AlignTop`, `setScaledContents(True)`
     - text: `title_label` (`detailsTitle`), `year_label` (`detailsYear`),
       `desc_label` (`detailsDescription`, `setMaximumHeight(220)`),
       `play_btn` («ЗАПУСТИТЬ ТРАНСЛЯЦИЮ», `actionButton`, 280×46)
3. `update_movie_details(metadata)`: `_current_kp_id`, title upper, year,
   `update_description`, `update_cover`
4. `update_cover(path)` — QPixmap, placeholder «ОБЛОЖКА НЕДОСТУПНА»
5. `update_description(text)` — `_truncate_for_display(text, 450)` по границе
   слова, badge `(English)` если не кириллица (>30% не-кириллических букв)
6. `_on_play_clicked()` — `start_streaming_requested.emit(_current_kp_id)`

**Проверка:** title/year/desc/cover отображаются, клик эмитит kp_id.

**Инвариант:** `big_cover` с `AlignTop` — при длинном описании постер
не съезжает.

---

### T-4.3: `ui/widgets/card_widget.py`

**Время:** 5 min
**Файлы:** `ui/widgets/card_widget.py` (create)
**Зависит от:** T-0.5

**Что делать:**

1. Константы: `_CARD_W=220`, `_CARD_H=340`, `_POSTER_H=260`, `_BAR_H=80`
2. `class MovieCardWidget(QWidget)`, `play_requested = pyqtSignal(int)`
3. `setFixedSize(220, 340)`, `setCursor(PointingHandCursor)`
4. `cover_label` — `setGeometry(0, 0, 220, 260)`, `setScaledContents(True)`,
   objectName `coverPlaceholder`
5. `info_bar` — `setGeometry(0, 260, 220, 80)`, objectName `cardInfoBar`,
   `QVBoxLayout` (14, 12, 14, 12, spacing 4):
   - `title_label` (`cardTitle`, upper, wordWrap)
   - `year_label` (`cardYear`)
6. `mousePressEvent` — LeftButton → `play_requested.emit(kp_id)`
7. `update_poster(path)` — QPixmap, `setText("")` если OK

**Проверка:** карточка с постером и title, клик эмитит kp_id.

---

### T-4.4: `ui/widgets/feed_widget.py`

**Время:** 8 min
**Файлы:** `ui/widgets/feed_widget.py` (create)
**Зависит от:** T-4.3

**Что делать:**

1. `class MovieFeedWidget(QWidget)`, `next_page_requested = pyqtSignal()`
2. Layout:
   - `title_label` («ВЕРИФИЦИРОВАННЫЙ КУЛЬТУРНЫЙ ФОНД», `sectionTitle`)
   - `QScrollArea` (`widgetResizable`, `NoFrame`, прозрачный, scrollbar 0px)
   - `grid_container` (`gridContainer`), `QGridLayout` (spacing 30)
3. `_on_scroll_moved(value)`:
   - `if _end_reached: return`
   - `if _is_loading_next:`
     - `if max_scroll != _last_max_scroll: _is_loading_next = False; _last_max_scroll = max_scroll`
     - return
   - `_last_max_scroll = max_scroll`
   - `if max_scroll > 0 and (max_scroll - value) < 300:`
     `_is_loading_next = True; next_page_requested.emit()`
4. `begin_batch()` — `blockSignals(True)` scrollbar + `setUpdatesEnabled(False)`
5. `end_batch()` — `adjustSize()` (до отрисовки), `setUpdatesEnabled(True)`,
   `blockSignals(False)`
6. `reset_loading_state()` — `_is_loading_next=False`, `_last_max_scroll=0`
7. `reset_loading_flag()` — только `_is_loading_next=False`
8. `mark_end_reached()`, `mark_end_not_reached()`
9. `add_card_to_grid(card) -> bool`:
   - dedup по `_rendered_kp_ids` (set)
   - `row, col = idx // 4, idx % 4`
   - если дубликат — `card.deleteLater()`, return False
10. `clear_grid()` — remove all, clear set, scrollbar 0

**Проверка:** скролл до низа эмитит `next_page_requested`; повторный
скролл в том же положении — нет; дубликаты карточек не добавляются.

**Инвариант:** `_on_scroll_moved` **не** emit'ит, если `_is_loading_next=True`
и `max_scroll` не изменился. Без этого — бесконечный цикл (max_scroll растёт
после add, valueChanged срабатывает с прежним value, снова emit).

---

### T-4.5: `ui/main_window.py`

**Время:** 12 min
**Файлы:** `ui/main_window.py` (create)
**Зависит от:** T-4.1, T-4.2, T-4.4

**Что делать:**

1. `class MainWindow(QMainWindow)`, title «Amagi-Player», `resize(1150, 820)`
2. Signals: `theme_toggle_requested`, `settings_opened`,
   `resume_movie_requested(int)`, `resume_dismiss_requested(int)`,
   `language_changed(str)`
3. `_init_ui_core`:
   - **header_bar** (75px, `headerBar`):
     - `logo_label` («AMAGI», `logoLabel`)
     - `search_bar` (`searchBar`, 400px, «ПОИСК ПО КУЛЬТУРНОМУ ФОНДУ...»)
     - `language_btn` (48×32, `languageButton`, EN/RU)
   - **content**: `QStackedWidget` с `feed_page`, `details_page`,
     `player_page`, `settings_page_placeholder`
   - **bottom bar**: `theme_btn` («✦ СВЕТЛАЯ ТЕМА», `sysButton`),
     `settings_btn` («Настройки», `sysButton`)
4. **resume_island** (QFrame, `continueIsland`, 420×96, `hide()`):
   - `resume_label`, `resume_action_btn` («Продолжить просмотр»),
     `resume_close_btn` («×», 20×20)
5. `_load_stylesheet()` — `ui/styles.qss`
6. `show_resume_bar(movie_id, title)`:
   - `_current_resume_id = movie_id`
   - `resume_label.setText(f"<b>{title.upper()}</b>")`
   - `_reposition_resume_island()`: `x=(width-420)//2`, `y=height-96-95`
   - `_animate_resume_island_in()` — opacity + slide-up 260ms
7. `_on_language_btn_clicked`:
   - `_current_lang = "ru" if _current_lang == "en" else "en"`
   - `language_btn.setText(_current_lang.upper())`, `language_changed.emit`
8. `_toggle_theme_internal`:
   - toggle `_is_light_theme`
   - `setProperty("theme", "light" if _is_light_theme else "dark")`
   - для всех `findChildren(QWidget)`: unpolish + polish
   - `theme_btn.setText(...)` в зависимости от темы

**Проверка:** окно открывается, три экрана переключаются, header виден,
EN/RU кликается, тема переключается, островок показывается внизу по центру.

**Инвариант:** `resume_island` — не модальный, плавающий поверх.
Не `setModal(True)` — иначе блокирует клики по ленте.

---

### T-4.6: `ui/styles.qss`

**Время:** 8 min
**Файлы:** `ui/styles.qss` (create)
**Зависит от:** T-4.5

**Что делать:**

1. `QMainWindow, QStackedWidget, QScrollArea, QWidget#gridContainer
   { background-color: #000000; }`
2. `QLineEdit#searchBar`:
   - `background-color: #000000`, `border: 1px solid rgba(255,255,255,0.25)`
   - `border-radius: 12px`, `padding: 10px 16px`, `color: #FFF`, `font-size: 13px`
3. `QLabel#logoLabel` — `color: #FFF`, `font-size: 22px`, `font-weight: 900`,
   `letter-spacing: 5px`
4. `MovieCardWidget`:
   - `background-color: rgba(255,255,255,0.03)`
   - `border: 1px solid rgba(255,255,255,0.06)`, `border-radius: 20px`
5. `QWidget#cardInfoBar` — `background: transparent`
6. `QPushButton#actionButton`:
   - `background-color: #FFF`, `color: #000`, `border: none`
   - `border-radius: 12px`, `padding: 10px 22px`, `font-weight: 700`
7. `QPushButton#sysButton`:
   - `background-color: transparent`, `color: rgba(255,255,255,0.6)`
   - `border: 1px solid rgba(255,255,255,0.15)`, `border-radius: 12px`,
     `padding: 8px 16px`

**Проверка:** тёмная тема, белый текст, скруглённые карточки, кнопки
с правильным padding.

**Инвариант:** Qt QSS — **не** CSS. `background-color`, не `background`.
`padding: 10px 16px`, не `padding: 10 16`. Дефисы обязательны.

---

## Phase 5: Wiring

**Зачем:** связать всё вместе. После этой фазы полный флоу работает:
запуск → лента → детали → стрим → close.

---

### T-5.1: `controllers/feed_controller.py`

**Время:** 12 min
**Файлы:** `controllers/feed_controller.py` (create)
**Зависит от:** T-1.3, T-4.4

**Что делать:**

1. Константы: `PAGE_SIZE=20`, `_MIN_POSTER_BYTES=2000`,
   `_KP_MIN_INTERVAL=1.5`, `_KP_COOLDOWN_429_SEC=60.0`
2. `class FeedController(app)`:
   - `loop`, `main_window`, `session`, `kp_service`
   - `current_page=1`, `_search_generation=0`, `_pagination_lock=asyncio.Lock()`
3. `async load_feed(clear_grid=False) -> int`:
   - `if clear_grid: clear_grid(); reset_loading_state()`
   - `query = search_bar.text().strip()`
   - **public:** `offset = (page-1) * PAGE_SIZE`;
     `ids = WhitelistRepository.search_movies_in_feed(query, limit=PAGE_SIZE, offset=offset)`
   - **private:** `kp_service.get_popular_movies` / `search_movies_by_keyword`
   - `if generation != _search_generation: return 0`
   - `begin_batch()`:
     - для каждого id: `get_movie(id)`, `MovieCardWidget(...)`,
       `card.play_requested.connect(_on_card_clicked)`,
       `if add_card_to_grid(card):`
       - `if not cover_path: create_task(_load_poster_cascade(...))`
   - `end_batch()`, `if not has_more: mark_end_reached()`
4. `_load_poster_cascade(kp_id, card, title, title_en, year)`:
   - **порядок:** cache → seed → IA thumbnail → KP
   - `sip.isdeleted(card)` перед `update_poster` — защита от гонки
5. `run_search()`:
   - `_search_generation += 1`, `current_page=1`
   - `mark_end_not_reached()`, `reset_loading_state()`
   - `create_task(load_feed(clear_grid=True))`
6. `load_next_page()` — `create_task(_load_next_page_async())`
7. `async _load_next_page_async()`:
   - `if _pagination_lock.locked(): return`
   - `async with _pagination_lock`:
     - `prev_page = current_page; current_page += 1`
     - `try: added = await load_feed(clear_grid=False)`
     - `except: current_page = prev_page; reset_loading_flag(); return`
     - `if added == 0 and not _end_reached: reset_loading_flag()`
8. `_on_card_clicked(kp_id)` — `app.details.open(kp_id)`
9. `on_search_text_changed(_text)` — `app.search_debounce.stop(); start()`

**Проверка:** 20 карточек при старте, поиск фильтрует, скролл грузит
следующую страницу, быстрый ввод в поиск не дублирует карточки.

**Инвариант:** `_search_generation` защищает от race: пользователь ввёл
«abc», потом «xyz». Проверка `if generation != _search_generation: return 0`
отбрасывает устаревший.

---

### T-5.2: `controllers/details_controller.py`

**Время:** 10 min
**Файлы:** `controllers/details_controller.py` (create)
**Зависит от:** T-1.3, T-4.2

**Что делать:**

1. Константы: `_MIN_POSTER_BYTES=500`, `_IA_MIN_BYTES=500`,
   `_MAX_DESCRIPTION_LEN=500`
2. `_escape_lucene(s)` — regex `([+\-&|!(){}\[\]^"~*?:\\/])` → `\\\1`
3. `_is_cyrillic_dominant(text)` — `>30%` букв в `\u0400-\u04FF`
4. `_clean_ia_description(raw)` — list→join, `<br>`→`\n`, убрать теги,
   `html.unescape`, сжать пробелы, truncate до 500 по слову + «...»
5. `class DetailsController(app)` — `loop`, `main_window`, `session`, `kp_service`
6. `open(kp_id)` → `create_task(_open_details_page(kp_id))`
7. `async _open_details_page(kp_id)`:
   - `resume_island.hide()`
   - `cover_path = cache/{kp_id}.jpg` если size > 500
   - `if kp_id < 0: metadata = _metadata_from_whitelist(...)`
   - `set_movie_id(kp_id)`, `update_movie_details(metadata)`,
     `screen_stack.setCurrentIndex(1)`
   - `if not cover_path: create_task(_load_cover_for_details(...))`
   - `if not description: create_task(_load_description_for_details(...))`
8. `_metadata_from_whitelist(kp_id, cover_path)` — `desc_ru or desc_en`,
   title_ru, title_en, year, cover_path
9. `async _load_description_for_details(kp_id, title_en, title_ru, year)`:
   - `archive_id = get_archive_identifier(kp_id)`
   - `if not archive_id: archive_id = await _search_archive_identifier(...)`
   - `if not archive_id: _apply_description_to_ui(kp_id, ""); return`
   - `_apply_description_to_ui(kp_id, await _fetch_ia_description(archive_id))`
10. `async _fetch_ia_description(archive_id)` — GET `metadata/{id}`,
    `_clean_ia_description(meta.get("description"))`
11. `async _search_archive_identifier(title, year)` — Lucene escape,
    `title:("{safe}")` + `year:[{y-1} TO {y+1}]` + `mediatype:(movies)`,
    `rows=5`, `sort[]=downloads desc`, return first `identifier`
12. `_apply_description_to_ui(kp_id, text)`:
    - `if current_movie_id != kp_id: return` — защита от гонки
    - `details_page.update_description(text)`
13. `handle_resume_dismiss(movie_id)`:
    - `QMessageBox.question(..., "Очистить историю просмотра?", ..., Yes|No, No)`
    - `if reply != Yes: return`
    - `clear_history_entry(movie_id); resume_island.hide()`
14. `check_resume_island()` — `get_last_session()`, если `>5` →
    `show_resume_bar`, иначе `resume_island.hide()`

**Проверка:** карточка → детали; для фильма без описания в БД через 5s
появляется описание с IA; крестик островка → QMessageBox → Yes → очистка.

**Инвариант:** `_apply_description_to_ui` проверяет `current_movie_id`
перед обновлением. Иначе: пользователь открыл A, description A прилетает
поверх B.

---

### T-5.3: `controllers/orchestrator.py`

**Время:** 12 min
**Файлы:** `controllers/orchestrator.py` (create)
**Зависит от:** T-3.2, T-5.1, T-5.2

**Что делать:**

1. `class AmagiApplicationOrchestrator(loop)`:
   - `web_fetcher=WebFetcher()`, `archive_org=ArchiveOrgSearcher()`,
     `kp_service=KPService()`, `balancer_client=BalancerClient()`
   - `cleanup_startup()`, `init_db()`, `init_whitelist_db()`
   - `_jackett_ready=False`, `_cleanup_timer=None`
2. `start_orchestration()`:
   - `if not config.LEGAL_DISCLAIMER_ACCEPTED:`
     - `dialog = LegalGateDialog()`
     - `if dialog.exec() != Accepted: QApplication.quit(); return`
     - `config.LEGAL_DISCLAIMER_ACCEPTED = True`
   - `if config.LEGAL_ONLY_MODE: QTimer.singleShot(0, _on_public_boot); return`
   - (private-ветка — wizard, в этом плане не реализуем)
3. `_on_public_boot()` → `_on_success_setup(None)`
4. `_on_success_setup(manager)`:
   - `session = aiohttp.ClientSession()`
   - `main_window = MainWindow()`
   - `playback = PlaybackController(main_window.player_page, main_window)`
   - `feed = FeedController(self)`, `details = DetailsController(self)`,
     `stream = StreamController(self)`
   - **connect signals:**
     - `feed_page.next_page_requested` → `feed.load_next_page`
     - `player_page.close_player_requested` → `stream.handle_close_player`
     - `resume_movie_requested` → `details.handle_resume_playback`
     - `resume_dismiss_requested` → `details.handle_resume_dismiss`
     - `details_page.back_to_feed_requested` → `details.handle_back_to_feed`
     - `details_page.start_streaming_requested` → `stream.handle_stream_start`
     - `language_changed` → `_on_language_changed`
   - `search_debounce = QTimer(main_window)` singleShot 400ms → `feed.run_search`
   - `search_bar.textChanged` → `feed.on_search_text_changed`
   - `main_window.show()`
   - `_start_periodic_cleanup()` — QTimer 60s
   - `create_task(_async_boot())`
5. `async _async_boot()`:
   - `await feed.load_feed(clear_grid=True)`
   - `details.check_resume_island()`
6. `_on_language_changed(lang)` — `if not in ("en","ru"): return`,
   `config.SEARCH_LANGUAGE = lang`
7. `async shutdown_async()`:
   - `_cleanup_timer.stop()`
   - `feed.shutdown()`, `kp_service.log_stats()`
   - `await stream.stop_all()`
   - `await session.close()`, `await web_fetcher.close()`, `await archive_org.close()`
   - (private: manager.stop_services, libtorrent remove_torrents)
   - `cleanup_all()`

**Проверка:** полный флоу — карточка → детали → стрим → play → close →
feed; `Ctrl+C` → всё закрывается, нет зомби.

**Инвариант:** `app` в контроллерах — это **`AmagiApplicationOrchestrator`**,
не `QApplication`. У него есть `session`, `details`, `feed`, `stream`,
`main_window`, `playback`.

---

## Phase 6: Verify

**Зачем:** проверить всё вместе. Phase 0–5 проходят unit-проверки, Phase 6
проверяет E2E.

---

### T-6.1: E2E smoke test

**Время:** 5 min
**Файлы:** —

**Шаги:**
1. `python main.py`
2. Карточки + постеры видны (20 шт)
3. Клик на карточку → детали с title/year/desc
4. «Запустить трансляцию» → loader → видео играет
5. Seek на 5:00 → прыжок
6. Close → feed → островок «Продолжить» появился
7. Клик на островок → возобновление с 5:00
8. Поиск «the kid» → находит «Малыш»
9. Очистить поиск → вся лента

**Проверка:** все 9 шагов без ошибок.

---

### T-6.2: Failure modes

**Время:** 5 min
**Файлы:** —

**Шаги:**
1. Поиск `nonexistent_xyz_12345` → пусто / «НИЧЕГО НЕ НАЙДЕНО»
2. Отключить сеть → поиск «The Kid» → «ФИЛЬМ НЕ НАЙДЕН», без крэша
3. Восстановить сеть → стрим работает
4. Закрыть приложение → открыть → история сохранилась
5. Закрыть во время загрузки ленты → нет крэша

**Проверка:** ни один не крэшит, все дают понятное сообщение.

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

**Зачем:** README и LICENSE. Минимум для репозитория.

---

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
1. Скопировать полный текст GPLv3 с `https://www.gnu.org/licenses/gpl-3.0.txt`

**Проверка:** файл существует, текст полный.

---

## Phase 8: CI

**Зачем:** автоматическая сборка. После этой фазы push тега → релиз на GitHub.

---

### T-8.1: `.github/workflows/tests.yml`

**Время:** 8 min
**Файлы:** `.github/workflows/tests.yml` (create)

**Шаги:**
1. `on: [push, pull_request]`
2. `runs-on: windows-latest`
3. `matrix: python-version: ["3.11", "3.12", "3.13"]`
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
     --include-qt-plugins=multimedia
     --include-data-dir=data=data --include-data-dir=ui=ui
     --windows-icon-from-ico=assets/icon.ico
     --output-dir=dist --output-filename=amagi-player.exe main.py`
   - `Compress-Archive`, `upload-artifact`
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

## Чек-лист готовности

- [ ] Phase -1: stubs созданы, `import` работает
- [ ] Phase -1: все константы `config.py` на месте
- [ ] Phase 0: `python main.py` открывает пустое окно
- [ ] Phase 1: `assert` на INSERT/SELECT проходят
- [ ] Phase 2: IA-поиск возвращает результаты
- [ ] Phase 3: клик «Запустить» → видео играет
- [ ] Phase 4: все виджеты рендерятся, тема переключается
- [ ] Phase 5: полный флоу работает
- [ ] Phase 6: E2E, failure modes, no zombies
- [ ] Phase 7: README, LICENSE
- [ ] Phase 8: CI green, локальный build работает

**Все ✅ → план выполнен.**
