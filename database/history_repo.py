"""Репозиторий истории просмотров."""

# Amagi-Player — desktop media player for public-domain content
# Copyright (C) 2026 AkashaForge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
