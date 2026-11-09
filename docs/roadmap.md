# Roadmap — что не реализовано в v2.x

Требования, которые **планируются**, но не в v2.x. Перенесены из основного
SRS в отдельный документ по замечанию к ТЗ: «ТЗ и README не должны обещать
функционал, который не планируется».

**Принцип:** «работает — не трогай». Все пункты — улучшения, но каждое
требует изменения критичного пути (поиск, БД, IO). Не трогали перед
сдачей, чтобы не сломать работающее.

**Соответствие SRS 🟡 требованиям:**

| Roadmap | SRS ID | Что |
|---|---|---|
| W-01 | F-W-01 | Retry 429/503 IA Search |
| W-02 | — | Retry 5xx IA Search (подмножество W-01) |
| W-03 | F-W-02 | Лимит ответа IA Search 5 MB |
| W-04 | F-W-11 | Лимит ответа IA Metadata 10 MB |
| W-05 | F-W-03 | Retry БД при locked |
| W-06 | F-W-04 | Диалог при corrupt БД |
| W-07 | F-W-05 | Лимит постера в runtime 5 MB |
| W-08 | F-W-06 | Лимит `.torrent` 10 MB |
| W-09 | F-W-09 | Теги и категории в БД |
| W-10 | F-W-10 | Горячие клавиши |
| W-11 | F-W-12 | Тесты на fallback |
| W-12 | API-11 | 5xx IA Metadata — не кэшировать |
| W-13 | API-19 | KP throttle 1.5s в `kp_service` |
| W-14 | API-20 | KP 402 cooldown |
| W-15 | API-21 | KP 429 cooldown |
| W-16 | LIM-03 | Размер ответа Jackett 2 MB |
| W-17 | LIM-04 | Размер ответа TorAPI 2 MB |
| W-18 | LIM-23 | Обрезка названия карточки 200 |
| W-19 | LIM-24 | `search_bar.setMaxLength(100)` |
| W-20 | F-W-07 | Retry 5xx IA Download |
| W-21 | F-W-08 | Локализация UI на английский |

---

## Категория A. Internet Archive — стабильность

### W-01. Retry 429/503 для IA Search

**Требование:** при HTTP 429 (Too Many Requests) или 503 (Service Unavailable) от `advancedsearch.php` — retry 3 раза с backoff 2/4/8 сек.

**Сейчас:** `searcher.py._search_identifiers` возвращает `[]` без retry.

**Почему не реализовано:** `searcher.py` — критичный путь поиска. Правка перед сдачей рискованна.

**Оценка:** 20 минут. `try/except` вокруг существующего кода + `asyncio.sleep`.

### W-02. Retry 5xx для IA Search

**Требование:** при HTTP 5xx от `advancedsearch.php` — 1 retry через 5 сек.

**Сейчас:** `return []`.

**Связь:** подмножество W-01. Если делаешь W-01, W-02 закрывается автоматически.

**Оценка:** 10 минут (отдельно) или 0 (в составе W-01).

### W-03. Лимит размера ответа IA Search (5 MB)

**Требование:** если `resp.content_length > 5 MB` — обрезать, лог WARNING.

**Сейчас:** нет проверки. IA редко возвращает > 1 MB, но защита нужна.

**Оценка:** 5 минут.

### W-04. Лимит размера ответа IA Metadata (10 MB)

**Требование:** если > 10 MB — обрезать, лог WARNING.

**Сейчас:** нет проверки.

**Оценка:** 5 минут.

### W-20. Retry 5xx для IA Download

**Требование:** при HTTP 5xx от `archive.org/download/...` — 1 retry через 5 сек, потом следующий direct_url.

**Сейчас:** fallback через `direct_url` работает (F-13), но **явного retry 5xx нет** — это fallback через `demux_error`, не retry HTTP.

**Оценка:** 10 минут в `cascade.py`.

---

## Категория B. База данных

### W-05. Retry при `database is locked`

**Требование:** при `sqlite3.OperationalError: database is locked` — retry 1 раз через 100ms, потом ошибка.

**Сейчас:** WAL обычно помогает, но при параллельных записях (main + tools) может возникнуть.

**Оценка:** 15 минут. `try/except` в `use_connection`.

### W-06. Диалог при повреждении БД

**Требование:** если `sqlite3.DatabaseError: database disk image is malformed` — `QMessageBox.question` «БД повреждена, пересоздать?». При Yes — пересоздать из seed.

**Сейчас:** приложение упадёт с traceback.

**Оценка:** 30 минут. Catch в `init_db`, диалог в `orchestrator`.

---

## Категория C. Файлы и кэш

### W-07. Лимит размера постера в runtime (5 MB)

**Требование:** при скачивании постера (`feed_controller._try_kp_poster`, `details_controller._try_kp_cover`) — если `len(content) > 5 MB`, отклонить.

**Сейчас:** в `enrich_whitelist.py` есть `MAX_POSTER_BYTES = 5_000_000`, но в runtime-скачивании нет проверки.

**Оценка:** 10 минут. 2 файла, по 1 условию.

### W-08. Лимит `.torrent` файла (10 MB)

**Требование:** при скачивании `.torrent` (`source_loader._download_torrent`) — если > 10 MB, отклонить.

**Сейчас:** `resp.read()` без проверки размера.

**Оценка:** 5 минут.

---

## Категория D. Внешние API — лимиты ответов

### W-16. Размер ответа Jackett/Prowlarr (2 MB)

**Требование:** при `resp.content_length > 2 MB` — обрезать, лог WARNING.

**Сейчас:** `jackett_client._get` — `xml = await resp.text()` без проверки.

**Оценка:** 5 минут. `if resp.content_length and resp.content_length > 2MB: return []`.

### W-17. Размер ответа TorAPI (2 MB)

**Требование:** при `resp.content_length > 2 MB` — обрезать.

**Сейчас:** `safe_torapi` — `data = await resp.json()` без проверки.

**Оценка:** 5 минут.

---

## Категория E. Kinopoisk — throttle и cooldown в `kp_service`

### W-13. KP throttle 1.5s в `kp_service`

**Требование:** все запросы к KP (`get_movie_data`, `search_movies_by_keyword`, `get_popular_movies`) — не чаще 1 / 1.5 сек.

**Сейчас:** throttle есть только в `feed_controller._try_kp_poster`. В `kp_service._get_json` — нет.

**Оценка:** 10 минут. `_last_request` timestamp + `asyncio.sleep`.

### W-14. KP 402 cooldown 5 минут

**Требование:** при HTTP 402 от KP — cooldown 5 минут (дневной лимит), все запросы возвращают `None` без обращения.

**Сейчас:** `kp_service._get_json` — только `log.warning` + `return None`. Cooldown нет — следующий запрос снова идёт к KP.

**Оценка:** 10 минут. `_cooldown_until` + проверка в начале `_get_json`.

### W-15. KP 429 cooldown 60 секунд

**Требование:** при HTTP 429 от KP — cooldown 60 секунд, retry после.

**Сейчас:** cooldown есть в `feed_controller._kp_search` (`_KP_COOLDOWN_429_SEC = 60.0`), в `kp_service._get_json` — нет.

**Оценка:** 10 минут. То же, что W-14.

---

## Категория F. UI

### W-18. Обрезка названия карточки (200 символов)

**Требование:** `card_widget.title_label` — название обрезается до 200 символов.

**Сейчас:** `QLabel(self.title.upper(), ...)` с `setWordWrap(True)` — переносит, не обрезает. Очень длинное название ломает вёрстку.

**Оценка:** 2 минуты. `self.title.upper()[:200]`.

### W-19. `search_bar.setMaxLength(100)`

**Требование:** поле поиска не принимает больше 100 символов.

**Сейчас:** `QLineEdit` без `setMaxLength`. Пользователь может ввести 1000.

**Оценка:** 1 минута.

### W-21. Локализация UI на английский

**Требование:** интерфейс на английском (сейчас только русский).

**Сейчас:** все строки — на русском. EN/RU переключает **поиск**, не UI.

**Оценка:** 3–5 дней. `QTranslator` + словари строк + замена всех `QLabel("...")` на `self.tr(...)`.

**Когда:** после v2.x, при желании выйти на международную аудиторию.

### W-10. Горячие клавиши в плеере

**Требование:** Space (play/pause), ←/→ (seek ±10s), F (fullscreen), M (mute), ↑/↓ (volume).

**Сейчас:** только Esc для выхода из fullscreen.

**Оценка:** 1 час. `_handle_key_press` в `playback_controller.py`.

---

## Категория G. Данные и тесты

### W-09. Теги и категории в БД

**Требование:** таблицы `tags` и `movie_tags` (many-to-many), фильтрация ленты по категориям.

**Сейчас:** плоский каталог без категорий.

**Оценка:** 2–3 дня (схема + репозиторий + UI-фильтр + наполнение).

### W-11. Тесты на fallback-логику

**Требование:** `tests/test_fallback.py` с моками libtorrent — public retry epoch, private auto-fallback, skip на последнем.

**Сейчас:** `tests/test_smoke.py` — 8 базовых тестов, fallback не покрыт.

**Оценка:** 2–3 часа.

### W-12. API-11 — 5xx IA Metadata не кэшировать

**Требование:** при HTTP 5xx от `archive.org/metadata/{id}` — return `None`, **не** кэшировать (повторить позже).

**Сейчас:** `metadata.py` кэширует `None` для **любого** статуса != 200 (включая 5xx). То есть 5xx кэшируется как 404.

**Оценка:** 5 минут. `if resp.status == 404: cache; elif resp.status >= 500: return None без cache`.

---

## Что НЕ в этом roadmap

Следующее **не планируется** в обозримом будущем — это Out of Scope,
не «отложено»:

- macOS, мобильные платформы
- Субтитры, аудиодорожки
- Chromecast, AirPlay, DLNA
- Аккаунты, облачная синхронизация
- ML-рекомендации
- Code signing
- Английский UI **как основной** (W-21 — как опция, не замена)

Эти пункты в SRS раздел 10 «Out of Scope». Их **не будет** в roadmap.
