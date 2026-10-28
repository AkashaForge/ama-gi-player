"""
Параллельное разрешение kp_id. Concurrency=3 (лимит KP API ~5 req/sec),
retry с exponential backoff при 429.
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

import asyncio
import sys

import aiohttp

import config
from database.whitelist_db import init_whitelist_db
from database.whitelist_repo import WhitelistRepository
from services.kp_service import KPService

_CONCURRENCY = 3
_MAX_RETRIES = 3
_BACKOFF_BASE = 3.0  # секунды: 3 → 9 → 27


async def _search_with_retry(service: KPService, session, query: str):
    """
    Поиск с retry на 429. Возвращает список или None.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            url = (
                f"{service.base_url}/api/v2.1/films/search-by-keyword"
                f"?keyword={query}&page=1"
            )
            # URL-encode query через quote_plus, чтобы кириллица работала
            from urllib.parse import quote_plus
            url = (
                f"{service.base_url}/api/v2.1/films/search-by-keyword"
                f"?keyword={quote_plus(query)}&page=1"
            )
            async with session.get(
                url, headers=service.headers, timeout=timeout
            ) as resp:
                if resp.status == 429:
                    wait = _BACKOFF_BASE * (3 ** attempt)
                    print(f"  429 → ждём {wait:.0f}s (попытка {attempt+1}/{_MAX_RETRIES})")
                    await asyncio.sleep(wait)
                    continue
                if resp.status != 200:
                    return None
                try:
                    return await resp.json()
                except Exception:
                    return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"  Ошибка запроса: {e}")
            return None
    return None


async def _resolve_one(session, service: KPService, item: dict) -> tuple:
    old_id = item["kp_id"]
    title_en = item["title_en"]
    year = item["year"]

    query = f"{title_en} {year}".strip()
    data = await _search_with_retry(service, session, query)

    if not data:
        return (old_id, 0, title_en, "API")

    films = data.get("films") or []
    for movie in films:
        if str(movie.get("year", "")) == str(year):
            return (old_id, movie.get("kinopoiskId") or movie.get("filmId") or 0,
                    title_en, "OK")

    if films:
        return (old_id, films[0].get("kinopoiskId") or films[0].get("filmId") or 0,
                title_en, "OK-first")

    return (old_id, 0, title_en, "not-found")


async def resolve_all() -> tuple[int, int]:
    if not config.KP_API_KEY:
        print("Ошибка: KP_API_KEY не задан в .env")
        return 0, 0

    pending = WhitelistRepository.get_pending_ids()
    if not pending:
        print("Все записи уже имеют реальный kp_id.")
        return 0, 0

    print(f"Разрешение kp_id: {len(pending)} записей, "
          f"{_CONCURRENCY} параллельно (лимит KP API)")
    print("При 429 — retry с backoff (3/9/27 сек)\n")

    sem = asyncio.Semaphore(_CONCURRENCY)
    resolved = 0
    not_found = 0
    api_failed = 0
    done = 0

    async def worker(item):
        nonlocal resolved, not_found, api_failed, done
        async with sem:
            old_id, new_id, title, status = await _resolve_one(
                session, service, item
            )
            done += 1

            if status == "API":
                api_failed += 1
                print(f"[{done}/{len(pending)}] ⚠️  {title} — API error (оставлен)")
            elif new_id and new_id > 0:
                WhitelistRepository.update_kp_id(old_id, new_id)
                resolved += 1
                print(f"[{done}/{len(pending)}] ✅ {title} → kp_id={new_id}")
            else:
                not_found += 1
                print(f"[{done}/{len(pending)}] ❌ {title} — не найден")

            # Небольшая пауза между запросами в рамках concurrency
            await asyncio.sleep(0.2)

    async with aiohttp.ClientSession() as session:
        service = KPService()
        tasks = [worker(item) for item in pending]
        await asyncio.gather(*tasks, return_exceptions=True)

    print(f"\nИтог: разрешено={resolved}, не найдено={not_found}, "
          f"API failed={api_failed}")
    if api_failed > 0:
        print(f"⚠️  {api_failed} записей остались с kp_id<0. "
              f"Запустите ещё раз: python -m database.resolve_kp_ids")
    return resolved, not_found


def main() -> int:
    init_whitelist_db()
    asyncio.run(resolve_all())
    return 0


if __name__ == "__main__":
    sys.exit(main())
