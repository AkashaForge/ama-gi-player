"""CascadeExecutor — выполняет поиск и запускает поток."""
import asyncio
import time

import aiohttp

import config
from core.logging_setup import get_logger
from search.aggregator import find_torrent_stream
from services.torrent.session import StreamSession
from services.torrent.tracker_balancer import TrackerBalancer

log = get_logger("stream.cascade")


class CascadeExecutor:
    def __init__(self, controller):
        self.controller = controller
        self.loop = controller.loop
        self.main_window = controller.main_window
        self.playback = controller.playback

    async def execute(self, meta: dict, movie_id: int,
                       movie_title: str, year: str):
        c = self.controller
        if not c.session:
            self.main_window.player_page.loader_label.setText("СЕТЬ НЕ ГОТОВА")
            c.stream_in_progress = False
            return

        try:
            title_ru = (meta.get("title") or "").strip()
            kp_id = meta.get("kp_id") or meta.get("kinopoiskId")
            imdb_id = str(meta.get("imdbId") or "").strip()
            title_en = str(meta.get("nameOriginal")
                           or meta.get("title_en") or "").strip()

            if not imdb_id and kp_id and kp_id > 0:
                imdb_id, title_en = await self._fetch_imdb(kp_id, title_en)
            if title_en == "----" or title_en == title_ru:
                title_en = ""

            log.info("IDs: RU='%s' EN='%s' YEAR='%s' IMDb='%s'",
                     title_ru, title_en, year, imdb_id)

            extra_trackers = await self._load_trackers()

            sources, ui_msg = await find_torrent_stream(
                tracker_client=c.app.jackett or c.app.prowlarr,
                web_fetcher=c.web_fetcher,
                archive_org=c.archive_org,
                session=c.session,
                balancer_client=c.balancer_client,
                title_ru=title_ru,
                title_en=title_en,
                year=year,
                imdb_id=imdb_id,
                language=config.SEARCH_LANGUAGE,
                yts_client=getattr(c.app, "yts_client", None),
                extra_trackers=extra_trackers,
            )

            if not sources:
                self.main_window.player_page.loader_label.setText(ui_msg)
                c.stream_in_progress = False
                await asyncio.sleep(3.0)
                if self.main_window.screen_stack.currentIndex() == 2:
                    self.main_window.screen_stack.setCurrentIndex(1)
                return

            await self._dispatch(sources, movie_id, movie_title, year)

        except Exception as e:
            log.exception("Cascade: %s", e)
            c.on_failed(str(e))

    async def _load_trackers(self) -> list[str]:
        try:
            balancer = TrackerBalancer()
            return await balancer.get_trackers()
        except Exception as e:
            log.debug("TrackerBalancer: %s", e)
            return []

    async def _dispatch(self, sources, movie_id, movie_title, year):
        c = self.controller
        online = [
            s for s in sources
            if s.get("indexer") in ("balancer", "videocdn", "bwa")
        ]
        p2p = [s for s in sources if s.get("type") in ("magnet", "torrent_url")]
        direct = [
            s for s in sources
            if s.get("type") == "direct_url"
            and s.get("indexer") not in ("balancer", "videocdn", "bwa")
        ]

        log.info("Источники: online=%d, p2p=%d, direct=%d",
                 len(online), len(p2p), len(direct))

        c._online_sources = online
        c._p2p_fallback = p2p
        c._direct_fallback = direct

        # 1. Online
        if online:
            chosen = online[0]
            log.info("ONLINE: %s (%.1f MB) — '%s' (%s)",
                     chosen["url"][:80],
                     (chosen.get("size", 0) or 0) / 1024 / 1024,
                     (chosen.get("title") or "")[:60],
                     chosen.get("indexer", "?"))
            self.main_window.player_page.set_buffering_progress(100)
            c.stream_in_progress = False
            self.playback.play_url(chosen["url"], movie_id, movie_title)
            c.buffer.start_online()
            return

        # 2. Public
        if config.LEGAL_ONLY_MODE:
            if not direct:
                self.main_window.player_page.loader_label.setText(
                    "ФИЛЬМ НЕ НАЙДЕН В INTERNET ARCHIVE"
                )
                c.stream_in_progress = False
                await asyncio.sleep(3.0)
                if self.main_window.screen_stack.currentIndex() == 2:
                    self.main_window.screen_stack.setCurrentIndex(1)
                return
            direct.sort(key=lambda s: s.get("size", 0) or 0, reverse=True)
            chosen = direct[0]
            log.info("PUBLIC: %s", chosen["url"][:80])
            self.main_window.player_page.set_buffering_progress(100)
            c.stream_in_progress = False
            self.playback.play_url(chosen["url"], movie_id, movie_title)
            return

        # 3. Private: P2P
        if p2p:
            await c._stop_resources()
            if not c.libtorrent_session:
                c.on_failed("Libtorrent session не инициализирован")
                return
            c.stream_session = StreamSession(
                http_session=c.session,
                downloads_dir=str(config.DOWNLOADS_DIR),
                libtorrent_session=c.libtorrent_session,
                progress_cb=c._update_bar,
                finished_cb=c.on_ready,
                failed_cb=c.on_failed,
            )
            await c.stream_session.start(p2p, year=year)
            return

        # 4. Direct
        if direct:
            direct.sort(key=lambda s: s.get("size", 0) or 0, reverse=True)
            chosen = direct[0]
            log.info("PRIVATE (no p2p): %s", chosen["url"][:80])
            self.main_window.player_page.set_buffering_progress(100)
            c.stream_in_progress = False
            self.playback.play_url(chosen["url"], movie_id, movie_title)
            return

        self.main_window.player_page.loader_label.setText("НЕТ ИСТОЧНИКОВ")
        c.stream_in_progress = False

    async def _fetch_imdb(self, kp_id: int, title_en: str) -> tuple[str, str]:
        c = self.controller
        try:
            url = f"https://kinopoiskapiunofficial.tech/api/v2.2/films/{kp_id}"
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            async with c.session.get(
                url, headers={"X-API-KEY": config.KP_API_KEY},
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    return "", title_en
                data = await resp.json()
                imdb_id = str(data.get("imdbId") or "").strip()
                if not title_en:
                    title_en = str(
                        data.get("nameOriginal")
                        or data.get("nameEn") or ""
                    ).strip()
                return imdb_id, title_en
        except Exception as e:
            log.warning("IMDb: %s", e)
            return "", title_en