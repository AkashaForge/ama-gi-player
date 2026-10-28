"""
Верификация вайтлиста на доступность в Internet Archive.
Concurrency=3, retry на сетевые ошибки.
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

from database.whitelist_db import init_whitelist_db
from database.whitelist_repo import WhitelistRepository
from search.archive_org_searcher import ArchiveOrgSearcher

_CONCURRENCY = 3
_MAX_RETRIES = 2


async def _check_archive_org(archive_org: ArchiveOrgSearcher,
                              title_en: str, title_ru: str,
                              year: str) -> bool:
    query = title_en or title_ru
    if not query:
        return False

    for attempt in range(_MAX_RETRIES):
        try:
            results = await archive_org.search(query, year)
            return len(results) > 0
        except Exception:
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(2.0)
                continue
            return False
    return False


async def verify_all(reset: bool = False, do_resolve: bool = False) -> None:
    # 1) Resolve
    if do_resolve:
        from database.resolve_kp_ids import resolve_all
        pending = WhitelistRepository.get_pending_ids()
        if pending:
            print(f"\n=== Разрешение kp_id ({len(pending)}) ===")
            await resolve_all()
        else:
            print("\nВсе kp_id уже реальные.")

    # 2) Reset
    if reset:
        n = WhitelistRepository.reset_verification()
        print(f"\nСброшено: {n} записей → available=NULL")

    # 3) Verify
    pending = WhitelistRepository.get_unverified()
    if not pending:
        print("\nВсе записи уже верифицированы.")
        print(f"  Доступно:    {WhitelistRepository.count_available()}")
        print(f"  Недоступно:  {WhitelistRepository.count_unavailable()}")
        return

    print(f"\n=== Верификация ({len(pending)}), {_CONCURRENCY} параллельно ===\n")

    archive_org = ArchiveOrgSearcher()
    sem = asyncio.Semaphore(_CONCURRENCY)
    available = 0
    unavailable = 0
    done = 0

    async def worker(item):
        nonlocal available, unavailable, done
        async with sem:
            kp = item["kp_id"]
            title_ru = item.get("title_ru", "")
            title_en = item.get("title_en", "")
            year = item.get("year", "")

            found = await _check_archive_org(
                archive_org, title_en, title_ru, year
            )
            done += 1

            if found:
                WhitelistRepository.mark_available(kp)
                available += 1
                print(f"[{done}/{len(pending)}] ✅ {title_ru} ({year})")
            else:
                WhitelistRepository.mark_unavailable(kp)
                unavailable += 1
                print(f"[{done}/{len(pending)}] ❌ {title_ru} ({year})")

            await asyncio.sleep(0.2)

    try:
        tasks = [worker(item) for item in pending]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await archive_org.close()

    print(f"\nИтог: доступно={available}, недоступно={unavailable}")
    print(f"Всего в БД: {WhitelistRepository.count()}, "
          f"доступно: {WhitelistRepository.count_available()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Сбросить available и проверить заново")
    parser.add_argument("--resolve", action="store_true",
                        help="Сначала разрешить kp_id через Kinopoisk")
    args = parser.parse_args()

    init_whitelist_db()
    asyncio.run(verify_all(reset=args.reset, do_resolve=args.resolve))
    return 0


if __name__ == "__main__":
    sys.exit(main())
