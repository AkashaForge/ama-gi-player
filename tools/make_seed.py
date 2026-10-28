#!/usr/bin/env python3
"""
Создаёт whitelist_seed.db + data/seed_posters/.

Список фильмов берётся из database/whitelist_seed.py (SEED_MOVIES).
WIKIPEDIA_PAGES оттуда же — для загрузки постеров.

Стратегия:
  1. Wikidata SPARQL (batch) → kp_id
  2. Wikipedia REST → постер
  3. archive.org → archive_identifier
  4. Pseudo-id если нет kp_id

Использование:
  python tools/make_seed.py --rebuild --concurrency 5
  python tools/make_seed.py --rebuild --concurrency 5 --allow-kp
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
import hashlib
import shutil
import sys
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED_DB = DATA / "whitelist_seed.db"
SEED_POSTERS = DATA / "seed_posters"

sys.path.insert(0, str(ROOT))

import config
from core.logging_setup import get_logger, setup_logging
from database.whitelist_seed import SEED_MOVIES, WIKIPEDIA_PAGES

setup_logging()
log = get_logger("make_seed")


def pseudo_kp_id(title_en: str, year: str) -> int:
    h = hashlib.sha1(f"{title_en}|{year}".encode()).hexdigest()
    n = int(h[:8], 16) % 100_000_000
    return -max(1, n)


class KPClient:
    BASE = "https://kinopoiskapiunofficial.tech"
    MIN_INTERVAL = 1.5
    TIMEOUT = 10

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = None
        self.last_request = 0.0
        self.used = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def search(self, query):
        async with self._lock:
            elapsed = time.time() - self.last_request
            if elapsed < self.MIN_INTERVAL:
                await asyncio.sleep(self.MIN_INTERVAL - elapsed)
            headers = {"X-API-KEY": self.api_key, "Accept": "application/json"}
            try:
                async with self.session.get(
                    f"{self.BASE}/api/v2.1/films/search-by-keyword",
                    headers=headers,
                    params={"keyword": query, "page": 1},
                ) as resp:
                    self.last_request = time.time()
                    if resp.status == 429:
                        return []
                    if resp.status != 200:
                        return []
                    self.used += 1
                    data = await resp.json()
                    return data.get("films") or []
            except Exception as e:
                log.info("KP: %s (%s)", type(e).__name__, e)
                return []


async def wikidata_batch(session, wiki_titles):
    """Wikidata SPARQL батчами по 50 (лимит на размер запроса)."""
    if not wiki_titles:
        return {}

    BATCH = 50
    out = {}

    for start in range(0, len(wiki_titles), BATCH):
        batch = wiki_titles[start:start + BATCH]
        log.info("Wikidata: батч %d-%d из %d",
                 start + 1, start + len(batch), len(wiki_titles))

        values = " ".join(f'"{t}"@en' for t in batch)
        query = f"""
SELECT ?wikiTitle ?kpId WHERE {{
  VALUES ?wikiTitle {{ {values} }}
  ?article schema:about ?item ;
           schema:isPartOf <https://en.wikipedia.org/> ;
           schema:name ?wikiTitle .
  OPTIONAL {{ ?item wdt:P2603 ?kpId . }}
}}
"""
        try:
            async with session.get(
                "https://query.wikidata.org/sparql",
                params={"query": query, "format": "json"},
                headers={"User-Agent": "Amagi-Player/2.0",
                         "Accept": "application/sparql-results+json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    log.warning("Wikidata batch %d: HTTP %d",
                                start, resp.status)
                    continue
                data = await resp.json()
        except Exception as e:
            log.warning("Wikidata batch %d: %s (%s)",
                        start, type(e).__name__, e)
            continue

        for b in (data.get("results") or {}).get("bindings") or []:
            t = b.get("wikiTitle", {}).get("value", "")
            if t and b.get("kpId"):
                try:
                    out[t] = int(b["kpId"]["value"])
                except (ValueError, TypeError):
                    pass

        await asyncio.sleep(0.5)   # вежливость к Wikidata

    log.info("Wikidata: итого %d kp_id из %d titles",
             len(out), len(wiki_titles))
    return out
async def wikipedia_poster(session, page_title):
    try:
        async with session.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "titles": page_title,
                "prop": "pageimages", "pithumbsize": "400",
                "format": "json", "redirects": "1",
            },
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None
    for pid, page in ((data.get("query") or {}).get("pages") or {}).items():
        if str(pid) == "-1":
            continue
        thumb = (page.get("thumbnail") or {}).get("source", "")
        if thumb:
            return thumb
    return None
async def archive_thumbnail(session, identifier, cache_path):
    """https://archive.org/services/img/{id} — thumbnail из IA. Не API, без лимита."""
    if not identifier:
        return False
    url = f"https://archive.org/services/img/{identifier}"
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=12)
        ) as resp:
            if resp.status != 200:
                return False
            content = await resp.read()
        if len(content) < 2000:   # placeholder IA, не реальный постер
            return False
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(content)
        return True
    except Exception:
        return False

async def archive_org_identifier(session, title_en, year):
    try:
        async with session.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f'title:("{title_en}") AND mediatype:(movies)',
                "fl[]": ["identifier", "title", "year", "language",
                          "downloads"],
                "sort[]": "downloads desc",
                "rows": "10",
                "output": "json",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None

    docs = (data.get("response") or {}).get("docs") or []
    for doc in docs:
        lang = doc.get("language") or ""
        if isinstance(lang, list):
            lang = ", ".join(str(x) for x in lang)
        lang_low = str(lang).lower()
        if lang_low and any(x in lang_low for x in (
            "chinese", "chi", "japanese", "jpn", "korean", "kor",
            "polish", "pol", "czech", "cze", "hungarian", "hun",
            "arabic", "ara", "hindi", "hin",
        )):
            continue
        doc_year = doc.get("year")
        if isinstance(doc_year, list):
            doc_year = doc_year[0] if doc_year else ""
        if year and doc_year and str(doc_year) != str(year):
            continue
        return doc.get("identifier")
    return None


async def download_poster(session, url, path):
    if not url:
        return False
    if path.exists() and path.stat().st_size > 1000:
        return True
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=12)
        ) as resp:
            if resp.status != 200:
                return False
            content = await resp.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return True
    except Exception:
        return False


def init_db():
    import sqlite3
    DATA.mkdir(parents=True, exist_ok=True)
    if SEED_DB.exists():
        SEED_DB.unlink()
    for s in ("-wal", "-shm"):
        p = Path(str(SEED_DB) + s)
        if p.exists():
            p.unlink()
    conn = sqlite3.connect(str(SEED_DB))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE movie_whitelist (
            kp_id INTEGER PRIMARY KEY,
            title_ru TEXT NOT NULL,
            title_en TEXT DEFAULT '',
            year TEXT DEFAULT '',
            archive_identifier TEXT DEFAULT '',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            available INTEGER DEFAULT 1
        );
        CREATE INDEX idx_avail ON movie_whitelist(available);
    """)
    conn.commit()
    conn.close()


def add_movie(kp_id, title_ru, title_en, year, archive_id, available=1):
    import sqlite3
    conn = sqlite3.connect(str(SEED_DB))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO movie_whitelist "
            "(kp_id, title_ru, title_en, year, archive_identifier, "
            "available) VALUES (?, ?, ?, ?, ?, ?);",
            (kp_id, title_ru, title_en, year, archive_id, available),
        )
        conn.commit()
    finally:
        conn.close()


async def process_film(
    http, kp, sem, idx, total,
    title_en, title_ru, year, wiki,
    wd_map, stats, allow_kp,
):
    async with sem:
        try:
            await asyncio.wait_for(
                _process_film_inner(
                    http, kp, idx, total,
                    title_en, title_ru, year, wiki,
                    wd_map, stats, allow_kp,
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            log.error("[%d/%d] '%s' TIMEOUT", idx, total, title_en)
            stats["fail"] += 1


async def _process_film_inner(
    http, kp, idx, total,
    title_en, title_ru, year, wiki,
    wd_map, stats, allow_kp,
):
    log.info("[%d/%d] %s (%s)", idx, total, title_en, year)

    kp_id = None
    poster_url = ""
    archive_id = ""
    source = ""

    # 1. kp_id из Wikidata
    if wiki and wiki in wd_map:
        kp_id = wd_map[wiki]
        stats["wd"] += 1
        log.info("  kp_id=%d (Wikidata)", kp_id)

    # 2. Постер из Wikipedia
    if wiki:
        purl = await wikipedia_poster(http, wiki)
        if purl:
            poster_url = purl
            source = "Wikipedia"
            log.info("  постер: Wikipedia")

    # 3. Archive.org identifier
    archive_id = await archive_org_identifier(http, title_en, year)
    if archive_id:
        stats["archive"] += 1
        log.info("  IA: %s", archive_id)
    else:
        log.info("  IA: не найден")

    # 4. kp_id pseudo если нет
    if not kp_id:
        kp_id = pseudo_kp_id(title_en, year)
        stats["pseudo"] += 1
        log.info("  kp_id=%d (pseudo)", kp_id)

    # 5. КАСКАД ПОСТЕРОВ: Wikipedia URL → IA thumbnail → KP
    poster_path = SEED_POSTERS / f"{kp_id}.jpg"
    poster_ok = False

    # 5a. Если Wikipedia дал URL — качаем
    if poster_url:
        poster_ok = await download_poster(http, poster_url, poster_path)
        if poster_ok:
            stats["poster"] += 1

    # 5b. Fallback: IA thumbnail
    if not poster_ok and archive_id:
        poster_ok = await archive_thumbnail(http, archive_id, poster_path)
        if poster_ok:
            stats["poster"] += 1
            source = "IA"

    # 5c. Fallback: KP (только если --allow-kp)
    if not poster_ok and allow_kp and kp:
        films = await kp.search(f"{title_en} {year}")
        if films:
            best = next(
                (f for f in films if str(f.get("year", "")) == year),
                films[0],
            )
            kp_url = (
                best.get("posterUrlPreview")
                or best.get("posterUrl") or ""
            )
            if kp_url:
                poster_ok = await download_poster(
                    http, kp_url, poster_path
                )
                if poster_ok:
                    stats["poster"] += 1
                    source = "KP"
            stats["kp"] += 1

    # 6. В БД
    add_movie(kp_id, title_ru, title_en, year, archive_id or "", 1)
    log.info("  ✓ kp_id=%d, IA=%s, poster=%s",
             kp_id, archive_id or "-", source or "нет")
async def make_seed(api_key, dry_run=False, concurrency=5, allow_kp=False):
    total = len(SEED_MOVIES)
    log.info("=" * 70)
    log.info("Фильмов (из whitelist_seed.py): %d", total)
    log.info("concurrency=%d, allow_kp=%s", concurrency, allow_kp)

    if dry_run:
        for i, (kp_id, ru, en, year) in enumerate(SEED_MOVIES, 1):
            log.info("  %2d. %-45s (%s)", i, en, year)
        return 0

    init_db()
    stats = {"wd": 0, "poster": 0, "archive": 0,
             "kp": 0, "pseudo": 0, "fail": 0}

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        kp = None
        if allow_kp and api_key:
            kp = KPClient(api_key)
            await kp.__aenter__()
            if not await kp.search("matrix"):
                await kp.__aexit__()
                kp = None

        try:
            # Собираем все wiki-titles из WIKIPEDIA_PAGES
            wiki_titles = []
            for kp_id, ru, en, year in SEED_MOVIES:
                wiki = WIKIPEDIA_PAGES.get(en, en)
                if wiki:
                    wiki_titles.append(wiki)

            log.info("=" * 70)
            log.info("Wikidata SPARQL batch...")
            wd_map = await wikidata_batch(http, wiki_titles)
            log.info("=" * 70)

            sem = asyncio.Semaphore(concurrency)
            tasks = []
            for i, (kp_id, ru, en, year) in enumerate(SEED_MOVIES, 1):
                wiki = WIKIPEDIA_PAGES.get(en, en)
                tasks.append(process_film(
                    http, kp, sem, i, total,
                    en, ru, year, wiki,
                    wd_map, stats, allow_kp,
                ))
            await asyncio.gather(*tasks)
        finally:
            if kp:
                await kp.__aexit__()

    log.info("=" * 70)
    log.info("ИТОГ:")
    log.info("  kp_id Wikidata: %d", stats["wd"])
    log.info("  kp_id pseudo:   %d", stats["pseudo"])
    log.info("  Постеры:        %d", stats["poster"])
    log.info("  archive_id:     %d", stats["archive"])
    log.info("  KP fallback:    %d", stats["kp"])
    log.info("  Не удалось:     %d", stats["fail"])

    import sqlite3
    if SEED_DB.exists():
        conn = sqlite3.connect(str(SEED_DB))
        t = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist"
        ).fetchone()[0]
        with_ia = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist "
            "WHERE archive_identifier != ''"
        ).fetchone()[0]
        conn.close()
        log.info("  Seed: %s (%d фильмов, %d с IA)", SEED_DB, t, with_ia)
    log.info("=" * 70)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--allow-kp", action="store_true")
    args = parser.parse_args()

    api_key = getattr(config, "KP_API_KEY", "") or ""

    if args.rebuild:
        if SEED_DB.exists():
            SEED_DB.unlink()
        for s in ("-wal", "-shm"):
            p = Path(str(SEED_DB) + s)
            if p.exists():
                p.unlink()
        if SEED_POSTERS.exists():
            shutil.rmtree(SEED_POSTERS, ignore_errors=True)
        log.info("Старый seed удалён")

    asyncio.run(make_seed(
        api_key, dry_run=args.dry_run,
        concurrency=args.concurrency,
        allow_kp=args.allow_kp,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
