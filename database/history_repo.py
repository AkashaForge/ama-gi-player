"""Репозиторий истории просмотров."""


from database.connection import use_connection


class HistoryRepository:

    @staticmethod
    def save_timestamp(kp_id: int, movie_title: str, current_seconds: int) -> None:
        """Сохраняет МАКСИМАЛЬНЫЙ прогресс — старый не сбрасывается."""
        if current_seconds <= 0:
            return
        with use_connection() as conn:
            conn.execute("""
                INSERT INTO user_history
                    (kp_id, movie_title, current_seconds, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(kp_id) DO UPDATE SET
                    current_seconds = MAX(excluded.current_seconds,
                                          user_history.current_seconds),
                    movie_title = excluded.movie_title,
                    updated_at = CURRENT_TIMESTAMP;
            """, (kp_id, movie_title, current_seconds))

    @staticmethod
    def get_last_session() -> dict | None:
        """Последняя сессия для острова."""
        with use_connection() as conn:
            cur = conn.execute("""
                SELECT kp_id, movie_title, current_seconds
                FROM user_history
                ORDER BY updated_at DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_seconds_for_movie(kp_id: int) -> int:
        """Сохранённый таймкод в секундах."""
        with use_connection() as conn:
            cur = conn.execute(
                "SELECT current_seconds FROM user_history WHERE kp_id = ?;",
                (kp_id,),
            )
            row = cur.fetchone()
            return row["current_seconds"] if row else 0

    @staticmethod
    def clear_history_entry(kp_id: int) -> None:
        """Удаляет запись истории."""
        with use_connection() as conn:
            conn.execute(
                "DELETE FROM user_history WHERE kp_id = ?;", (kp_id,)
            )

    @staticmethod
    def clear_all() -> int:
        """Полная очистка истории. Возвращает число удалённых."""
        with use_connection() as conn:
            cur = conn.execute("DELETE FROM user_history;")
            return cur.rowcount
