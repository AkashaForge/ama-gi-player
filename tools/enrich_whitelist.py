#!/usr/bin/env python3
"""
Обогащение whitelist_seed.db описаниями и качественными постерами.

Запускается ОДИН РАЗ. Не пересобирает seed — дополняет существующие записи:
  - description (EN)  из archive.org/metadata/{id}
  - description_ru    из KP (опционально, --allow-kp)
  - poster_source     откуда взят постер (IA-files / IA-thumb / KP / skip)
  - enriched = 1      отметка «эта запись обработана»
  - data/seed_posters/{kp_id}.jpg — скачанный постер

Особенности:
  - rate limit: 1 запрос в 1.5 сек, чтобы не забанили IA
  - длинная пауза каждые N запросов (--pause-every)
  - пропускает уже обогащённые (enriched=1), можно прервать и продолжить
  - НЕ трогает whitelist.db (working), только seed
  - не качает постеры заново, если файл уже есть и > 3 КБ
  - миграция схемы: добавит description, description_ru,
    poster_source, enriched, если их нет

Использование:
  python tools/enrich_whitelist.py
  python tools/enrich_whitelist.py --allow-kp
  python tools/enrich_whitelist.py --force
  python tools/enrich_whitelist.py --delay 2.0 --pause-every 20
  python tools/enrich_whitelist.py --no-posters
  python tools/enrich_whitelist.py --no-descriptions
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


# ======================================================================
#  Утилиты
# ======================================================================
def clean_description(raw) -> str:
    """HTML/список → plain text, обрезает до MAX_DESC_LEN."""
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
#  Миграция схемы seed
# ======================================================================
_NEW_COLUMNS = [
    ("description",    "TEXT DEFAULT ''"),
    ("description_ru", "TEXT DEFAULT ''"),
    ("poster_source",  "TEXT DEFAULT ''"),
    ("enriched",       "INTEGER DEFAULT 0"),
]


def migrate_schema():
    """Добавляет новые колонки, если их нет. Идемпотентно."""
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
                        f"ALTER TABLE movie_whitelist "
                        f"ADD COLUMN {col} {decl};"
                    )
                    added.append(col)
                except Exception as e:
                    log.warning("ALTER %s: %s", col, e)
        conn.commit()
        if added:
            log.info("Миграция: добавлены колонки %s", ", ".join(added))
        else:
            log.info("Схема актуальна, миграция не нужна")
    finally:
        conn.close()


# ======================================================================
#  Чтение seed
# ======================================================================
def read_rows(force: bool) -> list[dict]:
    conn = sqlite3.connect(str(SEED_DB))
    conn.row_factory = sqlite3.Row
    try:
        where = "" if force else "WHERE (enriched IS NULL OR enriched = 0)"
        cur = conn.execute(
            f"SELECT kp_id, title_ru, title_en, year, "
            f"archive_identifier, description, description_ru, "
            f"poster_source, enriched "
            f"FROM movie_whitelist {where} "
            f"ORDER BY kp_id DESC;"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_row(kp_id: int, description: str = None,
               description_ru: str = None,
               poster_source: str = None, enriched: int = 1):
    """Обновляет только переданные поля (не затирает остальные)."""
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
            f"UPDATE movie_whitelist SET {', '.join(fields)} "
            f"WHERE kp_id = ?;",
            params,
        )
        conn.commit()
    finally:
        conn.close()


# ======================================================================
#  HTTP-клиент IA
# ======================================================================
async def http_get_json(session, url, timeout=15, retries=2):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers={"User-Agent": UA},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (429, 503):
                    wait = 10 * attempt
                    log.warning("HTTP %d на %s, пауза %ds",
                                resp.status, url, wait)
                    await asyncio.sleep(wait)
                    continue
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.debug("HTTP попытка %d/%d: %s", attempt, retries, e)
            if attempt < retries:
                await asyncio.sleep(3 * attempt)
    return None


async def http_download(session, url, path: Path) -> bool:
    """Скачивает файл, если ещё нет или < 3 КБ. Возвращает True при успехе."""
    if path.exists() and path.stat().st_size >= MIN_POSTER_BYTES:
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
            log.warning("Постер слишком большой: %.1f MB",
                        len(content) / 1_000_000)
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return True
    except Exception as e:
        log.debug("Скачивание %s: %s", url, e)
        return False


# ======================================================================
#  IA metadata → (описание, url постера)
# ======================================================================
def _pick_best_poster(files: list) -> str | None:
    """Ищет в files самый «похожий на постер» JPG/PNG."""
    candidates = []
    for f in files:
        name = (f.get("name") or "").lower()
        if not name.endswith((".jpg", ".jpeg", ".png")):
            continue
        size = int(f.get("size") or 0)
        if size < MIN_FILE_POSTER_BYTES:
            continue
        score = 0
        if "poster" in name:                              score += 100
        if "cover" in name:                               score += 90
        if "box" in name or "front" in name:              score += 80
        if "thumb" in name:                               score += 30
        if "screenshot" in name or "sample" in name:      score -= 200
        if "frame" in name or "still" in name:            score -= 150
        candidates.append((score, size, f["name"]))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    best_score, _, best_name = candidates[0]
    return best_name if best_score > 0 else None


async def fetch_ia_metadata(session, archive_id: str):
    """Возвращает (description_en, poster_name, poster_size)."""
    if not archive_id:
        return ("", None, 0)
    data = await http_get_json(
        session, f"https://archive.org/metadata/{archive_id}"
    )
    if not data:
        return ("", None, 0)
    meta = data.get("metadata") or {}
    files = data.get("files") or []
    desc = clean_description(meta.get("description"))
    best = _pick_best_poster(files)
    if best:
        for f in files:
            if f.get("name") == best:
                return (desc, best, int(f.get("size") or 0))
    return (desc, None, 0)


# ======================================================================
#  KP-клиент (только для --allow-kp)
# ======================================================================
class KPClient:
    BASE = "https://kinopoiskapiunofficial.tech"
    MIN_INTERVAL = 2.0

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = None
        self.last = 0.0
        self.used = 0
        self.calls_402 = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12)
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def get_movie(self, kp_id: int) -> dict | None:
        if kp_id <= 0:
            return None
        elapsed = time.time() - self.last
        if elapsed < self.MIN_INTERVAL:
            await asyncio.sleep(self.MIN_INTERVAL - elapsed)
        headers = {"X-API-KEY": self.api_key, "Accept": "application/json"}
        try:
            async with self.session.get(
                f"{self.BASE}/api/v2.2/films/{kp_id}", headers=headers
            ) as resp:
                self.last = time.time()
                if resp.status == 402:
                    self.calls_402 += 1
                    log.warning("KP 402 (лимит), пауза 30с")
                    await asyncio.sleep(30)
                    return None
                if resp.status != 200:
                    return None
                self.used += 1
                return await resp.json()
        except Exception as e:
            log.debug("KP %d: %s", kp_id, e)
            return None


# ======================================================================
#  Обработка одной записи
# ======================================================================
async def enrich_one(session, kp: KPClient | None, row: dict,
                      no_descriptions: bool, no_posters: bool,
                      allow_kp: bool) -> str:
    kp_id = row["kp_id"]
    archive_id = (row["archive_identifier"] or "").strip()

    desc_en = row["description"] or ""
    desc_ru = row["description_ru"] or ""
    source = row["poster_source"] or ""
    poster_path = SEED_POSTERS / f"{kp_id}.jpg"

    if not archive_id and not (allow_kp and kp_id > 0):
        log.info("  [skip] нет archive_identifier и kp_id < 0")
        update_row(kp_id, poster_source="skip", enriched=1)
        return "skip"

    # --- 1. IA metadata: описание EN + лучший постер ---
    ia_poster_url = None
    if archive_id:
        d, poster_name, poster_size = await fetch_ia_metadata(
            session, archive_id
        )
        if d and not no_descriptions:
            desc_en = d
        if poster_name:
            ia_poster_url = (
                f"https://archive.org/download/{archive_id}/{poster_name}"
            )
            log.debug("  IA poster: %s (%.1f KB)",
                      poster_name, poster_size / 1024)

    # --- 2. Скачивание постера ---
    poster_ok = poster_path.exists() and poster_path.stat().st_size >= MIN_POSTER_BYTES
    if not poster_ok and not no_posters:
        if ia_poster_url:
            poster_ok = await http_download(session, ia_poster_url, poster_path)
            if poster_ok:
                source = "IA-files"
        # Fallback: IA thumbnail
        if not poster_ok and archive_id:
            thumb_url = (
                f"https://archive.org/services/img/{archive_id}"
            )
            poster_ok = await http_download(session, thumb_url, poster_path)
            if poster_ok:
                source = "IA-thumb"

    # --- 3. KP: описание RU + постер (если --allow-kp) ---
    if allow_kp and kp and kp_id > 0:
        kp_data = await kp.get_movie(kp_id)
        if kp_data:
            if not desc_ru and not no_descriptions:
                desc_ru = clean_description(kp_data.get("description"))
                if desc_ru:
                    log.debug("  KP desc_RU: %d симв.", len(desc_ru))
            if not poster_ok and not no_posters:
                kp_poster = (
                    kp_data.get("posterUrl")
                    or kp_data.get("posterUrlPreview") or ""
                )
                if kp_poster:
                    poster_ok = await http_download(
                        session, kp_poster, poster_path
                    )
                    if poster_ok:
                        source = "KP"

    if not source:
        source = "none"

    update_row(
        kp_id,
        description=None if no_descriptions else desc_en,
        description_ru=None if no_descriptions else desc_ru,
        poster_source=source,
        enriched=1,
    )
    return source


# ======================================================================
#  Главный цикл (последовательный, с паузами)
# ======================================================================
async def run(args):
    migrate_schema()
    rows = read_rows(force=args.force)
    total = len(rows)
    if total == 0:
        log.info("Нечего обогащать: все записи уже enriched=1")
        log.info("Запусти с --force, чтобы пересчитать заново")
        return

    SEED_POSTERS.mkdir(parents=True, exist_ok=True)
    log.info("=" * 70)
    log.info("К обогащению: %d фильмов", total)
    log.info("Задержка: %.1f сек | пауза %.0f сек каждые %d запросов",
             args.delay, args.pause_secs, args.pause_every)
    log.info("allow_kp=%s, descriptions=%s, posters=%s",
             args.allow_kp,
             not args.no_descriptions, not args.no_posters)
    log.info("=" * 70)

    stats = {"IA-files": 0, "IA-thumb": 0, "KP": 0,
             "skip": 0, "none": 0, "error": 0}
    start_ts = time.time()

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        kp = None
        if args.allow_kp and getattr(config, "KP_API_KEY", ""):
            kp = KPClient(config.KP_API_KEY)
            await kp.__aenter__()
            log.info("KP-клиент активен (описания RU + постеры)")
        elif args.allow_kp:
            log.warning("--allow-kp передан, но KP_API_KEY не задан в .env")

        try:
            for i, row in enumerate(rows, 1):
                title = row["title_en"] or row["title_ru"]
                year = row["year"] or "----"
                log.info("[%d/%d] %s (%s)", i, total, title, year)

                try:
                    source = await enrich_one(
                        session, kp, row,
                        no_descriptions=args.no_descriptions,
                        no_posters=args.no_posters,
                        allow_kp=args.allow_kp,
                    )
                    stats[source if source in stats else "none"] += 1
                except Exception as e:
                    log.error("  Ошибка: %s", e)
                    stats["error"] += 1

                # Паузы
                await asyncio.sleep(args.delay)
                if i % args.pause_every == 0 and i < total:
                    log.info("  → пауза %.0f сек (rate limit)", args.pause_secs)
                    await asyncio.sleep(args.pause_secs)
        finally:
            if kp:
                await kp.__aexit__()

    elapsed = time.time() - start_ts
    log.info("=" * 70)
    log.info("ГОТОВО за %.1f мин", elapsed / 60)
    log.info("  IA files постер:  %d", stats["IA-files"])
    log.info("  IA thumb постер:  %d", stats["IA-thumb"])
    log.info("  KP постер:        %d", stats["KP"])
    log.info("  skip:             %d", stats["skip"])
    log.info("  без постера:      %d", stats["none"])
    log.info("  ошибок:           %d", stats["error"])

    # Финальная статистика по БД
    conn = sqlite3.connect(str(SEED_DB))
    try:
        t = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist"
        ).fetchone()[0]
        e = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist WHERE enriched = 1"
        ).fetchone()[0]
        d_en = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist "
            "WHERE length(description) > 0"
        ).fetchone()[0]
        d_ru = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist "
            "WHERE length(description_ru) > 0"
        ).fetchone()[0]
    finally:
        conn.close()

    poster_count = len(list(SEED_POSTERS.glob("*.jpg")))
    poster_mb = sum(
        p.stat().st_size for p in SEED_POSTERS.glob("*.jpg")
    ) / 1_000_000

    log.info("-" * 70)
    log.info("БД: %d фильмов, %d enriched", t, e)
    log.info("Описания: %d EN, %d RU", d_en, d_ru)
    log.info("Постеры: %d файлов, %.1f MB", poster_count, poster_mb)
    log.info("=" * 70)
    log.info("Дальше:")
    log.info("  python tools/apply_seed.py   # seed → whitelist.db")
    log.info("  python main.py                # проверить")


def main():
    parser = argparse.ArgumentParser(
        description="Обогащение whitelist_seed.db описаниями и постерами"
    )
    parser.add_argument("--allow-kp", action="store_true",
                        help="Тянуть RU-описания и постеры из KP")
    parser.add_argument("--force", action="store_true",
                        help="Обработать заново все записи (включая enriched=1)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Пауза между запросами, сек (по умолчанию 1.5)")
    parser.add_argument("--pause-every", type=int, default=20,
                        help="Каждые N запросов — длинная пауза")
    parser.add_argument("--pause-secs", type=float, default=10.0,
                        help="Длительность длинной паузы, сек")
    parser.add_argument("--no-descriptions", action="store_true",
                        help="Не тянуть описания, только постеры")
    parser.add_argument("--no-posters", action="store_true",
                        help="Не качать постеры, только описания")
    parser.add_argument("--dry-run", action="store_true",
                        help="Только показать, что будет обработано")
    args = parser.parse_args()

    if not SEED_DB.exists():
        log.error("%s не найден", SEED_DB)
        log.error("Сначала: python tools/make_seed.py --rebuild")
        return 1

    if args.dry_run:
        migrate_schema()
        rows = read_rows(force=args.force)
        log.info("Будет обработано: %d фильмов", len(rows))
        for i, r in enumerate(rows[:10], 1):
            log.info("  %d. %s (%s)", i,
                     r["title_en"] or r["title_ru"], r["year"])
        if len(rows) > 10:
            log.info("  ... и ещё %d", len(rows) - 10)
        return 0

    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())