# Amagi-Player — Software Requirements Specification

**Версия:** 2.0
**Дата:** 2025-11-09
**Автор:** AkashaForge
**Версия приложения:** 2.x

---

## 1. Введение

### 1.1. Назначение

Десктопное приложение для поиска и стриминга фильмов общественного
достояния из Internet Archive. Два режима: **PUBLIC** (только IA,
легальный контент) и **PRIVATE** (P2P через libtorrent, для разработчиков).

### 1.2. Область применения

Локальное приложение для конечных пользователей. Не клиент-серверное,
без аккаунтов, без телеметрии. Сетевые запросы — только к тем источникам,
которые пользователь явно использует для поиска и воспроизведения.

### 1.3. Проблема

Internet Archive неаккуратен: метаданные врут, один фильм залит несколько
раз, файлы бывают DVD-образами (mpeg), которые ломаются при seek. Скачать
целиком — долго и не всегда нужно. Существующие плееры либо для
коммерческого контента, либо не работают с открытыми архивами.

### 1.4. Определения

| Термин | Определение |
|---|---|
| **PD** | Public domain — общественное достояние |
| **IA** | Internet Archive |
| **P2P** | Peer-to-peer, BitTorrent |
| **HTTP Range** | Частичный HTTP-запрос (`Range: bytes=X-Y`) |
| **Piece** | Фрагмент торрента (256 KB – 4 MB) |
| **Magnet** | Ссылка на торрент по info_hash |
| **Swarm** | Группа пиров, обменивающихся торрентом |
| **Composite health score** | Взвешенная оценка источника |
| **PYNORM** | SQLite-функция для Unicode-lowercase + ё→е |
| **Must-have** | Требование, реализованное в v2.x |
| **Wishlist** | Требование, запланированное после v2.x (см. roadmap.md) |

---

## 2. Пользователи и сценарии использования

### 2.1. Роли

| Роль | Описание | Режим |
|---|---|---|
| **Конечный пользователь** | Смотрит фильмы PD из Internet Archive. Не знает про P2P. | PUBLIC |
| **Разработчик** | Включает P2P, настраивает Jackett/Prowlarr, работает с приватными источниками. | PRIVATE |

### 2.2. Сценарии использования (Use Cases)

#### UC-01: Просмотр ленты PD-фильмов

**Роль:** конечный пользователь
**Предусловие:** приложение запущено, режим PUBLIC
**Основной поток:**
1. Пользователь видит главный экран с лентой из 20 карточек.
2. Каждая карточка содержит постер, название, год.
3. Скролл вниз → подгрузка следующей страницы (20 карточек).
4. После последней страницы — новых нет, лента «закрыта».

**Альтернативный поток:** если постер не найден ни в кэше, ни в seed, ни на IA — placeholder «ОБЛОЖКА НЕДОСТУПНА».

#### UC-02: Поиск фильма по названию

**Роль:** конечный пользователь
**Предусловие:** открыт главный экран
**Основной поток:**
1. Пользователь вводит запрос в search bar (≥ 3 символов).
2. Через 400 мс (debounce) запускается поиск по локальной БД.
3. Лента перестраивается: только найденные фильмы.
4. Очистка search bar → вся лента.

**Альтернативный поток:** если ничего не найдено — пустая лента, сообщение «НИЧЕГО НЕ НАЙДЕНО».

#### UC-03: Воспроизведение фильма из IA

**Роль:** конечный пользователь
**Предусловие:** открыт экран деталей фильма
**Основной поток:**
1. Пользователь нажимает «ЗАПУСТИТЬ ТРАНСЛЯЦИЮ».
2. Приложение ищет фильм на IA (каскад из 4 запросов).
3. Выбирает лучший файл по приоритету формата.
4. Переключается на экран плеера, загружает поток.
5. Видео воспроизводится. Seek работает.

**Альтернативный поток:** если фильм не найден — сообщение «ФИЛЬМ НЕ НАЙДЕН В INTERNET ARCHIVE», возврат на экран деталей через 3 секунды.

#### UC-04: Продолжить просмотр с места остановки

**Роль:** конечный пользователь
**Предусловие:** пользователь ранее смотрел фильм и закрыл его на позиции > 5 секунд
**Основной поток:**
1. На главном экране внизу появляется островок «Продолжить просмотр» с названием фильма.
2. Клик на «Продолжить» → экран деталей → «Запустить» → воспроизведение с сохранённой позиции.
3. Клик на крестик островка → `QMessageBox.question` → Yes → история удалена.

#### UC-05: Переключение темы

**Роль:** конечный пользователь
**Предусловие:** открыт главный экран
**Основной поток:**
1. Пользователь нажимает «✦ СВЕТЛАЯ ТЕМА» (или «✦ ТЁМНАЯ ТЕМА»).
2. Все элементы обновляются: фон, текст, кнопки, карточки.
3. Кнопка меняет текст на противоположный.

#### UC-06: Переключение языка поиска

**Роль:** конечный пользователь
**Предусловие:** открыт главный экран
**Основной поток:**
1. Пользователь нажимает кнопку EN (или RU).
2. Кнопка меняет текст на RU (или EN).
3. `config.SEARCH_LANGUAGE` обновляется.
4. **Интерфейс остаётся на русском** — переключается только язык поиска (какие фильмы искать — английские или русские).

#### UC-07: (PRIVATE) Стрим через P2P

**Роль:** разработчик
**Предусловие:** режим PRIVATE, Jackett/Prowlarr настроены
**Основной поток:**
1. Пользователь ищет фильм в ленте.
2. «Запустить трансляцию» → параллельный поиск по 6 источникам (Jackett, web_fetcher, IA, balancers, TorAPI, YTS).
3. Выбор победителя по composite health score.
4. HTTP Range сервер запущен, QMediaPlayer воспроизводит.
5. Seek работает через piece scheduler с deadline'ами.

**Альтернативный поток:** если все P2P-источники мертвы — fallback на IA (public direct), потом на private direct.

---

## 3. Требования к данным

### 3.1. База `whitelist.db` — каталог

#### Таблица `movie_whitelist`

| Колонка | Тип | Ключ | Default | Описание |
|---|---|---|---|---|
| `kp_id` | INTEGER | **PRIMARY KEY** | — | ID фильма (Кинопоиск или отрицательный pseudo-id) |
| `title_ru` | TEXT | NOT NULL | — | Название на русском |
| `title_en` | TEXT | | `''` | Название на английском (для поиска на IA) |
| `year` | TEXT | | `''` | Год выпуска |
| `archive_identifier` | TEXT | | `''` | ID на Internet Archive (для описания/постера/стрима) |
| `added_at` | TIMESTAMP | | `CURRENT_TIMESTAMP` | Когда добавлен в каталог |
| `available` | INTEGER | | `NULL` | `NULL` = не проверен, `1` = доступен, `0` = нет |
| `description` | TEXT | | `''` | EN-описание (из IA) — добавляется `enrich_whitelist.py` |
| `description_ru` | TEXT | | `''` | RU-описание (из KP) — добавляется `enrich_whitelist.py` |
| `poster_source` | TEXT | | `''` | `KP` / `IA-files` / `IA-thumb` / `none` / `existing` / `''` |
| `enriched` | INTEGER | | `0` | `1` = обработан `enrich_whitelist.py` |

**Индексы:**
- `idx_whitelist_available` на `available`
- `idx_whitelist_title_ru` на `title_ru`
- `idx_whitelist_title_en` на `title_en`

#### Особенности

- **`kp_id` — primary key.** Может быть отрицательным для «pseudo-id» фильмов без Кинопоиска (`-hash(title_en|year) mod 100_000_000`).
- **`available`** — три состояния. В PUBLIC-режиме лента показывает `(available = 1 OR available IS NULL)`.
- **`description` vs `description_ru`** — приоритет у `description_ru` (KP), fallback на `description` (IA).
- **`poster_source`** — откуда взят постер. Используется только для диагностики, не для UI.

### 3.2. База `app_data.db` — история

#### Таблица `user_history`

| Колонка | Тип | Ключ | Default | Описание |
|---|---|---|---|---|
| `kp_id` | INTEGER | **PRIMARY KEY** | — | ID фильма |
| `movie_title` | TEXT | NOT NULL | — | Название для островка «Продолжить» |
| `current_seconds` | INTEGER | NOT NULL | — | Позиция в секундах |
| `updated_at` | TIMESTAMP | | `CURRENT_TIMESTAMP` | Последнее обновление |

**Индекс:** `idx_history_updated` на `updated_at DESC`.

**UPSERT с MAX:** при повторном сохранении `current_seconds = MAX(excluded.current_seconds, user_history.current_seconds)` — не сбрасывать больший прогресс меньшим.

#### Таблица `schema_version`

| Колонка | Тип | Ключ | Default |
|---|---|---|---|
| `version` | INTEGER | **PRIMARY KEY** | — |

### 3.3. Связи между таблицами

- **`user_history.kp_id` → `movie_whitelist.kp_id`** — логическая связь, **без физического FK**. Разные базы (`app_data.db` и `whitelist.db`), могут пересоздаваться независимо. Это осознанное решение: потеря истории при пересборке каталога — приемлемо.

### 3.4. Кэши (файловая система)

| Путь | Что | TTL | Лимит |
|---|---|---|---|
| `data/cache/{kp_id}.jpg` | Постеры | — | Без лимита (файлы) |
| `data/cache/short/{kp_id}.json` | Короткие данные KP | 30 дней | Без лимита |
| `data/cache/full/{kp_id}.json` | Полные данные KP | 30 дней | Без лимита |
| `data/cache/lists/{hash}.json` | Списки popular/search | 24ч / 6ч | Без лимита |
| `data/seed_posters/{kp_id}.jpg` | Постеры из релиза | — | В релизе |
| `data/trackers_cache.txt` | Трекеры из балансера | 12ч | — |

**LRU метаданных IA (в памяти):** 500 записей, TTL 24 часа.

---

## 4. Экраны и элементы

### 4.1. Главный экран (лента)

**Файл:** `ui/main_window.py` + `ui/widgets/feed_widget.py`

**Элементы:**

| Элемент | Object name | Описание |
|---|---|---|
| Header bar (75px) | `headerBar` | Верхняя панель |
| Logo | `logoLabel` | «AMAGI», letter-spacing 5px |
| Search bar | `searchBar` | QLineEdit, 400px, placeholder «ПОИСК ПО КУЛЬТУРНОМУ ФОНДУ...» |
| Language button | `languageButton` | 48×32, текст «EN» / «RU» |
| Section title | `sectionTitle` | «ВЕРИФИЦИРОВАННЫЙ КУЛЬТУРНЫЙ ФОНД» |
| Scroll area | — | QScrollArea с grid карточек |
| Grid container | `gridContainer` | 4 колонки, spacing 30 |
| Theme button | `sysButton` | «✦ СВЕТЛАЯ ТЕМА» / «✦ ТЁМНАЯ ТЕМА» |
| Settings button | `sysButton` | «Настройки» |

**Островок «Продолжить»** (overlay):

| Элемент | Object name | Описание |
|---|---|---|
| Frame | `continueIsland` | 420×96, внизу по центру, скрыт по умолчанию |
| Title label | — | `<b>НАЗВАНИЕ</b>`, wordWrap |
| Action button | `islandActionButton` | «Продолжить просмотр» |
| Close button | `closeIslandButton` | «×», 20×20, правый верхний угол |

### 4.2. Экран деталей

**Файл:** `ui/widgets/details_widget.py`

| Элемент | Object name | Описание |
|---|---|---|
| Back button | `sysButton` | «← НАЗАД К ФОНДУ» |
| Big cover | `coverPlaceholder` | QLabel 300×450, AlignTop, scaledContents |
| Title | `detailsTitle` | 28pt, wordWrap |
| Year | `detailsYear` | «---- ГОД» |
| Description | `detailsDescription` | wordWrap, maxHeight 220px |
| Play button | `actionButton` | «ЗАПУСТИТЬ ТРАНСЛЯЦИЮ», 280×46 |

### 4.3. Экран плеера

**Файл:** `ui/widgets/player_widget.py`

| Элемент | Описание |
|---|---|
| Exit button | «✕ ЗАКРЫТЬ ТРАНСЛЯЦИЮ» |
| Video widget | QVideoWidget, чёрный фон |
| Loader container | Лоадер с прогресс-баром, скрыт при воспроизведении |
| Loader label | «ПОСЛЕДОВАТЕЛЬНАЯ БУФЕРИЗАЦИЯ P2P ПОТОКА...» |
| P2P progress | QProgressBar, height 2px |
| Timeline slider | 0..1000, маппинг в ms |
| Play/pause button | «⏸» / «▶» |
| Time label | «00:00 / --:--» |
| Skip button | «⏭», tooltip «Скипнуть раздачу» |
| Fullscreen button | «⛶» |

### 4.4. Экран настроек

**Файл:** `ui/main_window.py` (`settings_page_placeholder`)

| Элемент | Описание |
|---|---|
| Back button | «← НАЗАД В ЛЕНТУ» |
| Placeholder label | «ЭКРАН НАСТРОЕК (В РАЗРАБОТКЕ)» |
| Clear history button | «Очистить историю» → `QMessageBox.question` → очистка |
| About button | «О программе» → `QMessageBox.about` |

### 4.5. Диалоги

| Диалог | Файл | Назначение |
|---|---|---|
| **LegalGateDialog** | `legal_gate.py` | Дисклеймер при первом запуске. Кнопка «Принять» → `QDialog.Accepted` |
| **SourcePickerDialog** | `ui/source_picker_dialog.py` | Выбор альтернативы в PRIVATE. ListWidget + «Смотреть» + «Отмена» |
| **P2PInitialSetupWizard** | `ui/setup_wizard.py` | Мастер настройки Jackett в PRIVATE. QWebEngineView + «Активировал трекеры» |

**QMessageBox (3 варианта):**
1. **Подтверждение очистки островка** — `question`, Yes/No
2. **Очистка истории в настройках** — `question` + `information` (результат)
3. **О программе** — `about` (версия, лицензия, ссылка)

### 4.6. Требования к UI

| ID | Требование |
|---|---|
| UI-01 | Две темы: тёмная OLED (#000000) и светлая Gallery Editorial (#F2EDE3) |
| UI-02 | Переключение темы — без перезапуска, все элементы обновляются |
| UI-03 | EN/RU переключает язык поиска, не язык интерфейса |
| UI-04 | Шрифт system-ui, размеры по макету |
| UI-05 | Адаптивность: 4 → 3 → 2 колонки при сужении окна |
| UI-06 | Диалоги модальные, кроме островка (overlay) |

---

## 5. Функциональные требования

### 5.1. Обязательные (реализованы в v2.x)

| ID | Требование | Критерий приёмки |
|---|---|---|
| **F-01** | Лента из локального каталога, 20 карточек на страницу | Открыть → 20 карточек с постерами |
| **F-02** | Поиск по названию (RU/EN) и году, регистронезависимый для кириллицы | «МАТРИЦА» находит «Матрица» |
| **F-03** | Пагинация: скролл вниз → следующая страница | После последней — «больше нет» |
| **F-04** | Постерный каскад: кэш → seed → IA thumbnail → KP | Постер ≤ 3 сек |
| **F-05** | Placeholder «ОБЛОЖКА НЕДОСТУПНА» при отсутствии постера | Placeholder виден |
| **F-06** | Каскад из 4 IA-запросов | Лог `IA query:` для каждого шага |
| **F-07** | Допуск по году ±2 | `year:[1919 TO 1923]` |
| **F-08** | Скоринг: language × 100 + title × 50 + popularity × 20 | Сортировка по score |
| **F-09** | Для фильмов до 1930 язык — не дисквалификатор (0.9) | «Nosferatu» проходит |
| **F-10** | Приоритет расширения: MP4 > WebM > MKV > M4V > OGV > MOV > AVI > WMV > MPG > MPEG | При равенстве — больший размер |
| **F-11** | Файлы вне [30 MB, 4 GB] игнорируются, трейлеры < 50 MB игнорируются | `no playable video` |
| **F-12** | Если только «неудобные» форматы — берём лучший, логируем | `only unfriendly format` |
| **F-13** | При demux error — 1 retry через 5 сек, потом следующий direct_url | `public DEMUX → retry in 5s` |
| **F-14** | Если retry не помог и direct_url нет — «Все варианты испробованы» | Нет крэша |
| **F-15** | До 12 кандидатов в P2P, группировка по info_hash | `Taking N candidates` |
| **F-16** | Победитель по composite score, grace 10 сек, margin ×2 | `First ready` |
| **F-17** | Мёртвые handles убиваются: no peers 10s / no meta 60s / no first 45s | `Kill {key}: reason` |
| **F-18** | HTTP Range сервер на 127.0.0.1, Host-header → 403 | `Host: evil.com` → 403 |
| **F-19** | `set_piece_deadline(ms ≥ 100)`, lookahead 10, tail 20 | Seek ≤ 5 сек |
| **F-20** | `force_deadline` при каждом HTTP Range запросе | `force_deadline: piece=N` |
| **F-21** | `cancel()` освобождает handles за 15 сек + sync fallback | `Session state before add: 0` |
| **F-22** | Sync fallback `remove_torrent` если polling не помог | `sync remove для N handles` |
| **F-23** | `rmtree` в executor | Seek работает во время cleanup |
| **F-24** | 4 уровня fallback: online → public direct → P2P → private direct | Переход на следующий |
| **F-25** | PUBLIC: `_public_epoch` защищает от race | `stream reset (epoch X != Y)` |
| **F-26** | PUBLIC: skip на последнем → начинаем с первого | `начинаем с первого` |
| **F-27** | PRIVATE: demux → reload #1 через 5s → auto-fallback до 3 попыток | `auto-fallback [N/3]` |
| **F-28** | Watchdog: buffering > 25s и rate < 0.3 MB/s → stop + fallback | `WATCHDOG` |
| **F-29** | `player.stop()` через `QTimer.singleShot(0, ...)` | UI не замирает |
| **F-30** | Две темы | Переключение |
| **F-31** | EN/RU переключает язык поиска | `[LANG] Переключено на` |
| **F-32** | QMessageBox × 3 (resume, clear history, about) | Диалоги открываются |
| **F-33** | Островок при `current_seconds > 5` | Островок виден |
| **F-34** | Экран деталей: постер 300×450, описание ≤ 220px | Длинное не вылезает |
| **F-35** | Плеер: play/pause, seek, время, skip, fullscreen | Кнопки работают |
| **F-36** | `switch_mode.py public` → файлы в `.bak`, `whitelist.db` из seed | Нет `sources.txt` |
| **F-37** | `switch_mode.py private` → восстановление из `.bak` | Файлы на месте |
| **F-38** | Режим читается из `data/mode.txt` при импорте | Перезапуск применяет |
| **F-39** | Без Chrome — браузерная фаза пропускается | `[CONFIG] Браузер не найден` |
| **F-40** | Без KP_API_KEY — работает с БД и IA | `[CONFIG] KP_API_KEY не задан` |
| **F-41** | Ошибка торрента → «Ни один из N не начал качать» | Нет крэша |
| **F-42** | Без сети → «ФИЛЬМ НЕ НАЙДЕН» | Сообщение, не traceback |

### 5.2. Желательные (в roadmap, v2.x не реализованы)

| ID | Требование | Причина отсрочки |
|---|---|---|
| **F-W-01** | Retry при 429/503 для IA (сейчас `searcher.py` возвращает `[]`) | Не трогали `searcher.py` перед сдачей |
| **F-W-02** | Ограничение размера ответа IA (5 MB, защита от OOM) | Не критично для IA (метаданные редко > 1 MB) |
| **F-W-03** | Retry БД при `database is locked` | WAL обычно решает, явный retry — улучшение |
| **F-W-04** | Диалог при БД corrupt | Редкий случай, не критично |
| **F-W-05** | Ограничение размера постера в runtime | В `enrich_whitelist.py` есть, в runtime-скачивании нет |
| **F-W-06** | Ограничение размера `.torrent` файла (10 MB) | Обычно < 1 MB, улучшение |
| **F-W-07** | Retry 5xx для IA Download (сейчас fallback сразу) | Сейчас fallback через direct_url — работает |
| **F-W-08** | Локализация UI на английский | EN/RU — это поиск, не UI |
| **F-W-09** | Теги и категории в БД | Требует миграции схемы, отложено |
| **F-W-10** | Горячие клавиши в плеере | UX-улучшение |

**Полное описание каждого — в `docs/roadmap.md`.**

---

## 6. Нефункциональные требования

### 6.1. Производительность

| ID | Требование | Критерий |
|---|---|---|
| **N-01** | Время до первого кадра P2P ≤ 30 сек | Timeout → FAILED |
| **N-02** | `wait_for_piece` polling 50ms, refresh deadline 5s | Лог раз в 3 сек |
| **N-03** | `read_piece` timeout 8 сек | `alert timeout` |
| **N-04** | Время запуска ≤ 3 сек на SSD | Замер |
| **N-05** | Время загрузки первой страницы ≤ 2 сек | Замер |
| **N-06** | Время отклика UI ≤ 100 мс | Клик → переход |

### 6.2. Надёжность

| ID | Требование | Критерий |
|---|---|---|
| **N-07** | 2-фазное закрытие: `stop_and_save()` → 200ms → `cancel()` | Лог последовательности |
| **N-08** | Watchdog на `_closing_in_progress` — 30 сек | `WATCHDOG` в логе |
| **N-09** | `_stop_resources()` идемпотентен | Двойной вызов не ломает |
| **N-10** | `wait_for(_stop_resources(), timeout=25.0)` | Timeout → лог |
| **N-11** | Нет зомби после падения | `cleanup_startup()` |

### 6.3. Безопасность

| ID | Требование | Критерий |
|---|---|---|
| **N-12** | SSRF: блок localhost, 127.0.0.1, RFC1918 | `127.0.0.1` отвергается |
| **N-13** | Path traversal: `realpath` проверяет `downloads_dir` | `../../etc/passwd` → FAILED |
| **N-14** | XXE: `defusedxml` для Torznab XML | `grep xml.etree` — пусто |
| **N-15** | SSL verify везде | Все `*_VERIFY_SSL = True` |
| **N-16** | Секреты в `.gitignore` | `git status` — не видны |

### 6.4. Совместимость

| ID | Требование | Критерий |
|---|---|---|
| **N-17** | Windows 10/11 — основная платформа | Сборка работает |
| **N-18** | Linux (Ubuntu 22.04) — экспериментальная | Tarball запускается |
| **N-19** | Python 3.10+ | `pyproject.toml` |
| **N-20** | Без Chrome — деградация, не падение | `browser=0` |

---

## 7. Требования к внешним API

### 7.1. Обязательные

#### 7.1.1. Internet Archive — Advanced Search

| ID | Параметр | Требование |
|---|---|---|
| **API-01** | Endpoint | `https://archive.org/advancedsearch.php` |
| **API-02** | Метод | GET |
| **API-03** | Параметры | `q` (Lucene), `fl[]=identifier,title,year,downloads,language,creator`, `sort[]=downloads desc`, `rows ≤ 30`, `page=1`, `output=json` |
| **API-04** | Формат ответа | JSON, `response.docs[]` |
| **API-05** | Таймаут | 15 сек (`config.NETWORK_TIMEOUT`) |

#### 7.1.2. Internet Archive — Metadata

| ID | Параметр | Требование |
|---|---|---|
| **API-06** | Endpoint | `https://archive.org/metadata/{identifier}` |
| **API-07** | Формат ответа | JSON, `files[]` (name, size, format), `metadata` (description, title, year) |
| **API-08** | Таймаут | 12 сек |
| **API-09** | Кэш | LRU 500 записей, TTL 24 часа |
| **API-10** | Обработка 404 | Return `None`, **кэшировать** `None` |
| **API-11** | Обработка 5xx | Return `None`, **не** кэшировать |

#### 7.1.3. Internet Archive — Download

| ID | Параметр | Требование |
|---|---|---|
| **API-12** | Endpoint | `https://archive.org/download/{identifier}/{filename}` |
| **API-13** | Протокол | HTTP Range |
| **API-14** | Таймаут | `config.NETWORK_TIMEOUT` |
| **API-15** | Обработка 5xx | 1 retry через 5 сек → следующий direct_url |
| **API-16** | Обработка 416 | Лог, следующий источник |

#### 7.1.4. Kinopoisk API (опционально)

| ID | Параметр | Требование |
|---|---|---|
| **API-17** | Endpoint | `https://kinopoiskapiunofficial.tech/api/v2.*` |
| **API-18** | Аутентификация | `X-API-KEY` header, ключ из `.env` |
| **API-19** | Rate limit | ≤ 1 запрос / 1.5 сек (клиентский throttle) |
| **API-20** | Обработка 402 | Cooldown 5 минут, лог WARNING |
| **API-21** | Обработка 429 | Cooldown 60 секунд, retry |
| **API-22** | Без ключа | Функциональность не нарушена |

#### 7.1.5. Jackett / Prowlarr (PRIVATE)

| ID | Параметр | Требование |
|---|---|---|
| **API-23** | Endpoint | `http://127.0.0.1:{port}/api/v2.0/...` (Jackett) / `/api/v1/...` (Prowlarr) |
| **API-24** | Аутентификация | `apikey` query (Jackett) / `X-Api-Key` header (Prowlarr) |
| **API-25** | Таймаут | 8 сек |
| **API-26** | Retry | 2 попытки, задержки 0.3/0.7 сек |
| **API-27** | Формат | Torznab XML (Jackett) / JSON (Prowlarr), `defusedxml` для XML |

#### 7.1.6. TorAPI (PRIVATE)

| ID | Параметр | Требование |
|---|---|---|
| **API-28** | Endpoint | Из `TORAPI_BASE_URL` (`.env` или `data/torapi_base.txt`) |
| **API-29** | Таймаут | 15 сек |
| **API-30** | Обработка 402 | Лог WARNING, return `[]` (без retry) |
| **API-31** | Без URL | `safe_torapi` возвращает `[]` |

### 7.2. Желательные (в roadmap)

| ID | Требование |
|---|---|
| **API-W-01** | Ограничение размера ответа IA (5 MB) |
| **API-W-02** | Retry 429/503 для IA |
| **API-W-03** | Retry 5xx для IA Search (сейчас без retry) |

### 7.3. Общие принципы

| ID | Принцип |
|---|---|
| **API-32** | Все запросы через `aiohttp.ClientSession`, не sync |
| **API-33** | Все таймауты — из `config.py` |
| **API-34** | SSL verify всегда `True` |
| **API-35** | Никогда не падать на сетевой ошибке — return `[]` / `None` + лог |
| **API-36** | Retry только для transient errors (timeout, 429, 503) |
| **API-37** | User-Agent `AmagiPlayer/2.0` из config |

---

## 8. Обработка ошибок

### 8.1. Обязательные

#### 8.1.1. Матрица

| ID | Категория | Ошибка | Поведение | Лог | Пользователь видит |
|---|---|---|---|---|---|
| **ERR-01** | Сеть | Timeout | Return `[]`, не падать | WARNING | Ничего |
| **ERR-02** | Сеть | DNS failure | Return `[]` | WARNING | Ничего |
| **ERR-03** | Сеть | Connection refused | Return `[]` | WARNING | Ничего |
| **ERR-04** | HTTP | 402 Payment Required | Не retry, отключить источник | WARNING | Ничего |
| **ERR-05** | HTTP | 416 Range Not Satisfiable | Лог, следующий источник | WARNING | «Переключение» |
| **ERR-06** | Парсинг | Битый JSON | Return `[]`, лог | WARNING | Ничего |
| **ERR-07** | Парсинг | Неожиданные поля | Игнорировать, лог | DEBUG | Ничего |
| **ERR-08** | Парсинг | XXE | `defusedxml` блокирует | ERROR | Ничего |
| **ERR-09** | ФС | Диск полон | Остановить загрузку | ERROR | «Недостаточно места» |
| **ERR-10** | ФС | Нет прав | Остановить | ERROR | «Нет доступа» |
| **ERR-11** | ФС | Path traversal | Отказ | ERROR | «Ошибка безопасности» |
| **ERR-12** | libtorrent | `metadata_failed` | Убить handle | WARNING | Ничего |
| **ERR-13** | libtorrent | `storage_error` | Fail stream | ERROR | «Ошибка хранилища» |
| **ERR-14** | libtorrent | `torrent_error` | Лог, продолжить | ERROR | Ничего |
| **ERR-15** | QMediaPlayer | demux error | 1 retry через 5s, потом fallback | WARNING | «Переключение» |
| **ERR-16** | QMediaPlayer | Неподдерживаемый кодек | Fallback | WARNING | «Переключение» |
| **ERR-17** | UI | Виджет удалён (`sip.isdeleted`) | Skip update | DEBUG | Ничего |
| **ERR-18** | UI | `RuntimeError` reentrancy | `QTimer.singleShot(0, ...)` | ERROR | Ничего |
| **ERR-19** | Пользователь | Пустой запрос | Показать всю ленту | — | Лента |
| **ERR-20** | Пользователь | Неверный год | Игнорировать | DEBUG | Лента без фильтра |
| **ERR-21** | Пользователь | Запрос > 100 симв | Обрезать | DEBUG | Обрезанный |

#### 8.1.2. Retry-политика

| ID | Сервис | Max retries | Задержки | Условие |
|---|---|---|---|---|
| **ERR-22** | IA Download (5xx) | 1 | 5 сек | потом следующий |
| **ERR-23** | KP (429) | 1 | 60 сек cooldown | дневной лимит |
| **ERR-24** | KP (402) | 0 | 5 мин cooldown | дневной лимит |
| **ERR-25** | Jackett/Prowlarr | 2 | 0.3/0.7 сек | — |
| **ERR-26** | TorAPI (402) | 0 | — | — |
| **ERR-27** | QMediaPlayer demux | 1 | 5 сек | потом fallback |

### 8.2. Желательные (в roadmap)

| ID | Требование |
|---|---|
| **ERR-W-01** | Retry 429 для IA (сейчас `return []`) |
| **ERR-W-02** | Retry 5xx для IA Search |
| **ERR-W-03** | Retry при `database is locked` |
| **ERR-W-04** | Диалог при БД corrupt |

### 8.3. Принципы

| ID | Принцип |
|---|---|
| **ERR-P1** | Никогда не падать на сетевой ошибке |
| **ERR-P2** | Retry только для transient errors |
| **ERR-P3** | WARNING если пользователь не видит эффекта; ERROR — если видит |
| **ERR-P4** | Graceful degradation: один источник упал — остальные работают |
| **ERR-P5** | Fail fast для критичных: БД corrupt → диалог |
| **ERR-P6** | Пользовательские сообщения по-русски, без техдеталей |
| **ERR-P7** | Технические детали — в лог, не в UI |

---

## 9. Ограничения объёма

### 9.1. Обязательные

#### 9.1.1. Внешние API

| ID | Что | Лимит | При превышении |
|---|---|---|---|
| **LIM-01** | Количество результатов IA (`rows`) | 30 | Фиксировано (`_FETCH_LIMIT`) |
| **LIM-02** | Финальный топ после скоринга | 15 | `_FINAL_LIMIT` |
| **LIM-03** | Размер ответа Jackett/Prowlarr | 2 MB | Обрезать, лог |
| **LIM-04** | Размер ответа TorAPI | 2 MB | Обрезать, лог |
| **LIM-05** | Размер ответа балансера | 2 MB | Обрезать, лог |
| **LIM-06** | Размер ответа tracker_balancer | 1 MB | Обрезать, лог |

#### 9.1.2. Кэш

| ID | Что | Лимит |
|---|---|---|
| **LIM-07** | LRU метаданных IA | 500 записей |
| **LIM-08** | TTL метаданных IA | 24 часа |
| **LIM-09** | TTL популярных списков | 24 часа |
| **LIM-10** | TTL поисковых списков | 6 часов |
| **LIM-11** | TTL short-кэша KP | 30 дней |

#### 9.1.3. Файлы

| ID | Что | Лимит |
|---|---|---|
| **LIM-12** | Максимальный размер файла для стрима (IA) | 4 GB |
| **LIM-13** | Минимальный размер файла (IA) | 30 MB |
| **LIM-14** | Максимальный размер файла (P2P) | 100 GB |
| **LIM-15** | Минимальный размер файла (P2P) | 20 MB |
| **LIM-16** | Папка загрузок | 50 GB |
| **LIM-17** | Handles в libtorrent | 12 |
| **LIM-18** | Прямых URL для перебора | 15 |
| **LIM-19** | Трекеров на торрент | 200 |
| **LIM-20** | Multi-file threshold | 5 GB × 2 файла |

#### 9.1.4. Текстовые поля

| ID | Что | Лимит |
|---|---|---|
| **LIM-21** | Описание (display) | 500 символов |
| **LIM-22** | Описание (storage) | 2000 символов |
| **LIM-23** | Название (карточка) | 200 символов |
| **LIM-24** | Поисковый запрос | 100 символов |
| **LIM-25** | Лог-файл | 10 MB × 3 файла |

### 9.2. Желательные (в roadmap)

| ID | Требование |
|---|---|
| **LIM-W-01** | Лимит размера ответа IA Search (5 MB) |
| **LIM-W-02** | Лимит размера ответа IA Metadata (10 MB) |
| **LIM-W-03** | Лимит размера постера в runtime (5 MB) |
| **LIM-W-04** | Лимит размера `.torrent` файла (10 MB) |

### 9.3. Принципы

| ID | Принцип |
|---|---|
| **LIM-P1** | Все лимиты — в `config.py` |
| **LIM-P2** | При превышении — не падать, логировать |
| **LIM-P3** | При изменении — обновлять SRS |
| **LIM-P4** | Пользователь видит только actionable сообщения |

---

## 10. Что НЕ входит (Out of Scope)

Явно **не** реализуется в v2.x — осознанное решение:

- macOS, мобильные платформы
- Субтитры, выбор аудиодорожки
- Chromecast, AirPlay, DLNA
- Пользовательские аккаунты, облачная синхронизация
- ML-рекомендации
- Скачивание для офлайн (только стриминг)
- Code signing (в roadmap)
- Английский UI (EN/RU переключает поиск, не интерфейс)
- Взрослый контент / 18+
- Пользовательские плейлисты
- Поиск по режиссёру / актёру
- Теги и категории в БД (в roadmap, F-W-09)

---

## 11. Известные компромиссы

| Что | Почему оставил | Цена |
|---|---|---|
| `_sync_card_filters` через QTimer 300ms | Проще, чем сигнал из `add_card_to_grid` | Оверхед 3 r/sec |
| `paintEvent` шум попиксельно | Только light theme + header | O(w·75) на resize |
| `_read_json`/`_write_json` sync в `kp_service` | JSON 5–10 KB, миллисекунды | Блокировка loop ~40ms в PRIVATE |
| N+1 в `_build_movies_from_whitelist` | 20 карточек — незаметно | 21 запрос вместо 1 |
| Нет тестов на fallback | Моки libtorrent — отдельная задача | Непокрытая логика |
| `print()` в `config.py` | `import config` до `setup_logging` | Логи до инициализации — в stdout |

---

## 12. Связь с планами

| Требования | Plan |
|---|---|
| F-01…F-14, F-30…F-35, UI-01…UI-06 | `plans/01-public-streaming.md` |
| F-15…F-23 | `plans/02-p2p-streaming.md` |
| F-24…F-29 | `plans/03-fallback.md` (не написан, в roadmap) |
| F-36…F-38 | `plans/05-switch-mode.md` (не написан, в roadmap) |
| F-39…F-42 | Распределены по планам |
| N-01…N-20, API-01…API-37, ERR-01…ERR-27, LIM-01…LIM-25 | Распределены (acceptance / инварианты) |

---

## 13. Критерии готовности

Проект считается выполненным, если:

1. **Все обязательные функциональные требования** (F-01…F-42) выполнены и проверены
2. **Все обязательные нефункциональные** (N-01…N-20) выполнены или обоснованно отклонены
3. **Все обязательные требования к API** (API-01…API-37) реализованы
4. **Все обязательные требования к ошибкам** (ERR-01…ERR-27) покрыты
5. **Все обязательные ограничения** (LIM-01…LIM-25) заданы в config и применяются
6. **Схема БД** соответствует разделу 3
7. **Все экраны** (раздел 4) реализованы
8. **Сборка Nuitka** проходит, `.dist` содержит exe + data + ui
9. **Smoke-тесты** (`pytest`) проходят
10. **Документация** (README ×2, LICENSE, LICENSES ×2, NOTICE, README-LINUX, roadmap) в наличии
11. **Демонстрация** на защите: public + private + переключение

**Желательные требования (F-W, API-W, ERR-W, LIM-W) — не входят в критерии готовности v2.x. См. `docs/roadmap.md`.**
