"""
CLI для управления вайтлистом (data/whitelist.db).

Использование (из корня проекта):

    # Показать все фильмы
    python -m tools.manage_whitelist list

    # Сколько фильмов
    python -m tools.manage_whitelist count

    # Добавить по kp_id (названия подтянутся с Кинопоиска)
    python -m tools.manage_whitelist add 301

    # Добавить вручную
    python -m tools.manage_whitelist add-raw 301 --ru "Матрица" --en "The Matrix" --year 1999

    # Удалить
    python -m tools.manage_whitelist remove 301

    # Поиск по названию
    python -m tools.manage_whitelist search матрица

    # Пересоздать БД из seed (удалит все изменения!)
    python -m tools.manage_whitelist reset --yes

    # Разрешить все временные kp_id через Кинопоиск
    python -m tools.manage_whitelist resolve
"""

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

import argparse
import asyncio
import sys
from pathlib import Path

import aiohttp

import config
from database.whitelist_db import init_whitelist_db, use_whitelist_connection
from database.whitelist_repo import WhitelistRepository
from services.kp_service import KPService


# ======================================================================
#  КОМАНДЫ
# ======================================================================
def cmd_list(args) -> int:
    """Список всех фильмов."""
    with use_whitelist_connection() as conn:
        cur = conn.execute("""
            SELECT kp_id, title_ru, title_en, year, added_at
            FROM movie_whitelist
            ORDER BY kp_id DESC;
        """)
        rows = cur.fetchall()

    if not rows:
        print("Вайтлист пуст. Запустите reset или добавьте фильмы через add.")
        return 0

    print(f"\nВсего: {len(rows)}")
    print("─" * 90)
    print(f"{'kp_id':>10}  {'RU':<40}  {'YEAR':<6}")
    print("─" * 90)

    pending = 0
    for row in rows:
        kp = row["kp_id"]
        ru = row["title_ru"]
        year = row["year"] or "----"

        marker = "  ⏳" if kp < 0 else ""
        if kp < 0:
            pending += 1
            kp_display = f"[{kp}]"
        else:
            kp_display = str(kp)

        print(f"{kp_display:>10}  {ru[:40]:<40}  {year:<6}{marker}")

    print("─" * 90)
    if pending > 0:
        print(f"⏳ {pending} без kp_id — запустите: "
              f"python -m tools.manage_whitelist resolve")
    print()
    return 0


def cmd_count(args) -> int:
    """Сколько фильмов в БД."""
    total = WhitelistRepository.count()
    pending = len(WhitelistRepository.get_pending_ids())
    print(f"Всего: {total}")
    if pending:
        print(f"Без kp_id: {pending}")
    return 0


def cmd_add(args) -> int:
    """Добавить фильм по kp_id (названия с Кинопоиска)."""
    if not config.KP_API_KEY:
        print("Ошибка: KP_API_KEY не задан в .env — используйте add-raw")
        return 1

    async def _fetch():
        async with aiohttp.ClientSession() as session:
            service = KPService()
            return await service.get_movie_data(session, args.kp_id)

    print(f"Запрос kp_id={args.kp_id} у Кинопоиска...")
    try:
        movie = asyncio.run(_fetch())
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return 1

    title_ru = movie.get("title", "")
    if not title_ru or title_ru.startswith("Фильм "):
        print(f"Кинопоиск не вернул данные для kp_id={args.kp_id}")
        return 1

    added = WhitelistRepository.add_movie(
        kp_id=args.kp_id,
        title_ru=title_ru,
        title_en=movie.get("title_en", ""),
        year=movie.get("year", ""),
    )

    if added:
        print(f"✅ Добавлено: {args.kp_id} — {title_ru} ({movie.get('year', '')})")
        return 0
    print(f"⚠️  Уже есть: kp_id={args.kp_id}")
    return 1


def cmd_add_raw(args) -> int:
    """Добавить фильм вручную (без запроса к Кинопоиску)."""
    if not args.ru:
        print("Ошибка: укажите --ru <название>")
        return 1

    added = WhitelistRepository.add_movie(
        kp_id=args.kp_id,
        title_ru=args.ru,
        title_en=args.en or "",
        year=args.year or "",
    )

    if added:
        print(f"✅ Добавлено: {args.kp_id} — {args.ru}")
        return 0
    print(f"⚠️  Уже есть: kp_id={args.kp_id}")
    return 1


def cmd_remove(args) -> int:
    """Удалить фильм по kp_id."""
    if WhitelistRepository.remove_movie(args.kp_id):
        print(f"✅ Удалено: kp_id={args.kp_id}")
        return 0
    print(f"⚠️  Не найдено: kp_id={args.kp_id}")
    return 1


def cmd_search(args) -> int:
    """Поиск по названию (RU/EN)."""
    ids = WhitelistRepository.search_movies_in_feed(args.query)
    if not ids:
        print(f"Ничего не найдено по запросу: '{args.query}'")
        return 0

    print(f"\nНайдено: {len(ids)}\n")
    for kp_id in ids:
        movie = WhitelistRepository.get_movie(kp_id)
        if movie:
            year = movie["year"] or "----"
            print(f"  {kp_id:>8}  {movie['title_ru']} ({year})")
    print()
    return 0


def cmd_resolve(args) -> int:
    """Разрешить все временные kp_id через Кинопоиск."""
    if not config.KP_API_KEY:
        print("Ошибка: KP_API_KEY не задан в .env")
        return 1

    pending = WhitelistRepository.get_pending_ids()
    if not pending:
        print("Все записи уже имеют реальный kp_id.")
        return 0

    print(f"Записей без kp_id: {len(pending)}")
    print("Поиск на Кинопоиске может занять несколько минут...\n")

    from database.resolve_kp_ids import resolve_all
    resolved, not_found = asyncio.run(resolve_all())

    print(f"\n✅ Разрешено: {resolved}")
    if not_found:
        print(f"⚠️  Не найдено: {not_found}")
    return 0


def cmd_reset(args) -> int:
    """Удалить whitelist.db и пересоздать из seed."""
    if not args.yes:
        print("Это удалит все добавленные/изменённые фильмы.")
        print("Подтвердите: --yes")
        return 1

    db_path = Path(config.WHITELIST_DB_PATH)
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")

    removed = []
    for path in (db_path, wal_path, shm_path):
        if path.exists():
            try:
                path.unlink()
                removed.append(path.name)
            except Exception as e:
                print(f"Ошибка удаления {path.name}: {e}")
                return 1

    if removed:
        print(f"Удалено: {', '.join(removed)}")

    init_whitelist_db()
    print(f"✅ whitelist.db пересоздан: {WhitelistRepository.count()} фильмов")
    return 0


# ======================================================================
#  CLI
# ======================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Управление вайтлистом Amagi-Player (data/whitelist.db)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Показать все фильмы")
    p_list.set_defaults(func=cmd_list)

    p_count = sub.add_parser("count", help="Сколько фильмов в БД")
    p_count.set_defaults(func=cmd_count)

    p_add = sub.add_parser("add", help="Добавить по kp_id (названия с КП)")
    p_add.add_argument("kp_id", type=int)
    p_add.set_defaults(func=cmd_add)

    p_raw = sub.add_parser("add-raw", help="Добавить вручную")
    p_raw.add_argument("kp_id", type=int)
    p_raw.add_argument("--ru", required=True, help="Русское название")
    p_raw.add_argument("--en", default="", help="Английское название")
    p_raw.add_argument("--year", default="", help="Год")
    p_raw.set_defaults(func=cmd_add_raw)

    p_rm = sub.add_parser("remove", help="Удалить по kp_id")
    p_rm.add_argument("kp_id", type=int)
    p_rm.set_defaults(func=cmd_remove)

    p_search = sub.add_parser("search", help="Поиск по названию")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_resolve = sub.add_parser("resolve", help="Разрешить kp_id через КП")
    p_resolve.set_defaults(func=cmd_resolve)

    p_reset = sub.add_parser("reset", help="Пересоздать БД из seed")
    p_reset.add_argument("--yes", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()

    init_whitelist_db()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
