[🇬🇧 English](README.md) | [🇷🇺 Русский](README.ru.md)

<div align="center">

# Amagi-Player

**A desktop player for discovering and streaming public-domain content from open archives.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()

</div>

---

## About

Amagi-Player is a desktop application for searching and playing
audiovisual content that is in the **public domain** or distributed
by rights holders under open terms (Creative Commons, Open Access,
and similar regimes).

The application is configured out of the box to work with
**Internet Archive** — the largest open archive, which publishes
millions of items and provides its own API and HTTP file delivery.
Amagi-Player uses the standard Internet Archive mechanisms
(`advancedsearch`, `metadata`, `download`) and does not host or
redistribute the works themselves.

The application runs **locally**, with no analytics or telemetry.
Network requests are made only to the sources that the user
explicitly chooses for search and playback.

---

## Features

### Search and playback (public — supported)

- Search across Internet Archive — the largest open archive of
  public-domain works
- Direct HTTP playback from `archive.org/download/...`
  via QMediaPlayer + FFmpeg
- Built-in player: play/pause, seek, fullscreen
- "Continue watching" feature backed by local history
- Poster and metadata cache

### Experimental features (private — testing, for developers)

These features exist in the codebase for architecture testing;
they are not documented and not supported:

- BitTorrent streaming via **libtorrent** — playback of
  magnet links and `.torrent` files from external sources
  (not from Internet Archive)
- Alternative-source picker for unstable streams
- User-defined sources (`data/sources.txt`)
- External indexers (local Jackett and similar)
- Headless site parsing via `nodriver`

### Performance and reliability

- **Asynchronous architecture** on `asyncio` + `qasync` — the
  UI stays responsive during search and buffering
- **Blocking I/O** (cache reads, poster writes) is offloaded to
  `run_in_executor` — the event loop is never blocked
- **Child process control**: stuck processes are terminated
  automatically via `psutil`
- Isolated execution of external utilities with lifetime control

### User interface

- Dark minimalist theme built on **PyQt6**
- Works "out of the box" on Windows
- Distributed as a ZIP archive containing the executable

---

## How it works

The public mode (the only supported one for end users) consists of
two independent stages.

### Stage 1 — feed search (local)

```text
1. User types a query into the search bar (or leaves it empty)
2. Query goes to the local database data/whitelist.db
   SQL: SELECT kp_id FROM movie_whitelist
        WHERE (title_ru LIKE '%query%' OR title_en LIKE '%query%')
          AND available = 1
        ORDER BY kp_id DESC LIMIT 20 OFFSET N
   For an empty query — the last 20 records from the database
3. For each card — poster cascade:
   cache (data/cache/{kp_id}.jpg) → data/seed_posters/{kp_id}.jpg →
   archive.org/services/img/{identifier} → Kinopoisk API
4. User sees a grid of cards; click → details card
5. Details metadata: from WhitelistRepository (if kp_id < 0)
   or from KPService.get_movie_data (if kp_id > 0)
```

The local database is prepared in advance (via `make_seed.py` in
the source tree) and ships inside the ZIP already populated. No
network requests are needed for this stage — except to fetch
posters that are not yet cached.

### Stage 2 — playback (network)

```text
1. User clicks "Start streaming" on the details card
2. StreamController reads title_ru, title_en, year, imdb_id
   and calls aggregator.find_torrent_stream(legal_only=True)
3. aggregator._safe_archive_org → ArchiveOrgSearcher.search(
     query = title_en or title_ru,
     year
   )
4. ArchiveOrgSearcher.search:
   a) advancedsearch: title:("...") AND year:[y-1 TO y+1]
      AND mediatype:(movies), sort downloads desc, rows=10
   b) For each of the top 8 results — metadata/{identifier}
   c) Inside the metadata: iterate files, pick the largest
      one with a video extension (.mp4/.mkv/.webm/...)
   d) Scoring to sort results:
        language (×100) + title precision (×50) + downloads (×20)
      Explicitly wrong language (lang_s=0.0) — excluded
5. stream_controller._execute_cascade:
   direct_url sorted by size, the largest is chosen
6. playback.play_url(url) → QMediaPlayer.setSource(
     QUrl("https://archive.org/download/{id}/{file}")
   )
7. QMediaPlayer + FFmpeg open the HTTP stream directly from archive.org
   (HTTP Range for seeking)
```

Additional details:

- **Feed on the home screen** is built from the local database
  `data/whitelist.db`. The database ships in the ZIP already
  populated; in the source tree it can be rebuilt from
  `data/whitelist_seed.db` via `tools/apply_seed.py`.
- **Poster and metadata cache** is stored in `data/cache/`. On every
  request the TTL is checked: stale files are overwritten with new
  ones. `tools/cache_stats.py clear-stale` removes stale files.
- **Watch history** is stored in `data/app_data.db` and backs the
  "Continue watching" feature.

---

## Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.10+ | Primary language |
| GUI | **PyQt6** | User interface |
| Event loop | **qasync** | Bridge between `asyncio` and Qt |
| HTTP | **aiohttp** | Async requests to sources |
| Streaming | **libtorrent** | Streaming of external sources (developer mode) |
| Processes | **psutil** | Child process management and termination |
| Media | **QMediaPlayer** + FFmpeg | Video playback |
| Tests | **pytest** | Unit and integration tests |

---

## Architecture

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
     │    │          │              │  testing)  │
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

## Requirements

- **Windows 10/11**
- ~200–300 MB of free disk space (dependencies + cache)
- Internet access for search and playback

For **running from source** you additionally need: **Python 3.10+**.

---

## Installation

### From Releases (recommended)

1. Download the ZIP from the [**Releases**](https://github.com/AkashaForge/ama-gi-player/releases) page
2. Unpack it into any folder
3. Run `amagi-player.exe`
4. Accept the terms of use (disclaimer)

The database `data/whitelist.db` ships in the ZIP already populated.
If you delete it, the next launch will create an empty table — the
feed will stay empty. To restore it from the seed, use
`tools/apply_seed.py` (in the source tree).

### From source

```bash
git clone https://github.com/AkashaForge/ama-gi-player.git
cd ama-gi-player
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

### For development

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Usage

1. **Launch the application** and accept the disclaimer.
2. **Enter a search query** — by default the search runs against
   Internet Archive.
3. **Select a result** — a details card opens with metadata,
   a poster, and a play button.
4. **Playback** starts automatically.
5. **Continue watching** — history is stored locally.

---

## Configuration

### Operating modes

The application runs in one of two modes, determined by the file
`data/mode.txt`. If the file is absent, `public` is used.

| Mode | Status | Purpose |
|---|---|---|
| `public` | **Supported** | Works with Internet Archive. Default mode |
| `private` | **Testing, for developers** | Experimental architecture. Not documented and not supported |

### Metadata (optional)

For extended film metadata (descriptions, posters), the public
Kinopoisk API can be used. The key is provided in the `.env` file
next to `amagi-player.exe`:

```text
KP_API_KEY=your_key
```

Without the key, the application works with Internet Archive, but
descriptions and posters may be incomplete. The log will contain
the line `KP_API_KEY is not set — demo mode`.

---

## Diagnostics

The application prints diagnostic messages to the console
(opened alongside `amagi-player.exe`). Useful lines:

| Log line | Meaning |
|---|---|
| `Mode: PUBLIC (legal-only)` | Public mode is active (normal) |
| `KP_API_KEY is not set — demo mode` | No Kinopoisk key (optional) |
| `Feed: page=N, M films` | Feed loaded |
| `IA query: ...` | Request to Internet Archive |
| `IA result: N direct_url` | N results found |
| `Failed to initialize QMediaPlayer` | FFmpeg backend not loaded (check the build) |

If the application does not start — launch `amagi-player.exe` from
PowerShell (`cd <folder>; .\amagi-player.exe`) to see the full
traceback in the console.

---

## Project structure

```text
ama-gi-player/
├── controllers/          # UI controllers
├── core/                 # Core (event loop, managers)
├── data/                 # Configuration and data
│   ├── whitelist_seed.db # Database of public-domain films
│   ├── whitelist.db      # Working database (created on first launch)
│   └── cache/            # Poster and metadata cache
├── database/             # Local database (history, cache)
├── search/               # Search engine
├── services/             # External services
├── tests/                # Tests (pytest)
├── tools/                # Utilities
├── ui/                   # PyQt6 widgets
├── legal_gate.py         # Disclaimer dialog
├── legal_texts.py        # Disclaimer and privacy policy texts
├── main.py               # Entry point
├── config.py             # Configuration
├── requirements.txt
└── bin/                  # External utilities (only README.txt by default)
```

---

## Legal information

Amagi-Player is distributed under the
**GNU General Public License v3.0**.

- Full license text — [`LICENSE`](LICENSE)
- Third-party components — [`LICENSES.txt`](LICENSES.txt)
- Attribution — [`NOTICE`](NOTICE)
- Code signing policy — [`CODE_SIGNING_POLICY.md`](CODE_SIGNING_POLICY.md)
- Security policy — [`SECURITY.md`](SECURITY.md)
- Terms of use and privacy policy are shown on first launch
  (see `legal_texts.py`)

In short:

- The application does not host or redistribute works.
- The default sources are open public-domain archives
  (Internet Archive).
- The application runs locally, with no analytics or telemetry.

---

## Contributing

PRs and Issues are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md)
for details.

By submitting a PR, you agree to license your contribution under
**GPLv3**.

---

## License

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
