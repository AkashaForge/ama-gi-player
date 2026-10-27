#!/usr/bin/env python3
"""
Применяет data/whitelist_seed.db → data/whitelist.db.

Простое копирование без зависимостей от switch_mode.
Ставит available=1 для всех фильмов.

Использование:
  python tools/apply_seed.py
"""

import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = DATA / "whitelist_seed.db"
TARGET = DATA / "whitelist.db"


def main() -> int:
    print("=" * 60)
    print("Применение seed → whitelist.db")
    print("=" * 60)

    # 1. Проверка seed
    if not SEED.exists():
        print(f"❌ {SEED} НЕ НАЙДЕН")
        print("   Запусти: python tools/make_seed.py --rebuild")
        return 1

    seed_size = SEED.stat().st_size
    print(f"  📂 Seed: {SEED}")
    print(f"  📊 Размер: {seed_size // 1024} KB")

    try:
        conn = sqlite3.connect(str(SEED))
        seed_count = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist"
        ).fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка чтения seed: {e}")
        return 1

    print(f"  📊 Фильмов в seed: {seed_count}")

    if seed_count == 0:
        print("❌ Seed пустой (0 фильмов)")
        print("   Запусти: python tools/make_seed.py --rebuild")
        return 1

    # 2. Удалить старый whitelist.db + WAL/SHM
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(TARGET) + suffix)
        if p.exists():
            p.unlink()
            print(f"  🗑  Удалён: {p.name}")

    # 3. Скопировать seed → target
    try:
        shutil.copy2(SEED, TARGET)
        print("  ✅ Скопировано: seed → whitelist.db")
    except Exception as e:
        print(f"❌ Ошибка копирования: {e}")
        return 1

    # 4. Поставить available=1 для всех
    try:
        conn = sqlite3.connect(str(TARGET))
        conn.execute(
            "UPDATE movie_whitelist SET available = 1 "
            "WHERE available IS NULL"
        )
        conn.commit()

        final_count = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist"
        ).fetchone()[0]
        available_count = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist WHERE available = 1"
        ).fetchone()[0]
        with_ia = conn.execute(
            "SELECT COUNT(*) FROM movie_whitelist "
            "WHERE archive_identifier != ''"
        ).fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка обновления: {e}")
        return 1

    # 5. Итог
    print("=" * 60)
    print("✅ ГОТОВО")
    print(f"   Фильмов:      {final_count}")
    print(f"   available=1:  {available_count}")
    print(f"   с IA:         {with_ia}")
    print("=" * 60)
    print()
    print("Запускай: python main.py")
    print()

    if final_count != seed_count:
        print(f"⚠️  ВНИМАНИЕ: было {seed_count}, стало {final_count}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
