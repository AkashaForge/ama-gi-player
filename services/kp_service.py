"""
Async KPService с разделённым кэшем и статистикой.

Кэш:
  data/cache/short/{id}.json   — короткие данные (лента, search)
  data/cache/full/{id}.json    — полные данные (детали, imdbId)
  data/cache/lists/{hash}.json — popular/search списки с TTL
  data/cache/{id}.jpg          — постеры

Диагностика:
  - Логи [KP] CACHE HIT / MISS / API CALL
  - get_stats() — словарь со счётчиками за сессию
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
import hashlib
import json
import os
import time
from urllib.parse import quote_plus

import aiohttp

import config
from core.logging_setup import get_logger

log = get_logger("kp")


class KPService:
    def __init__(self):
        self.api_key = getattr(config, "KP_API_KEY", "")
        self.base_url = "https://kinopoiskapiunofficial.tech"
        self.headers = {
            "X-API-KEY": str(self.api_key),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": config.USER_AGENT,
        }

        self.CACHE_SHORT = str(getattr(config, "CACHE_SHORT_DIR", config.CACHE_DIR))
        self.CACHE_FULL = str(getattr(config, "CACHE_FULL_DIR", config.CACHE_DIR))
        self.CACHE_LISTS = str(getattr(config, "CACHE_LISTS_DIR", config.CACHE_DIR))
        self.CACHE_POSTER = str(config.CACHE_DIR)
        for d in (self.CACHE_SHORT, self.CACHE_FULL,
                  self.CACHE_LISTS, self.CACHE_POSTER):
            os.makedirs(d, exist_ok=True)

        self.POPULAR_TTL = getattr(config, "POPULAR_CACHE_TTL_HOURS", 24) * 3600
        self.SEARCH_TTL = getattr(config, "SEARCH_CACHE_TTL_HOURS", 6) * 3600
        self.SHORT_TTL = getattr(config, "SHORT_CACHE_TTL_HOURS", 24 * 30) * 3600

        self.stats = {
            "short_hits": 0, "short_misses": 0,
            "full_hits": 0, "full_misses": 0,
            "popular_hits": 0, "popular_misses": 0,
            "search_hits": 0, "search_misses": 0,
            "api_calls": 0, "api_402": 0,
        }

    # ==================================================================
    #  СЛУЖЕБНОЕ
    # ==================================================================
    def _has_key(self):
        return bool(self.api_key)

    def _poster_path(self, kp_id: int) -> str:
        return os.path.join(self.CACHE_POSTER, f"{kp_id}.jpg")

    def _short_path(self, kp_id: int) -> str:
        return os.path.join(self.CACHE_SHORT, f"{kp_id}.json")

    def _full_path(self, kp_id: int) -> str:
        return os.path.join(self.CACHE_FULL, f"{kp_id}.json")

    def _list_path(self, key: str) -> str:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.CACHE_LISTS, f"{h}.json")

    @staticmethod
    def _read_json(path: str) -> dict | None:
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Битый кэш %s: %s", path, e)
            return None

    @staticmethod
    def _write_json(path: str, data: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("Кэш не записан %s: %s", path, e)

    @staticmethod
    def _is_fresh(path: str, ttl_sec: int) -> bool:
        if not os.path.exists(path):
            return False
        try:
            age = time.time() - os.path.getmtime(path)
            return age < ttl_sec
        except Exception:
            return False

    # ==================================================================
    #  HTTP
    # ==================================================================
    async def _get_json(self, session, url):
        self.stats["api_calls"] += 1
        call_num = self.stats["api_calls"]
        log.info("[KP] API CALL #%d %s", call_num, url)
        try:
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            async with session.get(url, headers=self.headers,
                                    timeout=timeout) as resp:
                if resp.status == 402:
                    self.stats["api_402"] += 1
                    log.warning("[KP] API CALL #%d → 402 (лимит)", call_num)
                    return None
                if resp.status != 200:
                    log.warning("[KP] API CALL #%d → HTTP %d", call_num, resp.status)
                    return None
                try:
                    return await resp.json()
                except Exception as e:
                    log.warning("[KP] JSON %s", e)
                    return None
        except asyncio.TimeoutError:
            log.warning("[KP] API CALL #%d → timeout", call_num)
            return None
        except Exception as e:
            log.warning("[KP] API CALL #%d → %s", call_num, e)
            return None

    # ==================================================================
    #  ПОСТЕР (скачивание)
    # ==================================================================
    async def _download_poster(self, session, kp_id: int,
                                poster_url: str) -> str:
        """Скачивает постер, если его нет. Возвращает локальный путь или ''."""
        if not poster_url:
            return ""
        local = self._poster_path(kp_id)
        if os.path.exists(local):
            return local
        try:
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            async with session.get(poster_url, timeout=timeout) as r:
                if r.status == 200:
                    content = await r.read()
                    with open(local, "wb") as f:
                        f.write(content)
                    return local
        except Exception as e:
            log.warning("Постер %d: %s", kp_id, e)
        return ""

    # ==================================================================
    #  СПИСКИ (popular / search) — кэш с TTL
    # ==================================================================
    async def get_popular_movies(self, session, page=1):
        if not self._has_key():
            return []
        cache_key = f"popular_page_{page}"
        path = self._list_path(cache_key)

        if self._is_fresh(path, self.POPULAR_TTL):
            data = self._read_json(path)
            if data and data.get("items"):
                self.stats["popular_hits"] += 1
                log.info("[KP] CACHE HIT popular page=%d", page)
                return self._hydrate_items(data["items"])

        self.stats["popular_misses"] += 1
        url = (f"{self.base_url}/api/v2.2/films/collections"
               f"?type=TOP_POPULAR_MOVIES&page={page}")
        data = await self._get_json(session, url)
        if not data:
            return []
        items = data.get("items") or data.get("films") or []
        self._write_json(path, {"items": items, "ts": time.time()})
        return self._hydrate_items(items)

    async def search_movies_by_keyword(self, session, query, page=1):
        if not self._has_key() or not query.strip():
            return []
        q = query.strip()
        cache_key = f"search_{q.lower()}_p{page}"
        path = self._list_path(cache_key)

        if self._is_fresh(path, self.SEARCH_TTL):
            data = self._read_json(path)
            if data and data.get("items") is not None:
                self.stats["search_hits"] += 1
                log.info("[KP] CACHE HIT search '%s' page=%d", q, page)
                return self._hydrate_items(data["items"])

        self.stats["search_misses"] += 1
        encoded = quote_plus(q)
        url = (f"{self.base_url}/api/v2.1/films/search-by-keyword"
               f"?keyword={encoded}&page={page}")
        data = await self._get_json(session, url)
        if not data:
            return []
        items = data.get("films") or []
        self._write_json(path, {"items": items, "ts": time.time()})
        return self._hydrate_items(items)

    # ==================================================================
    #  ПРЕВРАЩЕНИЕ items → список словарей для ленты
    # ==================================================================
    def _hydrate_items(self, items: list) -> list[dict]:
        """
        Из сырых items KP делает карточки для ленты.
        Пишет short-кэш, если его нет. НЕ скачивает постеры (это в фоне).
        """
        result = []
        for item in items:
            kp_id = item.get("kinopoiskId") or item.get("filmId")
            if not kp_id:
                continue

            short_path = self._short_path(kp_id)
            short_data = self._read_json(short_path)

            if short_data and short_data.get("_complete_short"):
                self.stats["short_hits"] += 1
                result.append(self._finalize_card(short_data, kp_id))
                continue

            # Пишем/обновляем short-кэш
            self.stats["short_misses"] += 1
            title_ru = (item.get("nameRu") or item.get("nameOriginal")
                        or "Без названия")
            title_en = item.get("nameOriginal") or item.get("nameEn") or ""
            card = {
                "kp_id": kp_id,
                "title": str(title_ru),
                "title_en": str(title_en),
                "year": str(item.get("year") or "----"),
                "description": str(
                    item.get("description")
                    or "Описание доступно на экране деталей."
                ),
                "poster_url": (item.get("posterUrlPreview")
                               or item.get("posterUrl")),
                "imdbId": "",
                "_complete_short": True,
                "_ts": time.time(),
            }
            self._write_json(short_path, card)
            result.append(self._finalize_card(card, kp_id))
        return result

    def _finalize_card(self, card: dict, kp_id: int) -> dict:
        """Обогащает карточку путём к постеру (только если файл существует)."""
        out = dict(card)
        out["kp_id"] = kp_id
        out["title_en"] = str(out.get("title_en") or "")
        out.setdefault("imdbId", "")
        poster = self._poster_path(kp_id)
        out["cover_path"] = poster if os.path.exists(poster) else ""
        out.pop("_ts", None)
        out.pop("_complete_short", None)
        return out

    # ==================================================================
    #  ПОЛНАЯ КАРТОЧКА (детали)
    # ==================================================================
    async def get_movie_data(self, session, kp_id):
        try:
            clean_id = int(kp_id)
        except (ValueError, TypeError):
            return {"kp_id": kp_id, "title": "?", "title_en": "",
                    "year": "----", "description": "",
                    "cover_path": "", "imdbId": ""}

        full_path = self._full_path(clean_id)

        # 1) Full-кэш (свежий)
        if self._is_fresh(full_path, self.SHORT_TTL):
            data = self._read_json(full_path)
            if data and data.get("_complete_full"):
                self.stats["full_hits"] += 1
                log.info("[KP] CACHE HIT full kp_id=%d", clean_id)
                return self._finalize_card(data, clean_id)

        # 2) Есть только short — берём как основу, но нужен доп. запрос
        short_path = self._short_path(clean_id)
        short_data = self._read_json(short_path)

        # 3) API
        self.stats["full_misses"] += 1
        url = f"{self.base_url}/api/v2.2/films/{clean_id}"
        data = await self._get_json(session, url)

        if not data:
            # API не ответил: если есть short — вернём его (без imdbId, но играбельно)
            if short_data:
                log.info("[KP] API недоступен, отдаю short-кэш kp_id=%d", clean_id)
                return self._finalize_card(short_data, clean_id)
            return {
                "kp_id": clean_id,
                "title": (short_data.get("title") if short_data else f"Фильм {clean_id}"),
                "title_en": (short_data.get("title_en") if short_data else ""),
                "year": (short_data.get("year") if short_data else "----"),
                "description": "Не удалось получить данные.",
                "cover_path": "",
                "imdbId": "",
            }

        title_ru = (data.get("nameRu") or data.get("nameOriginal")
                    or (short_data.get("title") if short_data else "Без названия"))
        title_en = (data.get("nameOriginal") or data.get("nameEn")
                    or (short_data.get("title_en") if short_data else ""))
        poster_url = (data.get("posterUrlPreview") or data.get("posterUrl")
                      or (short_data.get("poster_url") if short_data else ""))

        movie_dict = {
            "kp_id": clean_id,
            "title": str(title_ru),
            "title_en": str(title_en),
            "year": str(data.get("year") or "----"),
            "description": str(data.get("description") or "Описание отсутствует."),
            "poster_url": poster_url,
            "imdbId": data.get("imdbId") or "",
            "_complete_full": True,
            "_ts": time.time(),
        }
        self._write_json(full_path, movie_dict)

        return self._finalize_card(movie_dict, clean_id)

    # ==================================================================
    #  СТАТИСТИКА
    # ==================================================================
    def get_stats(self) -> dict:
        return dict(self.stats)

    def log_stats(self) -> None:
        s = self.stats
        log.info(
            "[KP-STATS] API=%d (402=%d) | short H/M=%d/%d | "
            "full H/M=%d/%d | popular H/M=%d/%d | search H/M=%d/%d",
            s["api_calls"], s["api_402"],
            s["short_hits"], s["short_misses"],
            s["full_hits"], s["full_misses"],
            s["popular_hits"], s["popular_misses"],
            s["search_hits"], s["search_misses"],
        )