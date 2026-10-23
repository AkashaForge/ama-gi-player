"""Инициализация whitelist.db + connection-менеджер."""

import os
import sqlite3
from contextlib import contextmanager

import config
from core.logging_setup import get_logger

log = get_logger("whitelist_db")
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS movie_whitelist (
    kp_id INTEGER PRIMARY KEY,
    title_ru TEXT NOT NULL,
    title_en TEXT DEFAULT '',
    year TEXT DEFAULT '',
    archive_identifier TEXT DEFAULT '',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    available INTEGER DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_whitelist_available
    ON movie_whitelist(available);
CREATE INDEX IF NOT EXISTS idx_whitelist_title_ru
    ON movie_whitelist(title_ru);
CREATE INDEX IF NOT EXISTS idx_whitelist_title_en
    ON movie_whitelist(title_en);
"""


def _pynorm(value) -> str:
    """
    SQLite LOWER() не работает для кириллицы — регистронезависимый
    поиск невозможен через встроенные функции.
    PYNORM регистрируется через create_function и делает:
      - корректный .lower() через Python (все Unicode)
      - замену ё → е (нормализация для поиска)
    """
    if not isinstance(value, str):
        return ""
    return value.lower().replace("ё", "е")


def _connect() -> sqlite3.Connection:
    db_path = str(config.WHITELIST_DB_PATH)
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    # Регистрируем PYNORM — используется в LIKE-запросах
    conn.create_function("PYNORM", 1, _pynorm)
    return conn


@contextmanager
def use_whitelist_connection():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_whitelist_db() -> None:
    global _initialized
    if _initialized:
        return

    with use_whitelist_connection() as conn:
        cur = conn.execute("PRAGMA table_info(movie_whitelist);")
        cols = {row["name"] for row in cur.fetchall()}
        if cols and "archive_identifier" not in cols:
            try:
                conn.execute(
                    "ALTER TABLE movie_whitelist "
                    "ADD COLUMN archive_identifier TEXT DEFAULT '';"
                )
                log.info("Migration: added archive_identifier column")
            except Exception as e:
                log.warning("Migration archive_identifier: %s", e)

        conn.executescript(SCHEMA)

        cur = conn.execute("SELECT COUNT(*) AS c FROM movie_whitelist;")
        total = cur.fetchone()["c"]
        cur = conn.execute(
            "SELECT COUNT(*) AS c FROM movie_whitelist WHERE available = 1;"
        )
        available = cur.fetchone()["c"]
        cur = conn.execute(
            "SELECT COUNT(*) AS c FROM movie_whitelist "
            "WHERE archive_identifier != '';"
        )
        with_ia = cur.fetchone()["c"]

    print(
        f"[WHITELIST-DB] whitelist.db: {total} всего, "
        f"{available} доступны, {with_ia} с IA"
    )
    _initialized = True
