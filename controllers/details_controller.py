"""Контроллер карточки фильма + lazy resolve kp_id."""

import os

import aiohttp

import config
from core.logging_setup import get_logger
from database.history_repo import HistoryRepository
from database.whitelist_repo import WhitelistRepository

log = get_logger("details")

_MIN_POSTER_BYTES = 500
_IA_MIN_BYTES = 500


class DetailsController:
    def __init__(self, app):
        self.app = app
        self.loop = app.loop
        self.main_window = app.main_window
        self.session = app.session
        self.kp_service = app.kp_service

        self.current_movie_id = None
        self.current_movie_title = ""
        self.current_movie_metadata = None
        self._current_cover_task = None

    def open(self, kp_id: int):
        self.loop.create_task(self._open_details_page(kp_id))

    async def _open_details_page(self, kp_id: int):
        # === 1. Каскад постера: cache → seed → (в фоне) IA / KP ===
        cache_path = os.path.join(str(config.CACHE_DIR), f"{kp_id}.jpg")
        cover_path = ""
        if (os.path.exists(cache_path)
                and os.path.getsize(cache_path) > _MIN_POSTER_BYTES):
            cover_path = cache_path

        # === 2. Основные метаданные ===
        if kp_id < 0:
            row = WhitelistRepository.get_movie(kp_id)
            metadata = {
                "kp_id": kp_id,
                "title": row["title_ru"] if row else "Неизвестно",
                "title_en": row["title_en"] if row else "",
                "year": row["year"] if row else "----",
                "description": "Фильм общественного достояния.",
                "cover_path": cover_path,
            }
        else:
            metadata = await self.kp_service.get_movie_data(
                self.session, kp_id
            )
            metadata["kp_id"] = kp_id
            if not metadata.get("cover_path") and cover_path:
                metadata["cover_path"] = cover_path

        self.current_movie_id = kp_id
        self.current_movie_metadata = metadata
        self.current_movie_title = metadata.get("title", "Без названия")
        self.main_window.details_page.set_movie_id(kp_id)
        self.main_window.details_page.update_movie_details(metadata)
        self.main_window.screen_stack.setCurrentIndex(1)

        # === 3. Фоновая загрузка постера, если нет ===
        if not cover_path:
            self._current_cover_task = self.loop.create_task(
                self._load_cover_for_details(
                    kp_id,
                    title_en=metadata.get("title_en", ""),
                    title_ru=metadata.get("title", ""),
                    year=str(metadata.get("year", "")),
                )
            )

        # === 4. Lazy resolve для временных kp_id ===
        if kp_id < 0 and getattr(config, "LAZY_RESOLVE", True):
            self.loop.create_task(self._lazy_resolve(kp_id))

    # ==================================================================
    #  ЗАГРУЗКА ОБЛОЖКИ ДЛЯ ДЕТАЛЕЙ
    # ==================================================================
    async def _load_cover_for_details(
        self, kp_id: int, title_en: str, title_ru: str, year: str
    ):
        """Каскад: seed → IA → KP. Обновляет UI когда постер получен."""
        cache_path = os.path.join(str(config.CACHE_DIR), f"{kp_id}.jpg")

        # 1. seed_posters
        seed_dir = os.path.join(str(config.DATA_DIR), "seed_posters")
        p = os.path.join(seed_dir, f"{kp_id}.jpg")
        if os.path.exists(p) and os.path.getsize(p) > _MIN_POSTER_BYTES:
            try:
                import shutil
                shutil.copy2(p, cache_path)
            except Exception:
                pass
            self._apply_cover_to_ui(kp_id, p)
            return

        # 2. archive.org thumbnail
        archive_id = WhitelistRepository.get_archive_identifier(kp_id)
        if archive_id:
            ok = await self._try_ia_thumbnail(archive_id, cache_path)
            if ok:
                self._apply_cover_to_ui(kp_id, cache_path)
                return

        # 3. KP (только если kp_id > 0 или есть title_en)
        if kp_id > 0 or title_en:
            ok = await self._try_kp_cover(
                kp_id, title_en or title_ru, year, cache_path
            )
            if ok:
                self._apply_cover_to_ui(kp_id, cache_path)
                return

        log.info("Обложка для kp_id=%d не найдена ни в одном источнике",
                 kp_id)

    def _apply_cover_to_ui(self, kp_id: int, cover_path: str):
        """Обновляет UI только если пользователь всё ещё смотрит этот фильм."""
        if self.current_movie_id != kp_id:
            return
        if not os.path.exists(cover_path):
            return
        try:
            if self.current_movie_metadata is not None:
                self.current_movie_metadata["cover_path"] = cover_path
            self.main_window.details_page.update_movie_details(
                self.current_movie_metadata or {}
            )
        except Exception as e:
            log.debug("apply_cover_to_ui: %s", e)

    async def _try_ia_thumbnail(self, archive_id: str, cache_path: str) -> bool:
        url = f"https://archive.org/services/img/{archive_id}"
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    return False
                content = await resp.read()
            if len(content) < _IA_MIN_BYTES:
                return False

            def write():
                with open(cache_path, "wb") as f:
                    f.write(content)
            await self.loop.run_in_executor(None, write)
            log.info("Постер в деталях (IA): %s (%d B)",
                     archive_id, len(content))
            return True
        except Exception as e:
            log.debug("IA thumb %s: %s", archive_id, e)
            return False

    async def _try_kp_cover(
        self, kp_id: int, title: str, year: str, cache_path: str
    ) -> bool:
        poster_url = ""
        try:
            if kp_id > 0:
                metadata = await self.kp_service.get_movie_data(
                    self.session, kp_id
                )
                poster_url = (metadata.get("poster_url") or "").strip()
                if not poster_url and metadata.get("cover_path"):
                    # KP уже скачал — копируем
                    try:
                        import shutil
                        shutil.copy2(metadata["cover_path"], cache_path)
                        return True
                    except Exception:
                        pass
            if not poster_url:
                query = f"{title} {year}".strip()
                if not query:
                    return False
                films = await self._kp_search(query)
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
            log.debug("KP cover: %s", e)
            return False

        if not poster_url:
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
            log.info("Постер в деталях (KP): kp_id=%d (%d KB)",
                     kp_id, len(content) // 1024)
            return True
        except Exception as e:
            log.debug("KP download: %s", e)
            return False

    async def _kp_search(self, query: str) -> list[dict]:
        url = ("https://kinopoiskapiunofficial.tech"
               "/api/v2.1/films/search-by-keyword")
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
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []
        return data.get("films") or []

    # ==================================================================
    #  LAZY RESOLVE (kp_id < 0 → реальный)
    # ==================================================================
    async def _lazy_resolve(self, old_kp_id: int):
        row = WhitelistRepository.get_movie(old_kp_id)
        if not row:
            return

        title_en = row.get("title_en", "") or ""
        title_ru = row.get("title_ru", "") or ""
        year = row.get("year", "") or ""
        query = f"{title_en} {year}".strip() if title_en else title_ru
        if not query:
            return

        log.info("Lazy resolve: '%s'", query)
        try:
            results = await self.kp_service.search_movies_by_keyword(
                self.session, query
            )
        except Exception as e:
            log.warning("Lazy resolve: %s", e)
            return

        if not results:
            return

        new_kp_id = 0
        for m in results:
            if str(m.get("year", "")) == str(year):
                new_kp_id = m.get("kp_id") or 0
                break
        if not new_kp_id:
            new_kp_id = results[0].get("kp_id") or 0

        if not new_kp_id or new_kp_id <= 0:
            return

        WhitelistRepository.update_kp_id(old_kp_id, new_kp_id)
        log.info("Lazy resolve: %d → %d", old_kp_id, new_kp_id)

        if self.current_movie_id == old_kp_id:
            try:
                new_metadata = await self.kp_service.get_movie_data(
                    self.session, new_kp_id
                )
                new_metadata["kp_id"] = new_kp_id
                self.current_movie_id = new_kp_id
                self.current_movie_metadata = new_metadata
                self.current_movie_title = new_metadata.get(
                    "title", "Без названия"
                )
                self.main_window.details_page.set_movie_id(new_kp_id)
                self.main_window.details_page.update_movie_details(
                    new_metadata
                )
            except Exception as e:
                log.warning("Lazy resolve update: %s", e)

    # ==================================================================
    #  Навигация
    # ==================================================================
    def handle_back_to_feed(self):
        self.main_window.screen_stack.setCurrentIndex(0)

    def handle_resume_playback(self, movie_id: int):
        self.main_window.resume_island.hide()
        self.open(movie_id)

    def handle_resume_dismiss(self, movie_id: int):
        HistoryRepository.clear_history_entry(movie_id)
        self.main_window.resume_island.hide()

    def check_resume_island(self):
        if not hasattr(self.main_window, "resume_island"):
            return
        last = HistoryRepository.get_last_session()
        if last and last.get("current_seconds", 0) > 5:
            self.main_window.show_resume_bar(
                last["kp_id"], last["movie_title"]
            )
        else:
            self.main_window.resume_island.hide()
