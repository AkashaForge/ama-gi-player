"""Репозиторий для whitelist.db."""

import config
from core.logging_setup import get_logger
from database.whitelist_db import use_whitelist_connection

log = get_logger("whitelist_repo")


class WhitelistRepository:

    @staticmethod
    def count() -> int:
        with use_whitelist_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM movie_whitelist;"
            ).fetchone()["c"]

    @staticmethod
    def count_available() -> int:
        with use_whitelist_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM movie_whitelist WHERE available = 1;"
            ).fetchone()["c"]

    @staticmethod
    def count_unavailable() -> int:
        with use_whitelist_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM movie_whitelist WHERE available = 0;"
            ).fetchone()["c"]

    @staticmethod
    def count_unverified() -> int:
        with use_whitelist_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM movie_whitelist "
                "WHERE available IS NULL;"
            ).fetchone()["c"]

    @staticmethod
    def search_movies_in_feed(
        query: str = "", limit: int = 20, offset: int = 0,
    ) -> list[int]:
        q = (query or "").strip()
        legal_only = getattr(config, "LEGAL_ONLY_MODE", True)

        if legal_only:
            ids = WhitelistRepository._query_ids(
                where="available = 1", query=q,
                limit=limit, offset=offset,
            )
            if ids:
                return ids
            if offset == 0:
                log.warning(
                    "search_movies_in_feed: 0 verified. Fallback на "
                    "available IS NULL."
                )

        return WhitelistRepository._query_ids(
            where="(available = 1 OR available IS NULL)",
            query=q, limit=limit, offset=offset,
        )
    @staticmethod
    def _query_ids(where: str, query: str, limit: int, offset: int) -> list[int]:
        q = (query or "").strip()
        with use_whitelist_connection() as conn:
            if q:
                # PYNORM — зарегистрирован в whitelist_db._connect()
                # корректно обрабатывает кириллицу (SQLite LOWER() не умеет)
                sql = f"""
                    SELECT kp_id FROM movie_whitelist
                    WHERE {where}
                      AND (
                          PYNORM(title_ru) LIKE ?
                          OR PYNORM(title_en) LIKE ?
                          OR year LIKE ?
                      )
                    ORDER BY kp_id DESC
                    LIMIT ? OFFSET ?;
                """
                qn = q.lower().replace("ё", "е")
                params = (f"%{qn}%", f"%{qn}%", f"%{q}%", limit, offset)
            else:
                sql = f"""
                    SELECT kp_id FROM movie_whitelist
                    WHERE {where}
                    ORDER BY kp_id DESC
                    LIMIT ? OFFSET ?;
                """
                params = (limit, offset)
            return [row["kp_id"] for row in conn.execute(sql, params).fetchall()]


    @staticmethod
    def count_in_feed(query: str = "") -> int:
        """Кол-во результатов поиска (для отображения 'ничего не найдено')."""
        q = (query or "").strip()
        legal_only = getattr(config, "LEGAL_ONLY_MODE", True)

        def _count(where: str) -> int:
            with use_whitelist_connection() as conn:
                if q:
                    sql = f"""
                        SELECT COUNT(*) AS c FROM movie_whitelist
                        WHERE {where}
                          AND (
                              PYNORM(title_ru) LIKE ?
                              OR PYNORM(title_en) LIKE ?
                              OR year LIKE ?
                          );
                    """
                    qn = q.lower().replace("ё", "е")
                    params = (f"%{qn}%", f"%{qn}%", f"%{q}%")
                else:
                    sql = f"""
                        SELECT COUNT(*) AS c FROM movie_whitelist
                        WHERE {where};
                    """
                    params = ()
                return conn.execute(sql, params).fetchone()["c"]

        if legal_only:
            n = _count("available = 1")
            if n > 0:
                return n
        return _count("(available = 1 OR available IS NULL)")
    @staticmethod
    def get_movie(kp_id: int) -> dict | None:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "SELECT kp_id, title_ru, title_en, year, "
                "archive_identifier, added_at, available "
                "FROM movie_whitelist WHERE kp_id = ?;",
                (kp_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_archive_identifier(kp_id: int) -> str:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "SELECT archive_identifier FROM movie_whitelist "
                "WHERE kp_id = ?;",
                (kp_id,),
            )
            row = cur.fetchone()
            return (row["archive_identifier"] or "") if row else ""

    @staticmethod
    def list_all(limit: int = 1000) -> list[dict]:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "SELECT kp_id, title_ru, title_en, year, "
                "archive_identifier, added_at, available "
                "FROM movie_whitelist ORDER BY kp_id DESC LIMIT ?;",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def add_movie(kp_id: int, title_ru: str, title_en: str = "",
                  year: str = "", archive_identifier: str = "") -> bool:
        try:
            with use_whitelist_connection() as conn:
                conn.execute(
                    "INSERT INTO movie_whitelist "
                    "(kp_id, title_ru, title_en, year, "
                    "archive_identifier, available) "
                    "VALUES (?, ?, ?, ?, ?, NULL);",
                    (kp_id, title_ru, title_en, year, archive_identifier),
                )
            return True
        except Exception as e:
            if "UNIQUE" in str(e) or "PRIMARY" in str(e):
                return False
            log.warning("add_movie kp_id=%d: %s", kp_id, e)
            return False

    @staticmethod
    def remove_movie(kp_id: int) -> bool:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "DELETE FROM movie_whitelist WHERE kp_id = ?;", (kp_id,)
            )
            return cur.rowcount > 0

    @staticmethod
    def update_kp_id(old_kp_id: int, new_kp_id: int) -> bool:
        if old_kp_id == new_kp_id:
            return False
        try:
            with use_whitelist_connection() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM movie_whitelist WHERE kp_id = ?;",
                    (new_kp_id,),
                )
                if cur.fetchone() is not None:
                    conn.execute(
                        "DELETE FROM movie_whitelist WHERE kp_id = ?;",
                        (old_kp_id,),
                    )
                else:
                    conn.execute(
                        "UPDATE movie_whitelist SET kp_id = ? "
                        "WHERE kp_id = ?;",
                        (new_kp_id, old_kp_id),
                    )
            return True
        except Exception as e:
            log.warning("update_kp_id: %s", e)
            return False

    @staticmethod
    def update_archive_identifier(kp_id: int, archive_id: str) -> bool:
        try:
            with use_whitelist_connection() as conn:
                cur = conn.execute(
                    "UPDATE movie_whitelist SET archive_identifier = ? "
                    "WHERE kp_id = ?;",
                    (archive_id, kp_id),
                )
                return cur.rowcount > 0
        except Exception as e:
            log.warning("update_archive_identifier: %s", e)
            return False

    @staticmethod
    def get_pending_ids() -> list[dict]:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "SELECT kp_id, title_ru, title_en, year "
                "FROM movie_whitelist WHERE kp_id < 0 ORDER BY kp_id DESC;"
            )
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_unverified() -> list[dict]:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "SELECT kp_id, title_ru, title_en, year "
                "FROM movie_whitelist WHERE available IS NULL "
                "ORDER BY kp_id DESC;"
            )
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def reset_verification() -> int:
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "UPDATE movie_whitelist SET available = NULL;"
            )
            return cur.rowcount

    @staticmethod
    def mark_available(kp_id: int) -> None:
        with use_whitelist_connection() as conn:
            conn.execute(
                "UPDATE movie_whitelist SET available = 1 WHERE kp_id = ?;",
                (kp_id,),
            )

    @staticmethod
    def mark_unavailable(kp_id: int) -> None:
        with use_whitelist_connection() as conn:
            conn.execute(
                "UPDATE movie_whitelist SET available = 0 WHERE kp_id = ?;",
                (kp_id,),
            )

    @staticmethod
    def find_by_title(query: str, limit: int = 20) -> list[dict]:
        q = (query or "").strip()
        if not q:
            return []
        with use_whitelist_connection() as conn:
            cur = conn.execute(
                "SELECT kp_id, title_ru, title_en, year, available "
                "FROM movie_whitelist "
                "WHERE title_ru LIKE ? OR title_en LIKE ? "
                "ORDER BY kp_id DESC LIMIT ?;",
                (f"%{q}%", f"%{q}%", limit),
            )
            return [dict(row) for row in cur.fetchall()]
