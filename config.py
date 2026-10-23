"""Централизованная конфигурация Amagi-Player."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DISABLE_WHITELIST = False

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "app_data.db"
WHITELIST_DB_PATH = DATA_DIR / "whitelist.db"
JACKETT_DATA_DIR = DATA_DIR / "JackettData"
PROWLARR_DATA_DIR = DATA_DIR / "ProwlarrData"
DOWNLOADS_DIR = DATA_DIR / "downloads"
CUSTOM_SOURCES_FILE = DATA_DIR / "sources.txt"

BIN_DIR = BASE_DIR / "bin"
ARIA2_EXE = BIN_DIR / "Aria2" / "aria2c.exe"

JACKETT_DIR = BIN_DIR / "Jackett"
JACKETT_EXE = JACKETT_DIR / "JackettConsole.exe"
JACKETT_PORT = 9117

PROWLARR_DIR = BIN_DIR / "Prowlarr"
PROWLARR_EXE = PROWLARR_DIR / "Prowlarr.exe"
PROWLARR_PORT = 9696

ARIA2_PORT = 6888
NETWORK_TIMEOUT = 15
USER_AGENT = "AmagiPlayer/2.0"
MAX_TORRENT_SIZE_BYTES = 50 * 1024 * 1024 * 1024
TEST_MODE = False

for _dir in (CACHE_DIR, JACKETT_DATA_DIR, PROWLARR_DATA_DIR, DOWNLOADS_DIR):
    os.makedirs(_dir, exist_ok=True)

KP_API_KEY = ""
ARIA2_SECRET = "amagi_secure_fallback_token_2026"

env_path = BASE_DIR / ".env"
if env_path.exists():
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "KP_API_KEY":
                        KP_API_KEY = v
                    elif k == "ARIA2_SECRET":
                        ARIA2_SECRET = v
    except Exception as e:
        print(f"[CONFIG] Ошибка чтения .env: {e}")

if not KP_API_KEY:
    print("[CONFIG] KP_API_KEY не задан — демо-режим.")
else:
    print("[CONFIG] Ключ Кинопоиска загружен.")
print("[CONFIG] Защитный токен P2P-модулей загружен.")

JACKETT_API_KEY = ""
PROWLARR_API_KEY = ""

# ==============================================================================
# 5. LIBTORRENT — STREAMING
# ==============================================================================
LIBTORRENT_PORT = 6881

# --- Настройки сессии (issue #7666, libtorrent 2.1.1) ---
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

# --- Какие контейнеры стримабельны ---
LIBTORRENT_STREAMABLE_EXTS = (
    ".mp4", ".mkv", ".webm", ".m4v", ".mov", ".avi", ".wmv", ".flv",
)
LIBTORRENT_REJECT_EXTS = (
    ".vob", ".ifo", ".bup", ".ts", ".m2ts", ".mts",
    ".mpg", ".mpeg", ".rmvb", ".divx", ".asf", ".3gp", ".ogv", ".f4v",
)

# --- PieceScheduler ---
PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS = 100
PIECE_SCHEDULER_LOOKAHEAD_PIECES = 10
PIECE_SCHEDULER_DEADLINE_STEP_MS = 150
PIECE_SCHEDULER_TRAILING_RETENTION = 3
PIECE_SCHEDULER_TAIL_DEADLINE_MS = 1000

# --- PeerMonitor ---
PEER_MONITOR_INTERVAL_SEC = 2.0
PEER_MONITOR_TOP_N = 5

# --- HttpRangeServer ---
HTTP_RANGE_CACHE_PIECES = 3
HTTP_RANGE_POLL_SEC = 0.05
HTTP_RANGE_CHUNK_SIZE = 128 * 1024

# --- StreamSession ---
STREAM_SESSION_READY_MIN_CONNECTED_PEERS = 3
STREAM_SESSION_READY_MIN_PIECES = 1
STREAM_SESSION_STARTUP_TIMEOUT_SEC = 30.0
STREAM_SESSION_ADAPTIVE_START_BYTES = 8 * 1024 * 1024

# --- SourceSelector ---
SOURCE_SELECTOR_MIN_SEEDERS = 1
SOURCE_SELECTOR_QUALITY_BONUS_1080P = 15
SOURCE_SELECTOR_QUALITY_BONUS_4K = 20
SOURCE_SELECTOR_SIZE_PENALTY_GB = 0.5
SOURCE_SELECTOR_MAX_ALTERNATIVES = 10

# ==============================================================================
# 6. STREAMING / UI MONITORING
# ==============================================================================
STREAM_BUFFER_STOP_DELAY_SEC = 30.0
STREAM_DEMUX_ERROR_COOLDOWN_SEC = 1.0
STREAM_MONITOR_INTERVAL_MS = 1000
STREAMING_FILE_READ_RETRY = 5
STREAMING_FILE_READ_RETRY_DELAY = 0.2

# --- FILTERS ---
SEARCH_YEAR_TOLERANCE = 1
SEARCH_MIN_MATCHES_RATIO = 0.6
SEARCH_EXACT_QUERY_BONUS = 30
SEARCH_YEAR_MATCH_BONUS = 20
SEARCH_SEEDERS_DIVISOR = 10
SEARCH_MAX_RESULTS = 50
SEARCH_REJECT_COLLECTIONS_IF_YEAR = True

# ==============================================================================
# 7. ЯЗЫК
# ==============================================================================
SEARCH_LANGUAGE = "en"

# Идентификаторы индексаторов для определения языка релиза
# (используется в aggregator._is_russian_release для фильтрации результатов,
# НЕ для доступа к этим трекерам).
RU_INDEXER_IDS = frozenset({
    "rutracker", "rutor", "kinozal", "nnmclub", "nnm-club",
    "megapeer", "piratbit", "torrent9", "seedoff", "lostfilm",
    "baibako", "alexfilm", "kerob", "hdrezka",
})

# ==============================================================================
# 8. БРАУЗЕР
# ==============================================================================
CHROME_PATH = None
if sys.platform == "win32" and CHROME_PATH is None:
    _possible_paths = [
        str(BIN_DIR / "Chrome" / "chrome.exe"),
        str(BIN_DIR / "Chromium" / "chrome.exe"),
        os.path.expandvars(r"${ProgramFiles}\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"${ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"${LocalAppData}\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"${ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"${ProgramFiles}\Microsoft\Edge\Application\msedge.exe"),
    ]
    for _p in _possible_paths:
        if os.path.exists(_p):
            CHROME_PATH = _p
            print(f"[CONFIG] Найден браузер: {CHROME_PATH}")
            break

if CHROME_PATH is None:
    print("[CONFIG] Браузер не найден — будет использован HTTP-fallback.")
else:
    print(f"[CONFIG] Браузер: {CHROME_PATH}")

BROWSER_HEADLESS = True
BROWSER_FETCH_TIMEOUT = 30
BROWSER_MAX_TOTAL_TIMEOUT = 90
BROWSER_EXTRA_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--window-position=-32000,-32000",
    "--window-size=1280,800",
]

NODRIVER_EXTRA_ARGS = BROWSER_EXTRA_ARGS
CLOUDFLARE_HEADLESS = True
CLOUDFLARE_SOLVE_TIMEOUT = 15
RU_SEARCH_TIMEOUT = 60

HTTP_FETCH_PER_SOURCE_TIMEOUT = 20.0
HTTP_FETCH_TOTAL_TIMEOUT = 60.0
HTTP_FETCH_USE_SYSTEM_PROXY = True
HTTP_FETCH_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]
HTTP_FETCH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

WHITELIST_TRACKERS = [
    "internetarchive", "publicdomaintorrents",
    "legittorrents", "academictorrents",
]

ARCHIVE_ORG_ENABLED = True
ARCHIVE_ORG_MAX_RESULTS = 10
ARCHIVE_ORG_MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024

DOWNLOADS_MAX_GB = 50
DOWNLOADS_CLEANUP_ON_START = True

LEGAL_DISCLAIMER_ACCEPTED = False

CACHE_SHORT_DIR = CACHE_DIR / "short"
CACHE_FULL_DIR = CACHE_DIR / "full"
CACHE_LISTS_DIR = CACHE_DIR / "lists"

for _d in (CACHE_SHORT_DIR, CACHE_FULL_DIR, CACHE_LISTS_DIR):
    os.makedirs(_d, exist_ok=True)

POPULAR_CACHE_TTL_HOURS = 24
SEARCH_CACHE_TTL_HOURS = 6
SHORT_CACHE_TTL_HOURS = 24 * 30

_MODE_FILE = DATA_DIR / "mode.txt"
_runtime_mode = "public"
if _MODE_FILE.exists():
    try:
        _content = _MODE_FILE.read_text(encoding="utf-8").strip().lower()
        if _content in ("public", "private"):
            _runtime_mode = _content
    except Exception:
        pass

MODE = _runtime_mode

if _runtime_mode == "private":
    LEGAL_ONLY_MODE = False
    LEGAL_TRACKERS_TAG = ""
    LEGAL_FEED_ONLY_AVAILABLE = False
    DISABLE_WHITELIST = True
    SEARCH_LANGUAGE = "ru"
    print("[CONFIG] Режим: PRIVATE (полный функционал)")
else:
    LEGAL_ONLY_MODE = True
    LEGAL_TRACKERS_TAG = "legal"
    LEGAL_FEED_ONLY_AVAILABLE = True
    DISABLE_WHITELIST = False
    SEARCH_LANGUAGE = "en"
    print("[CONFIG] Режим: PUBLIC (legal-only)")

LAZY_RESOLVE = True

# ==============================================================================
# YTS (YIFY) API
# ==============================================================================
# URL читается из data/yts_api_base.txt (в .gitignore, локальный файл).
# Шаблон для пользователя — data/yts_api_base.example.txt.
# YTS включается только в PRIVATE-режиме (mode.txt) и только если URL задан.
YTS_ENABLED = (_runtime_mode == "private")
YTS_MAX_RESULTS = 20

# ==============================================================================
# LEGAL JACKETT INDEXERS (public domain, всегда доступны)
# ==============================================================================
# Эти индексаторы пропускаются в public режиме. В private — все.
# Сами индексаторы настраиваются пользователем в UI Jackett
# (http://127.0.0.1:9117/UI/Dashboard).
LEGAL_JACKETT_INDEXERS = frozenset({
    "internetarchive",
    "publicdomaintorrents",
    "academictorrents",
    "legittorrents",
})
