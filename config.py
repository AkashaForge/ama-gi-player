"""Централизованная конфигурация Amagi-Player."""
import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "app_data.db"
WHITELIST_DB_PATH = DATA_DIR / "whitelist.db"
JACKETT_DATA_DIR = DATA_DIR / "JackettData"
PROWLARR_DATA_DIR = DATA_DIR / "ProwlarrData"
DOWNLOADS_DIR = DATA_DIR / "downloads"
CUSTOM_SOURCES_FILE = DATA_DIR / "sources.txt"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
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

# LOGGING
LOG_FILE = LOGS_DIR / "amagi.log"
LOG_LEVEL_CONSOLE = "INFO"
LOG_LEVEL_FILE = "DEBUG"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_DEBUG_MODULES = []
CONNECT_LOG_FILE = LOGS_DIR / "connect.log"
CONNECT_LOG_ENABLED = True

# TRACKER BALANCER
TRACKER_BALANCERS_FILE = DATA_DIR / "tracker_balancers.txt"
TRACKER_BALANCERS_EXAMPLE = DATA_DIR / "tracker_balancers.example.txt"
TRACKER_CACHE_FILE = DATA_DIR / "trackers_cache.txt"
TRACKER_BALANCER_TTL_HOURS = 12
TRACKER_BALANCER_TIMEOUT_SEC = 10.0
TRACKER_BALANCER_MAX_URLS = 10
TRACKER_BALANCER_MAX_TRACKERS = 200
TRACKER_BALANCER_MAX_RESPONSE_BYTES = 1024 * 1024
TRACKER_BALANCER_VERIFY_SSL = True

# ONLINE BALANCERS
BALANCERS_FILE = DATA_DIR / "balancers.txt"
BALANCERS_EXAMPLE = DATA_DIR / "balancers.example.txt"
BALANCERS_CACHE = DATA_DIR / "balancers_cache.json"
BALANCER_CACHE_TTL_HOURS = 6
BALANCER_REQUEST_TIMEOUT_SEC = 10.0
BALANCER_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
BALANCER_VALIDATE_TITLE_THRESHOLD = 0.65
BALANCER_BLACKLIST_FAILURES = 3
BALANCER_BLACKLIST_TTL_HOURS = 1
BALANCER_VERIFY_SSL = True

# Cloudflare bypass cascade
USE_CURL_CFFI = True
USE_CLOUDSCRAPER = True
USE_NODRIVER = True

# ==============================================================================
# YTS (YIFY) — URL из data/yts_api_base.txt
# ==============================================================================
YTS_ENABLED = True
YTS_API_BASE_FILE = DATA_DIR / "yts_api_base.txt"
YTS_MAX_RESULTS = 20
YTS_REQUEST_TIMEOUT = 10.0
YTS_MAX_RETRIES = 2
YTS_RETRY_DELAY = 2.0

# ==============================================================================
# TorAPI (русские трекеры) — URL из data/torapi_base.txt
# ==============================================================================
TORAPI_ENABLED = True
TORAPI_BASE_FILE = DATA_DIR / "torapi_base.txt"
TORAPI_REQUEST_TIMEOUT = 15.0
TORAPI_MAX_RESULTS = 30

# ==============================================================================
# API KEYS
# ==============================================================================
KP_API_KEY = ""
ARIA2_SECRET = ""
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
        print(f"[CONFIG] .env: {e}")

if not ARIA2_SECRET:
    _sf = DATA_DIR / ".aria2_secret"
    try:
        if _sf.exists():
            ARIA2_SECRET = _sf.read_text(encoding="utf-8").strip()
        if not ARIA2_SECRET:
            ARIA2_SECRET = secrets.token_urlsafe(32)
            _sf.write_text(ARIA2_SECRET, encoding="utf-8")
    except Exception as e:
        print(f"[CONFIG] ARIA2_SECRET: {e}")
        ARIA2_SECRET = secrets.token_urlsafe(32)

if not KP_API_KEY:
    print("[CONFIG] KP_API_KEY не задан.")
else:
    print("[CONFIG] Ключ Кинопоиска загружен.")
print("[CONFIG] Защитный токен загружен.")

JACKETT_API_KEY = ""
PROWLARR_API_KEY = ""

# ==============================================================================
# LIBTORRENT
# ==============================================================================
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

PIECE_SCHEDULER_PLAYHEAD_DEADLINE_MS = 100
PIECE_SCHEDULER_LOOKAHEAD_PIECES = 10
PIECE_SCHEDULER_DEADLINE_STEP_MS = 150
PIECE_SCHEDULER_TRAILING_RETENTION = 3
PIECE_SCHEDULER_TAIL_DEADLINE_MS = 1000
PIECE_SCHEDULER_DEADLINE_REFRESH_SEC = 5.0
PIECE_SCHEDULER_TAIL_COUNT = 20

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
STREAM_MIN_BITRATE_KBPS = 1000
STREAM_MAX_SOURCES = 12
MULTI_FILE_THRESHOLD_GB = 5
MULTI_FILE_MAX_COUNT = 2
MAX_STREAMABLE_FILE_GB = 100

PROBE_HEAD_PIECES = 5
PROBE_MIN_RATE_MB = 0.2
PROBE_MIN_PEERS = 10

# ==============================================================================
# SourceSelector: композитный health score (Popcorn Time style)
# ==============================================================================
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

# ==============================================================================
# STREAMING / UI MONITORING
# ==============================================================================
STREAM_BUFFER_STOP_DELAY_SEC = 30.0
STREAM_DEMUX_ERROR_COOLDOWN_SEC = 1.0
STREAM_MONITOR_INTERVAL_MS = 1000
STREAMING_FILE_READ_RETRY = 5
STREAMING_FILE_READ_RETRY_DELAY = 0.2

# ==============================================================================
# FILTERS
# ==============================================================================
SEARCH_YEAR_TOLERANCE = 1
SEARCH_MIN_MATCHES_RATIO = 0.6
SEARCH_EXACT_QUERY_BONUS = 30
SEARCH_YEAR_MATCH_BONUS = 20
SEARCH_SEEDERS_DIVISOR = 10
SEARCH_MAX_RESULTS = 50
SEARCH_REJECT_COLLECTIONS_IF_YEAR = True

# ==============================================================================
# ЯЗЫК
# ==============================================================================
SEARCH_LANGUAGE = "en"

RU_INDEXER_IDS = frozenset({
    "rutracker", "rutor", "kinozal", "nnmclub", "nnm-club",
    "megapeer", "piratbit", "torrent9", "seedoff", "lostfilm",
    "baibako", "alexfilm", "kerob", "hdrezka",
})

# ==============================================================================
# БРАУЗЕР
# ==============================================================================
CHROME_PATH = None
if sys.platform == "win32":
    _paths = [
        str(BIN_DIR / "Chrome" / "chrome.exe"),
        str(BIN_DIR / "Chromium" / "chrome.exe"),
        os.path.expandvars(r"${ProgramFiles}\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"${ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"${LocalAppData}\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"${ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"${ProgramFiles}\Microsoft\Edge\Application\msedge.exe"),
    ]
    for _p in _paths:
        if os.path.exists(_p):
            CHROME_PATH = _p
            print(f"[CONFIG] Браузер: {CHROME_PATH}")
            break
if CHROME_PATH is None:
    print("[CONFIG] Браузер не найден.")

BROWSER_HEADLESS = True
BROWSER_FETCH_TIMEOUT = 30
BROWSER_MAX_TOTAL_TIMEOUT = 90
BROWSER_EXTRA_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run", "--no-default-browser-check",
    "--disable-dev-shm-usage", "--disable-gpu",
    "--window-position=-32000,-32000", "--window-size=1280,800",
]
NODRIVER_EXTRA_ARGS = BROWSER_EXTRA_ARGS
CLOUDFLARE_HEADLESS = True
CLOUDFLARE_SOLVE_TIMEOUT = 15
RU_SEARCH_TIMEOUT = 60

WEB_FETCHER_MIN_HTTP_RESULTS = 2
HTTP_FETCH_PER_SOURCE_TIMEOUT = 8.0
HTTP_FETCH_TOTAL_TIMEOUT = 60.0
HTTP_FETCH_USE_SYSTEM_PROXY = True
HTTP_FETCH_VERIFY_SSL = True
HTTP_FETCH_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]
HTTP_FETCH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

JACKETT_DEBUG_SAVE_XML = False
JACKETT_REQUEST_TIMEOUT = 8.0
JACKETT_RETRY_DELAYS = [0.3, 0.7]

WHITELIST_TRACKERS = ["internetarchive", "publicdomaintorrents",
                       "legittorrents", "academictorrents"]
ARCHIVE_ORG_ENABLED = True
ARCHIVE_ORG_MAX_RESULTS = 10
ARCHIVE_ORG_MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
ARCHIVE_ORG_MAX_METADATA_CHECKS = 8
ARCHIVE_ORG_METADATA_CACHE_TTL = 24 * 3600
ARCHIVE_ORG_METADATA_CACHE_MAX = 500
ARCHIVE_ORG_MIN_MOVIE_SIZE = 400 * 1024 * 1024

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
        _c = _MODE_FILE.read_text(encoding="utf-8").strip().lower()
        if _c in ("public", "private"):
            _runtime_mode = _c
    except Exception:
        pass

MODE = _runtime_mode
if _runtime_mode == "private":
    LEGAL_ONLY_MODE = False
    LEGAL_TRACKERS_TAG = ""
    LEGAL_FEED_ONLY_AVAILABLE = False
    DISABLE_WHITELIST = True
    SEARCH_LANGUAGE = "ru"
    print("[CONFIG] Режим: PRIVATE")
else:
    LEGAL_ONLY_MODE = True
    LEGAL_TRACKERS_TAG = "legal"
    LEGAL_FEED_ONLY_AVAILABLE = True
    DISABLE_WHITELIST = False
    SEARCH_LANGUAGE = "en"
    print("[CONFIG] Режим: PUBLIC")

LAZY_RESOLVE = True
USE_WHITELIST = not DISABLE_WHITELIST

LEGAL_JACKETT_INDEXERS = frozenset({
    "internetarchive", "publicdomaintorrents",
    "academictorrents", "legittorrents",
})