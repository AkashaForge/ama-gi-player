[🇬🇧 English](README.md) | [🇷🇺 Русский](README.ru.md)

<div align="center">

# Amagi-Player

**Десктоп-плеер для поиска и воспроизведения контента общественного достояния из открытых архивов.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()

</div>

---

## О проекте

Amagi-Player — десктоп-приложение для поиска и воспроизведения
аудиовизуального контента, находящегося в **общественном достоянии**
(public domain) либо распространяемого правообладателями на открытых
условиях (Creative Commons, Open Access и аналогичные режимы).

Приложение изначально настроено на работу с **Internet Archive** —
крупнейшим открытым архивом, который публикует миллионы единиц
контента и предоставляет собственный API и HTTP-доставку файлов.
Amagi-Player использует штатные механизмы Internet Archive
(`advancedsearch`, `metadata`, `download`) и не хранит
и не распространяет сами произведения.

Приложение работает **локально**, без аналитики и телеметрии.
Сетевые запросы выполняются только к тем источникам, которые
пользователь явно использует для поиска и воспроизведения.

---

## Возможности

### Поиск и воспроизведение (public — поддерживается)

- Поиск по Internet Archive — крупнейшему открытому архиву
  общественного достояния
- Прямое HTTP-воспроизведение с `archive.org/download/...`
  через QMediaPlayer + FFmpeg
- Встроенный плеер: пауза, перемотка, полный экран
- Функция «Продолжить просмотр» с локальной историей
- Кэш постеров и метаданных

### Экспериментальные функции (private — тестовый, для разработчиков)

Эти функции присутствуют в коде для тестирования архитектуры,
не документируются и не поддерживаются:

- Потоковое воспроизведение через **libtorrent** — работа
  с magnet-ссылками и `.torrent`-файлами от внешних источников
  (не от Internet Archive)
- Выбор альтернативной раздачи при нестабильном стриме
- Пользовательские источники (`data/sources.txt`)
- Внешние индексаторы (локальный Jackett и аналогичные)
- Headless-парсинг сайтов через `nodriver`

### Производительность и надёжность

- **Асинхронная архитектура** на `asyncio` + `qasync` — интерфейс
  не блокируется во время поиска и буферизации
- **Блокирующий I/O** (чтение файлов кэша, запись постеров)
  вынесен в `run_in_executor` — не блокирует event loop
- **Контроль дочерних процессов**: автоматическое завершение
  «повисших» процессов через `psutil`
- Изолированный запуск внешних утилит с контролем времени жизни

### Интерфейс

- Тёмная минималистичная тема на **PyQt6**
- Работает «из коробки» на Windows
- Распространение в виде ZIP-архива с exe-файлом

---

## Как это работает

Публичный режим (единственный поддерживаемый) состоит из двух
независимых этапов.

### Этап 1 — поиск в ленте (локальный)

```text
1. Пользователь вводит запрос в строке поиска (или оставляет пустым)
2. Запрос идёт в локальную базу data/whitelist.db
   SQL: SELECT kp_id FROM movie_whitelist
        WHERE (title_ru LIKE '%query%' OR title_en LIKE '%query%')
          AND available = 1
        ORDER BY kp_id DESC LIMIT 20 OFFSET N
   Для пустого запроса — последние 20 записей из базы
3. Для каждой карточки — каскад постера:
   кэш (data/cache/{kp_id}.jpg) → data/seed_posters/{kp_id}.jpg →
   archive.org/services/img/{identifier} → Kinopoisk API
4. Пользователь видит сетку карточек; клик → карточка деталей
5. Метаданные деталей: из WhitelistRepository (если kp_id < 0)
   или из KPService.get_movie_data (если kp_id > 0)
```

Локальная база формируется заранее (утилитой `make_seed.py`
в исходниках) и поставляется в ZIP уже заполненной. Никаких
сетевых запросов на этом этапе не требуется — только для
подгрузки постеров, если их нет в кэше.

### Этап 2 — воспроизведение (сетевой)

```text
1. Пользователь нажимает «Запустить трансляцию» в карточке
2. StreamController берёт title_ru, title_en, year, imdb_id
   и вызывает aggregator.find_torrent_stream(legal_only=True)
3. aggregator._safe_archive_org → ArchiveOrgSearcher.search(
     query = title_en или title_ru,
     year
   )
4. ArchiveOrgSearcher.search:
   a) advancedsearch: title:("...") AND year:[y-1 TO y+1]
      AND mediatype:(movies), sort downloads desc, rows=10
   b) Для каждого из топ-8 результатов — metadata/{identifier}
   c) Внутри метаданных: перебор файлов, выбор самого большого
      с видео-расширением (.mp4/.mkv/.webm/...)
   d) Скоринг для сортировки результатов:
        язык (×100) + точность title (×50) + downloads (×20)
      Явно чужой язык (lang_s=0.0) — отсев, не попадает в список
5. stream_controller._execute_cascade:
   direct_url сортируются по размеру, берётся самый большой
6. playback.play_url(url) → QMediaPlayer.setSource(
     QUrl("https://archive.org/download/{id}/{file}")
   )
7. QMediaPlayer + FFmpeg открывают HTTP-поток напрямую с archive.org
   (HTTP Range для seek)
```

Дополнительно:

- **Лента на главном экране** формируется из локальной базы
  `data/whitelist.db` — списка фильмов общественного достояния
  с постером и метаданными. База поставляется в ZIP уже
  заполненной; в исходниках её можно пересоздать из
  `data/whitelist_seed.db` через `tools/apply_seed.py`.
- **Кэш постеров и метаданных** хранится в `data/cache/`. При
  запросе проверяется TTL: устаревшие файлы перезаписываются
  новыми. Утилита `tools/cache_stats.py clear-stale`
  (в исходниках) позволяет вручную удалить устаревшие файлы.
- **История просмотров** сохраняется в `data/app_data.db`
  и используется для функции «Продолжить просмотр».

---

## Технологический стек

| Слой | Технология | Назначение |
|---|---|---|
| Язык | Python 3.10+ | Основной язык проекта |
| GUI | **PyQt6** | Пользовательский интерфейс |
| Event loop | **qasync** | Мост между `asyncio` и Qt |
| HTTP | **aiohttp** | Асинхронные запросы к источникам |
| Потоковая доставка | **libtorrent** | Потоковое воспроизведение раздач внешних источников (режим разработчика) |
| Процессы | **psutil** | Управление и завершение дочерних процессов |
| Медиа | **QMediaPlayer** + FFmpeg | Воспроизведение видео |
| Тесты | **pytest** | Юнит- и интеграционные тесты |

---

## Архитектура

```text
┌──────────────────────────────────────────────┐
│                  PyQt6 UI                    │
│            (qasync event loop)               │
└───────────────┬──────────────────────────────┘
                │
     ┌──────────┴───────────┐
     │                      │
┌────▼─────┐          ┌─────▼──────┐
│  Search  │          │   Player   │
│  Engine  │          │            │
│ (async)  │          └─────┬──────┘
└────┬─────┘                │
     │         ┌────────────┴─────────────┐
     │         │                          │
     │    ┌────▼─────┐              ┌─────▼──────┐
     │    │ HTTP     │              │ libtorrent │
     │    │ (public) │              │ (private,  │
     │    │          │              │  тестовый) │
     │    └──────────┘              └─────┬──────┘
     │                                    │
     │                             ┌──────▼─────┐
     │                             │  Process   │
     │                             │  Manager   │
     │                             │  (psutil)  │
     │                             └────────────┘
     │
┌────▼──────────────────────────────┐
│  Sources                          │
│  └─ Internet Archive (default)    │
└───────────────────────────────────┘
```

---

## Требования

- **Windows 10/11**
- ~200–300 МБ свободного места (зависимости + кэш)
- Интернет для поиска и воспроизведения

Для **запуска из исходников** дополнительно: **Python 3.10+**.

---

## Установка

### Из Releases (рекомендуется)

1. Скачайте ZIP со страницы [**Releases**](https://github.com/AkashaForge/ama-gi-player/releases)
2. Распакуйте в любую папку
3. Запустите `amagi-player.exe`
4. Примите условия использования (дисклеймер)

База `data/whitelist.db` поставляется в ZIP уже заполненной.
Если её удалить, при следующем запуске будет создана пустая
таблица — лента останется пустой. Для восстановления из seed
используйте `tools/apply_seed.py` (в исходниках).

### Из исходников

```bash
git clone https://github.com/AkashaForge/ama-gi-player.git
cd ama-gi-player
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

---

## Использование

1. **Запустите приложение** и примите дисклеймер.
2. **Введите поисковый запрос** — по умолчанию поиск идёт по
   Internet Archive.
3. **Выберите результат** — откроется карточка с метаданными,
   постером и кнопкой воспроизведения.
4. **Воспроизведение** запустится автоматически.
5. **Продолжить просмотр** — история сохраняется локально.

---

## Конфигурация

### Режимы работы

Приложение работает в одном из двух режимов, определяемых файлом
`data/mode.txt`. При отсутствии файла используется `public`.

| Режим | Статус | Назначение |
|---|---|---|
| `public` | **Поддерживается** | Работа с Internet Archive. Режим по умолчанию |
| `private` | **Тестовый, для разработчиков** | Экспериментальная архитектура. Не документируется и не поддерживается |

### Метаданные (опционально)

Для расширенных метаданных фильмов (описание, постеры) может
использоваться публичный API Кинопоиска. Ключ задаётся в файле
`.env` рядом с `amagi-player.exe`:

```text
KP_API_KEY=ваш_ключ
```

Без ключа приложение работает с Internet Archive, но описания
и постеры могут быть неполными. В логе будет строка
`KP_API_KEY не задан — демо-режим`.

---

## Диагностика

Приложение выводит диагностические сообщения в консоль
(открывается вместе с `amagi-player.exe`). Полезные строки:

| Строка в логе | Что означает |
|---|---|
| `Режим: PUBLIC (legal-only)` | Работает публичный режим (норма) |
| `KP_API_KEY не задан — демо-режим` | Нет ключа Кинопоиска (опционально) |
| `Лента: page=N, M фильмов` | Лента загружена |
| `IA query: ...` | Запрос к Internet Archive |
| `IA итог: N direct_url` | Найдено N результатов |
| `Failed to initialize QMediaPlayer` | Не загружен FFmpeg-бэкенд (проверьте сборку) |

Если приложение не запускается — запустите `amagi-player.exe`
из PowerShell (`cd <папка>; .\amagi-player.exe`), чтобы увидеть
полный traceback в консоли.

---

## Структура проекта

```text
ama-gi-player/
├── controllers/          # Контроллеры UI
├── core/                 # Ядро (event loop, менеджеры)
├── data/                 # Конфигурация и данные
│   ├── whitelist_seed.db # База фильмов общественного достояния
│   ├── whitelist.db      # Рабочая база (создаётся при первом запуске)
│   └── cache/            # Кэш постеров и метаданных
├── database/             # Локальная БД (история, кэш)
├── search/               # Движок поиска
├── services/             # Внешние сервисы
├── tests/                # Тесты (pytest)
├── tools/                # Утилиты
├── ui/                   # PyQt6-виджеты
├── legal_gate.py         # Окно дисклеймера
├── legal_texts.py        # Тексты дисклеймера и политики
├── main.py               # Точка входа
├── config.py             # Конфигурация
├── requirements.txt
└── bin/                  # Внешние утилиты (только README.txt по умолчанию)
```

---

## Правовая информация

Amagi-Player распространяется под **GNU General Public License v3.0**.

- Полный текст лицензии — [`LICENSE`](LICENSE)
- Сторонние компоненты — [`LICENSES.txt`](LICENSES.txt)
- Атрибуция — [`NOTICE`](NOTICE)
- Политика подписи кода — [`CODE_SIGNING_POLICY.md`](CODE_SIGNING_POLICY.md)
- Политика безопасности — [`SECURITY.md`](SECURITY.md)
- Условия использования и политика конфиденциальности показываются
  при первом запуске (см. `legal_texts.py`)

Кратко:

- Приложение не хранит и не распространяет произведения.
- Источники по умолчанию — открытые архивы общественного достояния
  (Internet Archive).
- Приложение работает локально, без аналитики и телеметрии.

---

## Участие в разработке

PR и Issues приветствуются. Подробности — в [`CONTRIBUTING.md`](CONTRIBUTING.md).

Отправляя PR, вы соглашаетесь лицензировать свой вклад под **GPLv3**.

---

## Лицензия

```text
Amagi-Player
Copyright (C) 2026 AkashaForge

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```