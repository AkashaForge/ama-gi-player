"""Контроллер карточки фильма.

v2.0.6:
  - Lucene-эскейпинг в _search_archive_identifier (было — только `"`);
  - проверка схемы poster_url (_try_kp_cover);
  - остальное как в v2.0.5.
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

import html as html_lib
import os
import re

import aiohttp

import config
from core.logging_setup import get_logger
from database.history_repo import HistoryRepository
from database.whitelist_repo import WhitelistRepository

log = get_logger("details")

_MIN_POSTER_BYTES = 500
_IA_MIN_BYTES = 500
_MAX_DESCRIPTION_LEN = 500

_WHITELIST_DESC_FIELDS = (
    "description_ru",
    "description",
)

# Lucene escape (то же, что в archive_org_searcher)
_LUCENE_SPECIAL_RE = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')


def _escape_lucene(s: str) -> str:
    if not s:
        return ""
    return _LUCENE_SPECIAL_RE.sub(r'\\\1', s)


def _is_cyrillic_dominant(text: str) -> bool:
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    cyrillic = sum(1 for c in letters if "\u0400" <= c <= "\u04FF")
    return (cyrillic / len(letters)) > 0.30


def _clean_ia_description(raw) -> str:
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

    if len(text) > _MAX_DESCRIPTION_LEN:
        cut = text[: _MAX_DESCRIPTION_LEN - 3].rstrip()
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut + "..."
    return text


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
        self._current_desc_task = None

    def _is_public(self) -> bool:
        return bool(getattr(config, "LEGAL_ONLY_MODE", True))

    def _kp_enabled(self) -> bool:
        return not self._is_public()

    def open(self, kp_id: int):
        self.loop.create_task(self._open_details_page(kp_id))

    async def _open_details_page(self, kp_id: int):
        if hasattr(self.main_window, "resume_island"):
            self.main_window.resume_island.hide()

        cache_path = os.path.join(str(config.CACHE_DIR), f"{kp_id}.jpg")
        cover_path = ""
        if (os.path.exists(cache_path)
                and os.path.getsize(cache_path) > _MIN_POSTER_BYTES):
            cover_path = cache_path

        if kp_id < 0:
            metadata = self._metadata_from_whitelist(kp_id, cover_path)
        elif self._kp_enabled():
            metadata = await self.kp_service.get_movie_data(
                self.session, kp_id
            )
            metadata["kp_id"] = kp_id
            if not metadata.get("cover_path") and cover_path:
                metadata["cover_path"] = cover_path
        else:
            metadata = self._metadata_from_whitelist(kp_id, cover_path)

        self.current_movie_id = kp_id
        self.current_movie_metadata = metadata
        self.current_movie_title = metadata.get("title", "Без названия")
        self.main_window.details_page.set_movie_id(kp_id)
        self.main_window.details_page.update_movie_details(metadata)
        self.main_window.screen_stack.setCurrentIndex(1)

        will_lazy_resolve = (
            self._kp_enabled()
            and kp_id < 0
            and getattr(config, "LAZY_RESOLVE", True)
        )

        if not cover_path:
            self._current_cover_task = self.loop.create_task(
                self._load_cover_for_details(
                    kp_id,
                    title_en=metadata.get("title_en", ""),
                    title_ru=metadata.get("title", ""),
                    year=str(metadata.get("year", "")),
                )
            )
        if (not (metadata.get("description") or "").strip()
                and not will_lazy_resolve):
            self._current_desc_task = self.loop.create_task(
                self._load_description_for_details(
                    kp_id,
                    title_en=metadata.get("title_en", ""),
                    title_ru=metadata.get("title", ""),
                    year=str(metadata.get("year", "")),
                )
            )

        if will_lazy_resolve:
            self.loop.create_task(self._lazy_resolve(kp_id))

    def _metadata_from_whitelist(self, kp_id: int, cover_path: str) -> dict:
        row = WhitelistRepository.get_movie(kp_id)
        row_dict = dict(row) if row else {}
        desc_ru = (row_dict.get("description_ru") or "").strip()
        desc_en = (row_dict.get("description") or "").strip()
        description = desc_ru or desc_en
        return {
            "kp_id": kp_id,
            "title": row_dict.get("title_ru") or "Без названия",
            "title_en": row_dict.get("title_en") or "",
            "year": row_dict.get("year") or "----",
            "description": description,
            "cover_path": cover_path,
        }

    def _whitelist_description(self, kp_id: int, row) -> str:
        if not row:
            return ""
        try:
            row_dict = dict(row)
        except Exception:
            return ""
        for field in _WHITELIST_DESC_FIELDS:
            val = row_dict.get(field)
            if val and _is_cyrillic_dominant(str(val)):
                return str(val).strip()
        return ""

    async def _load_description_for_details(
        self, kp_id: int, title_en: str, title_ru: str, year: str
    ):
        archive_id = WhitelistRepository.get_archive_identifier(kp_id)
        if not archive_id and (title_en or title_ru):
            archive_id = await self._search_archive_identifier(
                title_en or title_ru, year
            )
        if not archive_id:
            log.debug("description: нет identifier для kp_id=%d", kp_id)
            self._apply_description_to_ui(kp_id, "")
            return

        description = await self._fetch_ia_description(archive_id)
        self._apply_description_to_ui(kp_id, description or "")

    async def _fetch_ia_description(self, archive_id: str) -> str:
        url = f"https://archive.org/metadata/{archive_id}"
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()
        except Exception as e:
            log.debug("IA metadata %s: %s", archive_id, e)
            return ""

        meta = data.get("metadata") or {}
        raw = meta.get("description")
        text = _clean_ia_description(raw)
        if text:
            lang = "RU" if _is_cyrillic_dominant(text) else "EN/other"
            log.info(
                "Описание (IA): %s (%d симв., %s)",
                archive_id, len(text), lang,
            )
        return text

    def _apply_description_to_ui(self, kp_id: int, text: str):
        if self.current_movie_id != kp_id:
            return
        try:
            if self.current_movie_metadata is not None:
                self.current_movie_metadata["description"] = text
            self.main_window.details_page.update_description(text)
        except Exception as e:
            log.debug("apply_description_to_ui: %s", e)

    async def _load_cover_for_details(
        self, kp_id: int, title_en: str, title_ru: str, year: str
    ):
        cache_path = os.path.join(str(config.CACHE_DIR), f"{kp_id}.jpg")

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

        archive_id = WhitelistRepository.get_archive_identifier(kp_id)
        if archive_id:
            ok = await self._try_ia_thumbnail(archive_id, cache_path)
            if ok:
                self._apply_cover_to_ui(kp_id, cache_path)
                return

        if not archive_id and (title_en or title_ru):
            found_id = await self._search_archive_identifier(
                title_en or title_ru, year
            )
            if found_id:
                ok = await self._try_ia_thumbnail(found_id, cache_path)
                if ok:
                    self._apply_cover_to_ui(kp_id, cache_path)
                    return

        if self._kp_enabled() and (kp_id > 0 or title_en):
            ok = await self._try_kp_cover(
                kp_id, title_en or title_ru, year, cache_path
            )
            if ok:
                self._apply_cover_to_ui(kp_id, cache_path)
                return

        log.info("Постер kp_id=%d не найден", kp_id)
        self._notify_cover_failed(kp_id)

    async def _search_archive_identifier(
        self, title: str, year: str
    ) -> str | None:
        query = (title or "").strip()
        if not query:
            return None

        safe = _escape_lucene(query)

        if year and str(year).isdigit():
            q = (
                f'title:("{safe}") AND '
                f'year:[{int(year) - 1} TO {int(year) + 1}] AND '
                f'mediatype:(movies)'
            )
        else:
            q = f'title:("{safe}") AND mediatype:(movies)'

        url = "https://archive.org/advancedsearch.php"
        params = [
            ("q", q),
            ("fl[]", "identifier"),
            ("rows", "5"),
            ("output", "json"),
            ("sort[]", "downloads desc"),
        ]
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                url, params=params, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except Exception as e:
            log.debug("IA search fallback: %s", e)
            return None

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return None
        identifier = docs[0].get("identifier") or None
        if identifier:
            log.info("IA search: '%s' → %s", query, identifier)
        return identifier

    def _apply_cover_to_ui(self, kp_id: int, cover_path: str | None):
        if self.current_movie_id != kp_id:
            return
        if cover_path and not os.path.exists(cover_path):
            return
        try:
            if cover_path and self.current_movie_metadata is not None:
                self.current_movie_metadata["cover_path"] = cover_path
            self.main_window.details_page.update_cover(cover_path)
        except Exception as e:
            log.debug("apply_cover_to_ui: %s", e)

    def _notify_cover_failed(self, kp_id: int):
        if self.current_movie_id != kp_id:
            return
        try:
            self.main_window.details_page.update_cover(None)
        except Exception as e:
            log.debug("notify_cover_failed: %s", e)

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
            log.info("Постер (IA): %s (%d B)", archive_id, len(content))
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
        # Проверка схемы: не даём скачивать произвольные протоколы
        if not poster_url.startswith(("https://", "http://")):
            log.warning("KP poster: bad scheme %r", poster_url[:40])
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
                "Постер (KP): kp_id=%d (%d KB)",
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
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []
        return data.get("films") or []

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

    def handle_back_to_feed(self):
        self.main_window.screen_stack.setCurrentIndex(0)
        self.check_resume_island()

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