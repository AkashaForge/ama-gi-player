"""Единая настройка logging."""
import logging
import sys
from logging.handlers import RotatingFileHandler

_CONFIGURED = False

_CONSOLE_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)-20s | %(message)s"
_FILE_FORMAT = ("%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s "
                "[%(threadName)s] %(filename)s:%(lineno)d | %(message)s")
_DATE_FORMAT = "%H:%M:%S"
_FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    try:
        import config
        log_file = getattr(config, "LOG_FILE", None)
        console_level = getattr(config, "LOG_LEVEL_CONSOLE", "INFO")
        file_level = getattr(config, "LOG_LEVEL_FILE", "DEBUG")
        log_max_bytes = getattr(config, "LOG_MAX_BYTES", 10 * 1024 * 1024)
        log_backup_count = getattr(config, "LOG_BACKUP_COUNT", 3)
        debug_modules = getattr(config, "LOG_DEBUG_MODULES", [])
    except Exception:
        log_file = None
        console_level = "INFO"
        file_level = "DEBUG"
        log_max_bytes = 10 * 1024 * 1024
        log_backup_count = 3
        debug_modules = []

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(getattr(logging, console_level, logging.INFO))
    ch.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(ch)

    if log_file:
        try:
            fh = RotatingFileHandler(str(log_file), maxBytes=log_max_bytes,
                                      backupCount=log_backup_count,
                                      encoding="utf-8")
            fh.setLevel(getattr(logging, file_level, logging.DEBUG))
            fh.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_FILE_DATE_FORMAT))
            root.addHandler(fh)
        except Exception as e:
            print(f"[LOGGING] {log_file}: {e}")

    for noisy in ("aiohttp.access", "aiohttp.client", "aiohttp.connector",
                   "asyncio", "nodriver", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    for mod in debug_modules:
        try:
            logging.getLogger(mod).setLevel(logging.DEBUG)
        except Exception:
            pass
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)