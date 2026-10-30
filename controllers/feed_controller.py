"""Контроллер ленты.

Изменения v2.0.6:
  - _pagination_lock: race condition при быстром скролле страниц.
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
import os
import re
import time

import aiohttp
from PyQt6.QtCore import QTimer

import config
from core.logging_setup import get_logger
from database.whitelist_repo import WhitelistRepository
from ui.widgets.card_widget import MovieCardWidget

log = get_logger("feed")

PAGE_SIZE = 20
_KP_MIN_INTERVAL = 1.5
_KP_COOLDOWN_429_SEC = 60.0
_MIN_POSTER_BYTES = 2000

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _make_slug(title: str, year: str = "") -> str:
    s = (title or "").lower()
    s = _SLUG_RE.sub("_", s).strip("_")
    if year and year != "----":
        s = f"{s}_{year}" if s else str(year)
    return s[:100]


def _find_seed_poster(kp_id: int, title_en: str, year: str) -> str:
    seed_dir = os.path.join(str(config.DATA_DIR), "seed_posters")
    if not os.path.isdir(seed_dir):
        return ""
    p = os.path.join(seed_dir, f"{kp_id}.jpg")
    if os.path.exists(p) and os.path.getsize(p) > _MIN_POSTER_BYTES:
        return p
    slug = _make_slug(title_en, str(year))
    if slug:
        p = os.path.join(seed_dir, f"{slug}.jpg")
        if os.path.exists(p) and os.path.getsize(p) > _MIN_POSTER_BYTES:
            return p
    return ""


class FeedController:
    def __init__(self, app):
        self.app = app
        self.loop = app.loop
        self.main_window = app.main_window
        self.session = app.session
        self.kp_service = app.kp_service

        self.current_page = 1
        self._search_generation = 0
        self._kp_last_request = 0.0
        self._kp_cooldown_until = 0.0
        self._db_stats_logged = False
        self._pagination_lock = asyncio.Lock()

    async def load_feed(self, clear_grid: bool = False):
        if clear_grid:
            self.main_window.feed_page.clear_grid()
            self.main_window.feed_page.reset_loading_state()
            self._db_stats_logged = False

        generation = self._search_generation
        query = self.main_window.search_bar.text().strip()

        if config.DISABLE_WHITELIST:
            if query:
                movies = await self.kp_service.search_movies_by_keyword(
                    self.session, query, page=self.current_page
                )
            else:
                movies = await self.kp_service.get_popular_movies(
                    self.session, page=self.current_page
                )
            has_more = len(movies) >= PAGE_SIZE
        else:
            offset = (self.current_page - 1) * PAGE_SIZE
            movies = self._build_movies_from_whitelist(
                query, limit=PAGE_SIZE, offset=offset
            )
            has_more = len(movies) >= PAGE_SIZE

            if (not self._db_stats_logged
                    and not query
                    and self.current_page == 1):
                self._log_db_stats()
                self._db_stats_logged = True

        if generation != self._search_generation:
            self.main_window.feed_page.reset_loading_state()
            return

        log.info(
            "Лента: page=%d, %d фильмов (mode=%s, query='%s', has_more=%s)",
            self.current_page, len(movies),
            "public" if not config.DISABLE_WHITELIST else "private",
            query or "-", has_more,
        )

        if not movies and clear_grid and query:
            log.info("Поиск '%s' — ничего не найдено", query)
            try:
                self.main_window.player_page.loader_label.setText(
                    f"ПО ЗАПРОСУ '{query.upper()}' НИЧЕГО НЕ НАЙДЕНО"
                )
            except Exception:
                pass

        added_count = 0
        for data in movies:
            kp_id = data.get("kp_id")
            if not kp_id:
                continue
            card = MovieCardWidget(
                kp_id=kp_id,
                title=data.get("title", "Без названия"),
                year=data.get("year", "----"),
                cover_path=data.get("cover_path", ""),
            )
            card.play_requested.connect(self._on_card_clicked)
            added = self.main_window.feed_page.add_card_to_grid(card)
            if added:
                added_count += 1
                if not data.get("cover_path"):
                    self.loop.create_task(
                        self._load_poster_cascade(
                            kp_id, card,
                            title=data.get("title", ""),
                            title_en=data.get("title_en", ""),
                            year=data.get("year", ""),
                        )
                    )

        if not has_more:
            self.main_window.feed_page.mark_end_reached()
            log.info(
                "Больше страниц нет (page=%d), лента закрыта",
                self.current_page,
            )

    def _log_db_stats(self):
        try:
            total = WhitelistRepository.count()
            avail = WhitelistRepository.count_available()
            unverified = WhitelistRepository.count_unverified()
            log.info(
                "БД: всего=%d, available=1: %d, available=NULL: %d",
                total, avail, unverified,
            )
            if avail < total:
                log.warning(
                    "ВНИМАНИЕ: %d фильмов имеют available != 1 "
                    "и не показываются в public-режиме. "
                    "Проверьте: python tools/apply_seed.py",
                    total - avail,
                )
        except Exception as e:
            log.debug("_log_db_stats: %s", e)

    def _build_movies_from_whitelist(
        self, query: str, limit: int, offset: int
    ) -> list[dict]:
        ids = WhitelistRepository.search_movies_in_feed(
            query, limit=limit, offset=offset
        )
        movies = []
        for kp_id in ids:
            row = WhitelistRepository.get_movie(kp_id)
            if not row:
                continue
            title = row.get("title_ru") or row.get("title_en") or "Без названия"
            title_en = row.get("title_en") or ""
            year = row.get("year") or "----"

            cache_path = os.path.join(str(config.CACHE_DIR), f"{kp_id}.jpg")
            cover = ""
            if (os.path.exists(cache_path)
                    and os.path.getsize(cache_path) > _MIN_POSTER_BYTES):
                cover = cache_path
            else:
                seed = _find_seed_poster(kp_id, title_en, year)
                if seed:
                    cover = seed
                    try:
                        import shutil
                        shutil.copy2(seed, cache_path)
                    except Exception:
                        pass

            movies.append({
                "kp_id": kp_id,
                "title": title,
                "title_en": title_en,
                "year": year,
                "description": "Фильм общественного достояния.",
                "cover_path": cover,
                "poster_url": None,
            })
        return movies

    async def _load_poster_cascade(
        self, kp_id: int, card, title: str, title_en: str, year: str
    ):
        from PyQt6 import sip
        if not self.session or sip.isdeleted(card):
            return

        cache_path = os.path.join(str(config.CACHE_DIR), f"{kp_id}.jpg")

        if (os.path.exists(cache_path)
                and os.path.getsize(cache_path) > _MIN_POSTER_BYTES):
            if not sip.isdeleted(card):
                card.update_poster(cache_path)
            return

        seed = _find_seed_poster(kp_id, title_en, year)
        if seed:
            try:
                import shutil
                shutil.copy2(seed, cache_path)
            except Exception:
                pass
            if not sip.isdeleted(card):
                card.update_poster(seed)
            return

        archive_id = WhitelistRepository.get_archive_identifier(kp_id)
        if archive_id:
            ok = await self._try_archive_thumbnail(archive_id, cache_path)
            if ok:
                if not sip.isdeleted(card):
                    card.update_poster(cache_path)
                return

        ok = await self._try_kp_poster(
            kp_id, title, title_en, year, cache_path
        )
        if ok:
            if not sip.isdeleted(card):
                card.update_poster(cache_path)

    async def _try_archive_thumbnail(
        self, archive_id: str, cache_path: str
    ) -> bool:
        url = f"https://archive.org/services/img/{archive_id}"
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    return False
                content = await resp.read()
            if len(content) < _MIN_POSTER_BYTES:
                return False

            def write():
                with open(cache_path, "wb") as f:
                    f.write(content)
            await self.loop.run_in_executor(None, write)
            log.info(
                "Постер IA: %s (%d KB)",
                archive_id, len(content) // 1024,
            )
            return True
        except Exception as e:
            log.debug("IA thumb %s: %s", archive_id, e)
            return False

    async def _try_kp_poster(
        self, kp_id: int, title: str, title_en: str, year: str,
        cache_path: str,
    ) -> bool:
        now = time.time()
        if now < self._kp_cooldown_until:
            return False
        elapsed = now - self._kp_last_request
        if elapsed < _KP_MIN_INTERVAL:
            await asyncio.sleep(_KP_MIN_INTERVAL - elapsed)

        poster_url = ""
        try:
            if kp_id > 0:
                metadata = await self.kp_service.get_movie_data(
                    self.session, kp_id
                )
                self._kp_last_request = time.time()
                poster_url = (metadata.get("poster_url") or "").strip()
            else:
                query = f"{title_en or title} {year}".strip()
                if not query:
                    return False
                films = await self._kp_search(query)
                self._kp_last_request = time.time()
                if not films:
                    return False
                best = next(
                    (f for f in films if str(f.get("year", "")) == year),
                    films[0],
                )
                poster_url = (
                    best.get("posterUrlPreview")
                    or best.get("posterUrl") or ""
                )
        except Exception as e:
            log.debug("KP poster: %s", e)
            return False

        if not poster_url:
            return False
        if not poster_url.startswith(("https://", "http://")):
            return False
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with self.session.get(
                poster_url, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    return False
                content = await resp.read()

            def write():
                with open(cache_path, "wb") as f:
                    f.write(content)
            await self.loop.run_in_executor(None, write)
            log.info(
                "Постер KP: kp_id=%d (%d KB)",
                kp_id, len(content) // 1024,
            )
            return True
        except Exception as e:
            log.debug("KP download: %s", e)
            return False

    async def _kp_search(self, query: str) -> list[dict]:
        url = (
            "https://kinopoiskapiunofficial.tech"
            "/api/v2.1/films/search-by-keyword"
        )
        headers = {
            "X-API-KEY": config.KP_API_KEY,
            "Accept": "application/json",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            async with self.session.get(
                url, headers=headers,
                params={"keyword": query, "page": 1},
                timeout=timeout,
            ) as resp:
                if resp.status == 429:
                    self._kp_cooldown_until = (
                        time.time() + _KP_COOLDOWN_429_SEC
                    )
                    log.warning(
                        "KP: 429 — cooldown %.0fs",
                        _KP_COOLDOWN_429_SEC,
                    )
                    return []
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []
        films = data.get("films") or []
        return [{
            "kp_id": f.get("filmId") or f.get("kinopoiskId"),
            "year": str(f.get("year") or ""),
            "posterUrlPreview": f.get("posterUrlPreview") or "",
            "posterUrl": f.get("posterUrl") or "",
        } for f in films]

    def on_search_text_changed(self, _text: str):
        self.app.search_debounce.stop()
        self.app.search_debounce.start()

    def run_search(self):
        self._search_generation += 1
        self.current_page = 1
        self.main_window.feed_page.mark_end_not_reached()
        self.main_window.feed_page.reset_loading_state()
        self.loop.create_task(self.load_feed(clear_grid=True))

    def load_next_page(self):
        """Синхронный слот сигнала — запускает async-задачу с lock."""
        self.loop.create_task(self._load_next_page_async())

    async def _load_next_page_async(self):
        # Быстрый скролл: если уже грузим следующую — игнорируем
        if self._pagination_lock.locked():
            log.debug("load_next_page: уже загружается, пропускаем")
            return
        async with self._pagination_lock:
            self.current_page += 1
            try:
                await self.load_feed(clear_grid=False)
            except Exception as e:
                log.warning("load_next_page: %s", e)

    def _on_card_clicked(self, kp_id: int):
        log.info("Клик: kp_id=%s", kp_id)
        self.app.details.open(kp_id)

    def shutdown(self):
        pass