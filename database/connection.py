"""Подключение к app_data.db (только история)."""

import contextlib
import sqlite3
from pathlib import Path

import config

_SCHEMA_VERSION = 1


def get_connection() -> sqlite3.Connection:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    return conn


@contextlib.contextmanager
def use_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Инициализирует app_data.db: только user_history + schema_version."""
    with use_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_history (
                kp_id INTEGER PRIMARY KEY,
                movie_title TEXT NOT NULL,
                current_seconds INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_updated
                ON user_history(updated_at DESC);
        """)

        try:
            cur.execute("SELECT version FROM schema_version LIMIT 1;")
            row = cur.fetchone()
            version = row["version"] if row else 0
        except sqlite3.OperationalError:
            version = 0

        if version < _SCHEMA_VERSION:
            cur.execute(
                "INSERT INTO schema_version (version) VALUES (?);",
                (_SCHEMA_VERSION,),
            )

    print("[DB] app_data.db инициализирована (WAL, user_history)")
