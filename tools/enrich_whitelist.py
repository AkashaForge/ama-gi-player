#!/usr/bin/env python3
"""
Обогащение whitelist_seed.db описаниями и качественными постерами.

v2.1.0:
  - --allow-kp: тянет RU-описания и постеры из Kinopoisk API
    (rate-limit: --delay сек между запросами, --pause-secs пауза
    каждые --pause-every запросов; обработка 402/429 с cooldown)
  - --force-posters: перекачивает постеры, даже если файл уже есть
    (исправляет skip-баг: старые thumbnails 180x124 не
    перекачивались, потому что были > 3 KB)
  - приоритет источника постера: KP → IA files → IA thumb
  - приоритет описания: RU из KP → EN из IA
  - не трогает whitelist.db (working copy), только seed

Использование:
  python tools/enrich_whitelist.py --allow-kp --force --force-posters
  python tools/enrich_whitelist.py --allow-kp --force --force-posters \\
      --delay 3.0 --pause-every 20 --pause-secs 40
  python tools/enrich_whitelist.py --dry-run

После завершения:
  python tools/apply_seed.py
  python main.py
"""

import argparse
import asyncio
import html as html_lib
import os
import re
import sqlite3
import sys
import time
import traceback
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
SEED_DB = DATA / "whitelist_seed.db"
SEED_POSTERS = DATA / "seed_posters"

import config
from core.logging_setup import get_logger, setup_logging

setup_logging()
log = get_logger("enrich")

UA = "Amagi-Player/2.0 (enrich; +https://github.com/AkashaForge/ama-gi-player)"
MAX_DESC_LEN = 2000
MIN_POSTER_BYTES = 3000
MIN_FILE_POSTER_BYTES = 10000
MAX_POSTER_BYTES = 5_000_000

_NEW_COLUMNS = [
    ("description",    "TEXT DEFAULT ''"),
    ("description_ru", "TEXT DEFAULT ''"),
    ("poster_source",  "TEXT DEFAULT ''"),
    ("enriched",       "INTEGER DEFAULT 0"),
]


# ======================================================================
#  Утилиты
# ======================================================================
def clean_description(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, list):
        raw = " ".join(str(x) for x in raw if x)
    text = str(raw)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_DESC_LEN:
        cut = text[: MAX_DESC_LEN - 3].rstrip()
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut + "..."
    return text


# ======================================================================
#  Миграция схемы
# ======================================================================
def migrate_schema():
    conn = sqlite3.connect(str(SEED_DB))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("PRAGMA table_info(movie_whitelist);")
        existing = {row["name"] for row in cur.fetchall()}
        added = []
        for col, decl in _NEW_COLUMNS:
            if col not in existing:
                try:
                    conn.execute(
                        f"ALTER TABLE movie_whitelist ADD COLUMN {col} {decl};"
                    )
                    added.append(col)
                except Exception as e:
                    log.warning("ALTER %s: %s", col, e)
        conn.commit()
        if added:
            log.info("Миграция: добавлены колонки %s", ", ".join(added))
        else:
            log.info("Схема актуальна")
    finally:
        conn.close()


def read_rows(force: bool) -> list[dict]:
    conn = sqlite3.connect(str(SEED_DB))
    conn.row_factory = sqlite3.Row
    try:
        where = "" if force else "WHERE (enriched IS NULL OR enriched = 0)"
        cur = conn.execute(
            f"SELECT kp_id, title_ru, title_en, year, archive_identifier, "
            f"description, description_ru, poster_source, enriched "
            f"FROM movie_whitelist {where} ORDER BY kp_id DESC;"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_row(kp_id: int, description=None, description_ru=None,
               poster_source=None, enriched=1):
    fields, params = [], []
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if description_ru is not None:
        fields.append("description_ru = ?")
        params.append(description_ru)
    if poster_source is not None:
        fields.append("poster_source = ?")
        params.append(poster_source)
    if enriched is not None:
        fields.append("enriched = ?")
        params.append(enriched)
    if not fields:
        return
    params.append(kp_id)
    conn = sqlite3.connect(str(SEED_DB))
    try:
        conn.execute(
            f"UPDATE movie_whitelist SET {', '.join(fields)} WHERE kp_id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


# ======================================================================
#  HTTP
# ======================================================================
async def http_get_json(session, url, timeout=15, headers=None, retries=2):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers=headers or {"User-Agent": UA},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (429, 503):
                    await asyncio.sleep(10 * attempt)
                    continue
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            if attempt < retries:
                await asyncio.sleep(3 * attempt)
    return None


async def http_download(session, url, path: Path, force: bool = False) -> bool:
    if not force and path.exists() and path.stat().st_size >= MIN_POSTER_BYTES:
        return True
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"User-Agent": UA},
        ) as resp:
            if resp.status != 200:
                return False
            content = await resp.read()
        if len(content) < MIN_POSTER_BYTES:
            return False
        if len(content) > MAX_POSTER_BYTES:
            log.warning("Постер слишком большой: %.1f MB", len(content) / 1e6)
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return True
    except Exception as e:
        log.debug("Скачивание %s: %s", url, e)
        return False


# ======================================================================
#  IA
# ======================================================================
def _pick_best_poster(files: list) -> str | None:
    """Приоритет по имени (poster/cover/box/front).
    Fallback: самый большой JPG/PNG > 10 KB (без ключевых слов в имени).
    Игнорирует screenshots/samples/frames."""
    candidates = []
    all_large = []
    for f in files:
        name = (f.get("name") or "").lower()
        if not name.endswith((".jpg", ".jpeg", ".png")):
            continue
        size = int(f.get("size") or 0)
        if size < MIN_FILE_POSTER_BYTES:
            continue
        score = 0
        if "poster" in name: score += 100
        if "cover" in name: score += 90
        if "box" in name or "front" in name: score += 80
        if "thumb" in name: score += 30
        if "screenshot" in name or "sample" in name: score -= 200
        if "frame" in name or "still" in name: score -= 150
        candidates.append((score, size, f["name"]))
        all_large.append((size, f["name"]))
    if candidates:
        candidates.sort(reverse=True)
        best_score, _, best_name = candidates[0]
        if best_score > 0:
            return best_name
    if all_large:
        all_large.sort(reverse=True)
        return all_large[0][1]
    return None


async def fetch_ia_metadata(session, archive_id: str):
    """Возвращает (description_en, poster_filename)."""
    if not archive_id:
        return ("", None)
    data = await http_get_json(
        session, f"https://archive.org/metadata/{archive_id}"
    )
    if not data:
        return ("", None)
    meta = data.get("metadata") or {}
    files = data.get("files") or []
    desc = clean_description(meta.get("description"))
    poster = _pick_best_poster(files)
    return (desc, poster)


# ======================================================================
#  KP
# ======================================================================
class KPClient:
    BASE = "https://kinopoiskapiunofficial.tech"

    def __init__(self, api_key, min_interval=2.5):
        self.api_key = api_key
        self.session = None
        self.last = 0.0
        self.min_interval = min_interval
        self.used = 0
        self.calls_402 = 0
        self.calls_429 = 0
        self.cooldown_until = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def _get(self, url, params=None):
        async with self._lock:
            now = time.time()
            if now < self.cooldown_until:
                wait = self.cooldown_until - now
                log.debug("KP cooldown, ждём %.1f сек", wait)
                await asyncio.sleep(wait)
            elapsed = time.time() - self.last
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            headers = {
                "X-API-KEY": self.api_key,
                "Accept": "application/json",
            }
            try:
                async with self.session.get(
                    url, headers=headers, params=params
                ) as resp:
                    self.last = time.time()
                    if resp.status == 402:
                        self.calls_402 += 1
                        log.warning("KP: 402 (дневной лимит). Пауза 5 мин.")
                        self.cooldown_until = time.time() + 300
                        return None
                    if resp.status == 429:
                        self.calls_429 += 1
                        log.warning("KP: 429 (слишком часто). Пауза 60 сек.")
                        self.cooldown_until = time.time() + 60
                        return None
                    if resp.status != 200:
                        return None
                    self.used += 1
                    return await resp.json()
            except Exception as e:
                log.debug("KP HTTP: %s", e)
                return None

    async def get_movie(self, kp_id: int):
        if kp_id <= 0:
            return None
        return await self._get(f"{self.BASE}/api/v2.2/films/{kp_id}")

    async def search_best(self, query: str, year: str):
        """Строгое совпадение по году. Если год не совпал — None."""
        if not query:
            return None
        data = await self._get(
            f"{self.BASE}/api/v2.1/films/search-by-keyword",
            params={"keyword": query, "page": 1},
        )
        films = (data or {}).get("films") or []
        for f in films:
            if str(f.get("year") or "") == str(year):
                return f
        return None


# ======================================================================
#  Обработка одной записи
# ======================================================================
async def enrich_one(session, kp, row, no_descriptions, no_posters,
                     allow_kp, force_posters) -> str:
    kp_id = row["kp_id"]
    archive_id = (row["archive_identifier"] or "").strip()

    desc_en = row["description"] or ""
    desc_ru = row["description_ru"] or ""
    poster_path = SEED_POSTERS / f"{kp_id}.jpg"

    # === 1. KP: RU-описание + KP-постер (приоритет)
    kp_poster_url = None
    if allow_kp and kp and not no_descriptions:
        kp_data = None
        if kp_id > 0:
            kp_data = await kp.get_movie(kp_id)
        else:
            query = (row["title_ru"] or row["title_en"] or "").strip()
            kp_data = await kp.search_best(query, row["year"])
        if kp_data:
            ru = clean_description(kp_data.get("description"))
            if ru:
                desc_ru = ru
            kp_poster_url = (
                kp_data.get("posterUrl")
                or kp_data.get("posterUrlPreview")
                or ""
            )

    # === 2. IA: EN-описание + полноразмерный постер из files
    ia_poster_url = None
    if archive_id:
        d_en, poster_name = await fetch_ia_metadata(session, archive_id)
        if d_en and not desc_en:
            desc_en = d_en
        if poster_name:
            ia_poster_url = (
                f"https://archive.org/download/{archive_id}/{poster_name}"
            )

    # === 3. Скачивание постера: KP → IA files → IA thumb
    poster_ok = (
        not force_posters
        and poster_path.exists()
        and poster_path.stat().st_size >= MIN_FILE_POSTER_BYTES
    )
    source = (row["poster_source"] or "existing") if poster_ok else ""

    if not poster_ok and not no_posters:
        if kp_poster_url:
            if await http_download(session, kp_poster_url, poster_path, force=True):
                source = "KP"
                poster_ok = True
        if not poster_ok and ia_poster_url:
            if await http_download(session, ia_poster_url, poster_path, force=True):
                source = "IA-files"
                poster_ok = True
        if not poster_ok and archive_id:
            thumb_url = f"https://archive.org/services/img/{archive_id}"
            if await http_download(session, thumb_url, poster_path, force=True):
                source = "IA-thumb"
                poster_ok = True
        if not poster_ok and poster_path.exists() and poster_path.stat().st_size >= MIN_FILE_POSTER_BYTES:
            poster_ok = True
            source = row["poster_source"] or "existing"

    if not source:
        source = "none"

    update_row(
        kp_id,
        description=None if no_descriptions else desc_en,
        description_ru=None if no_descriptions else desc_ru,
        poster_source=source if poster_ok else row["poster_source"],
        enriched=1,
    )
    return source


# ======================================================================
#  Главный цикл
# ======================================================================
async def run(args):
    migrate_schema()
    rows = read_rows(force=args.force)
    total = len(rows)
    if total == 0:
        log.info("Нечего обогащать (--force не передан и все enriched=1)")
        return

    SEED_POSTERS.mkdir(parents=True, exist_ok=True)
    log.info("=" * 70)
    log.info("К обогащению: %d фильмов", total)
    log.info("delay=%.1f сек, пауза %.0f сек каждые %d запросов",
             args.delay, args.pause_secs, args.pause_every)
    log.info("allow_kp=%s, force_posters=%s",
             args.allow_kp, args.force_posters)
    log.info("=" * 70)

    stats = {"KP": 0, "IA-files": 0, "IA-thumb": 0,
             "none": 0, "existing": 0, "error": 0}
    start_ts = time.time()

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        kp = None
        if args.allow_kp and getattr(config, "KP_API_KEY", ""):
            kp = KPClient(config.KP_API_KEY, min_interval=args.delay)
            await kp.__aenter__()
            log.info("KP-клиент активен (rate-limit %.1f сек)", args.delay)
        elif args.allow_kp:
            log.warning("--allow-kp передан, но KP_API_KEY не задан в .env")

        try:
            for i, row in enumerate(rows, 1):
                title = row["title_en"] or row["title_ru"]
                log.info("[%d/%d] %s (%s)", i, total, title, row["year"])
                try:
                    source = await enrich_one(
                        session, kp, row,
                        no_descriptions=args.no_descriptions,
                        no_posters=args.no_posters,
                        allow_kp=args.allow_kp,
                        force_posters=args.force_posters,
                    )
                    stats[source if source in stats else "none"] += 1
                except Exception:
                    log.error("Ошибка:")
                    traceback.print_exc()
                    stats["error"] += 1

                if i % args.pause_every == 0 and i < total:
                    log.info("  → пауза %.0f сек", args.pause_secs)
                    await asyncio.sleep(args.pause_secs)
        finally:
            if kp:
                await kp.__aexit__()

    elapsed = time.time() - start_ts
    log.info("=" * 70)
    log.info("ГОТОВО за %.1f мин", elapsed / 60)
    log.info("  KP постеры:       %d", stats["KP"])
    log.info("  IA files постеры: %d", stats["IA-files"])
    log.info("  IA thumb постеры: %d", stats["IA-thumb"])
    log.info("  existing (не перекачивались): %d", stats["existing"])
    log.info("  без постера:      %d", stats["none"])
    log.info("  ошибок:           %d", stats["error"])

    if kp:
        log.info("  KP API calls:     %d (402: %d, 429: %d)",
                 kp.used, kp.calls_402, kp.calls_429)

    conn = sqlite3.connect(str(SEED_DB))
    try:
        t = conn.execute("SELECT COUNT(*) FROM movie_whitelist").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM movie_whitelist WHERE enriched=1").fetchone()[0]
        d_ru = conn.execute("SELECT COUNT(*) FROM movie_whitelist WHERE length(description_ru)>0").fetchone()[0]
        d_en = conn.execute("SELECT COUNT(*) FROM movie_whitelist WHERE length(description)>0").fetchone()[0]
    finally:
        conn.close()

    posters = list(SEED_POSTERS.glob("*.jpg"))
    big = [p for p in posters if p.stat().st_size >= 100_000]
    total_mb = sum(p.stat().st_size for p in posters) / 1e6

    log.info("-" * 70)
    log.info("БД: %d фильмов, %d enriched", t, e)
    log.info("Описания: %d RU, %d EN", d_ru, d_en)
    log.info("Постеры: %d файлов, %.1f MB, >100KB: %d",
             len(posters), total_mb, len(big))
    log.info("=" * 70)
    log.info("Дальше:")
    log.info("  python tools/apply_seed.py")
    log.info("  python main.py")


def main():
    parser = argparse.ArgumentParser(
        description="Обогащение whitelist_seed.db описаниями и постерами"
    )
    parser.add_argument("--allow-kp", action="store_true",
                        help="Тянуть RU-описания и постеры из Kinopoisk")
    parser.add_argument("--force", action="store_true",
                        help="Обработать все, даже enriched=1")
    parser.add_argument("--force-posters", action="store_true",
                        help="Перекачать постеры (даже если файл есть)")
    parser.add_argument("--delay", type=float, default=2.5,
                        help="Пауза между запросами, сек (2.5 — безопасно)")
    parser.add_argument("--pause-every", type=int, default=30,
                        help="Длинная пауза каждые N запросов")
    parser.add_argument("--pause-secs", type=float, default=30.0,
                        help="Длительность длинной паузы")
    parser.add_argument("--no-descriptions", action="store_true")
    parser.add_argument("--no-posters", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SEED_DB.exists():
        log.error("%s не найден", SEED_DB)
        return 1

    if args.dry_run:
        migrate_schema()
        rows = read_rows(force=args.force)
        log.info("К обработке: %d фильмов", len(rows))
        return 0

    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())