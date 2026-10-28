"""
CLI-диагностика кэша KP.

    python -m tools.cache_stats
    python -m tools.cache_stats --clear-stale    # удалить устаревшее
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
import sys
import time
from pathlib import Path

import config


def _scan_dir(path: Path) -> dict:
    if not path.exists():
        return {"count": 0, "size": 0, "oldest": None, "newest": None}
    count = 0
    size = 0
    oldest = None
    newest = None
    for entry in path.iterdir():
        if not entry.is_file():
            continue
        try:
            st = entry.stat()
            count += 1
            size += st.st_size
            if oldest is None or st.st_mtime < oldest:
                oldest = st.st_mtime
            if newest is None or st.st_mtime > newest:
                newest = st.st_mtime
        except Exception:
            continue
    return {"count": count, "size": size, "oldest": oldest, "newest": newest}


def _fmt_age(ts) -> str:
    if ts is None:
        return "—"
    age = time.time() - ts
    if age < 3600:
        return f"{age/60:.0f} мин назад"
    if age < 86400:
        return f"{age/3600:.1f} ч назад"
    return f"{age/86400:.1f} дн назад"


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.1f} MB"


def cmd_stats() -> int:
    base = Path(config.CACHE_DIR)
    print("=" * 70)
    print("  СТАТИСТИКА КЭША KP")
    print("=" * 70)

    for label, sub in [
        ("Постеры (data/cache/*.jpg)", base),
        ("Short (data/cache/short/)", getattr(config, "CACHE_SHORT_DIR", base / "short")),
        ("Full (data/cache/full/)", getattr(config, "CACHE_FULL_DIR", base / "full")),
        ("Lists (data/cache/lists/)", getattr(config, "CACHE_LISTS_DIR", base / "lists")),
    ]:
        p = Path(sub)
        if label.startswith("Постеры") and p.exists():
            # для постеров — только *.jpg
            stats = {"count": 0, "size": 0, "oldest": None, "newest": None}
            for entry in p.iterdir():
                if not entry.is_file() or not entry.name.endswith(".jpg"):
                    continue
                try:
                    st = entry.stat()
                    stats["count"] += 1
                    stats["size"] += st.st_size
                    if stats["oldest"] is None or st.st_mtime < stats["oldest"]:
                        stats["oldest"] = st.st_mtime
                    if stats["newest"] is None or st.st_mtime > stats["newest"]:
                        stats["newest"] = st.st_mtime
                except Exception:
                    pass
        else:
            stats = _scan_dir(p)

        print(f"\n  {label}")
        print(f"    Файлов:    {stats['count']}")
        print(f"    Размер:    {_fmt_size(stats['size'])}")
        print(f"    Старейший: {_fmt_age(stats['oldest'])}")
        print(f"    Новейший:  {_fmt_age(stats['newest'])}")

    print("\n" + "=" * 70)
    return 0


def cmd_clear_stale() -> int:
    """Удаляет списки (popular/search) старше их TTL."""
    lists_dir = Path(getattr(config, "CACHE_LISTS_DIR", config.CACHE_DIR / "lists"))
    if not lists_dir.exists():
        print("Папка lists не существует")
        return 0

    popular_ttl = getattr(config, "POPULAR_CACHE_TTL_HOURS", 24) * 3600
    search_ttl = getattr(config, "SEARCH_CACHE_TTL_HOURS", 6) * 3600

    removed = 0
    for entry in lists_dir.iterdir():
        if not entry.is_file():
            continue
        try:
            age = time.time() - entry.stat().st_mtime
            # heuristic: popular живет дольше search, берём максимум
            if age > max(popular_ttl, search_ttl):
                entry.unlink()
                removed += 1
        except Exception:
            continue
    print(f"Удалено устаревших файлов: {removed}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Диагностика кэша KP Amagi-Player",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("stats", help="Показать статистику")
    sub.add_parser("clear-stale", help="Удалить устаревшие списки")

    args = parser.parse_args()
    if args.cmd == "clear-stale":
        return cmd_clear_stale()
    return cmd_stats()


if __name__ == "__main__":
    sys.exit(main())
