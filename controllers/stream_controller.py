"""
Контроллер P2P-стрима.

Public mode: только direct_url (archive.org) → play_url напрямую
Private mode: p2p → StreamSession, direct_url → play_url
"""

import asyncio
import time

import aiohttp
from PyQt6.QtCore import QTimer

import config
from core.logging_setup import get_logger
from search.aggregator import find_torrent_stream
from services.torrent.stream_session import StreamSession

log = get_logger("stream")


class StreamController:
    def __init__(self, app):
        self.app = app
        self.loop = app.loop
        self.main_window = app.main_window
        self.playback = app.playback
        self.session = app.session
        self.web_fetcher = app.web_fetcher
        self.archive_org = app.archive_org
        self.libtorrent_session = getattr(app, 'libtorrent_session', None)

        self.stream_session: StreamSession | None = None
        self._stream_in_progress = False
        self._current_movie_id = None
        self._current_movie_title = ""
        self._current_year = ""

        self._buffer_timer = None
        self._buffer_stopped = False
        self._buffer_pending_since = None
        self._last_demux_error_ts = 0.0

        self.BUFFER_STOP_DELAY = getattr(config, "STREAM_BUFFER_STOP_DELAY_SEC", 30.0)
        self.MONITOR_INTERVAL_MS = getattr(config, "STREAM_MONITOR_INTERVAL_MS", 1000)
        self.DEMUX_COOLDOWN_SEC = getattr(config, "STREAM_DEMUX_ERROR_COOLDOWN_SEC", 1.0)

        try:
            self.main_window.player_page.skip_requested.connect(self._on_skip)
        except Exception as e:
            log.debug("connect skip_requested: %s", e)

        try:
            self.main_window.player_page.source_selected.connect(self._on_source_selected)
        except Exception as e:
            log.debug("connect source_selected: %s", e)

        try:
            self.playback.demux_error.connect(self._on_demux_error)
        except Exception as e:
            log.debug("connect demux_error: %s", e)

    def handle_stream_start(self, kp_id: int):
        log.info("Старт стрима kp_id=%s", kp_id)
        if self._stream_in_progress:
            return
        meta = self.app.details.current_movie_metadata
        if not meta or meta.get("kp_id") != kp_id:
            self.app.details.open(kp_id)
            return

        self._stream_in_progress = True
        self._current_movie_id = kp_id
        self._current_movie_title = meta.get("title", "Без названия")
        self._current_year = (meta.get("year") or "").strip()

        self.main_window.screen_stack.setCurrentIndex(2)
        self.main_window.player_page.show_loader()
        self.main_window.player_page.p2p_progress.setValue(0)
        self.main_window.player_page.loader_label.setText("ПОИСК ПОТОКОВ...")
        self.loop.create_task(self._execute_cascade(meta))

    async def _execute_cascade(self, meta: dict):
        if not self.session:
            self.main_window.player_page.loader_label.setText("СЕТЬ НЕ ГОТОВА")
            self._stream_in_progress = False
            return

        try:
            title_ru = (meta.get("title") or "").strip()
            year = (meta.get("year") or "").strip()
            kp_id = meta.get("kp_id") or meta.get("kinopoiskId")
            imdb_id = str(meta.get("imdbId") or "").strip()
            title_en = str(meta.get("nameOriginal") or meta.get("title_en") or "").strip()

            if not imdb_id and kp_id and kp_id > 0:
                imdb_id, title_en = await self._fetch_imdb(kp_id, title_en)

            if title_en == "----" or title_en == title_ru:
                title_en = ""

            log.info("Идентификаторы: RU='%s', EN='%s', YEAR='%s', IMDb='%s'",
                     title_ru, title_en, year, imdb_id)

            sources, ui_msg = await find_torrent_stream(
                tracker_client=self.app.jackett or self.app.prowlarr,
                web_fetcher=self.web_fetcher,
                archive_org=self.archive_org,
                session=self.session,
                title_ru=title_ru,
                title_en=title_en,
                year=year,
                imdb_id=imdb_id,
                language=config.SEARCH_LANGUAGE,
                yts_client=getattr(self.app, 'yts_client', None),
            )

            if not sources:
                self.main_window.player_page.loader_label.setText(ui_msg)
                self._stream_in_progress = False
                await asyncio.sleep(3.0)
                if self.main_window.screen_stack.currentIndex() == 2:
                    self.main_window.screen_stack.setCurrentIndex(1)
                return

            p2p = [s for s in sources if s.get("type") in ("magnet", "torrent_url")]
            direct = [s for s in sources if s.get("type") == "direct_url"]

            log.info(
                "Источники: p2p=%d, direct=%d (mode=%s)",
                len(p2p), len(direct),
                "public" if getattr(config, "LEGAL_ONLY_MODE", True) else "private",
            )

            # ============================================================
            # PUBLIC MODE: только direct_url (archive.org)
            # ============================================================
            if getattr(config, "LEGAL_ONLY_MODE", True):
                if not direct:
                    self.main_window.player_page.loader_label.setText(
                        "ФИЛЬМ НЕ НАЙДЕН В INTERNET ARCHIVE"
                    )
                    self._stream_in_progress = False
                    await asyncio.sleep(3.0)
                    if self.main_window.screen_stack.currentIndex() == 2:
                        self.main_window.screen_stack.setCurrentIndex(1)
                    return

                # Выбираем самый большой файл (лучшее качество)
                direct.sort(key=lambda s: s.get("size", 0) or 0, reverse=True)
                chosen = direct[0]
                log.info(
                    "PUBLIC: play_url %s (%.1f MB) — '%s'",
                    chosen["url"][:80],
                    (chosen.get("size", 0) or 0) / 1024 / 1024,
                    (chosen.get("title") or "")[:60],
                )
                self.main_window.player_page.set_buffering_progress(100)
                self._stream_in_progress = False
                self.playback.play_url(
                    chosen["url"],
                    self._current_movie_id,
                    self._current_movie_title,
                )
                return

            # ============================================================
            # PRIVATE MODE: p2p приоритет, direct как fallback
            # ============================================================
            if p2p:
                await self._stop_resources()
                if not self.libtorrent_session:
                    self._on_failed("Libtorrent session не инициализирован")
                    return
                self.stream_session = StreamSession(
                    http_session=self.session,
                    downloads_dir=str(config.DOWNLOADS_DIR),
                    libtorrent_session=self.libtorrent_session,
                    progress_cb=self._update_bar,
                    finished_cb=self._on_ready,
                    failed_cb=self._on_failed,
                )
                await self.stream_session.start(p2p, year=year)
                return

            if direct:
                direct.sort(key=lambda s: s.get("size", 0) or 0, reverse=True)
                chosen = direct[0]
                log.info(
                    "PRIVATE (no p2p): play_url %s",
                    chosen["url"][:80],
                )
                self.main_window.player_page.set_buffering_progress(100)
                self._stream_in_progress = False
                self.playback.play_url(
                    chosen["url"],
                    self._current_movie_id,
                    self._current_movie_title,
                )
                return

            self.main_window.player_page.loader_label.setText("НЕТ ИСТОЧНИКОВ")
            self._stream_in_progress = False

        except Exception as e:
            log.exception("Каскад: %s", e)
            self._on_failed(str(e))

    async def _fetch_imdb(self, kp_id: int, title_en: str) -> tuple[str, str]:
        try:
            url = f"https://kinopoiskapiunofficial.tech/api/v2.2/films/{kp_id}"
            timeout = aiohttp.ClientTimeout(total=config.NETWORK_TIMEOUT)
            async with self.session.get(
                url, headers={"X-API-KEY": config.KP_API_KEY}, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    return "", title_en
                data = await resp.json()
                imdb_id = str(data.get("imdbId") or "").strip()
                if not title_en:
                    title_en = str(data.get("nameOriginal") or data.get("nameEn") or "").strip()
                return imdb_id, title_en
        except Exception as e:
            log.warning("IMDb: %s", e)
            return "", title_en

    # ==================================================================
    #  CALLBACKS StreamSession (private mode)
    # ==================================================================
    def _on_ready(self, session: StreamSession):
        if not session.http_server:
            self._on_failed("HTTP server не создан")
            return
        url = f"http://127.0.0.1:{session.http_server.port}/stream"
        log.info("Стрим готов: %s", url)
        self.playback.play_url(url, self._current_movie_id, self._current_movie_title)
        self._start_buffer_monitor()

    def _on_failed(self, err: str):
        log.error("FAILED: %s", err)
        self._stream_in_progress = False
        self._stop_buffer_monitor()
        if self.stream_session:
            self.loop.create_task(self.stream_session.cancel())
            self.stream_session = None
        self.main_window.player_page.loader_label.setText(f"ОШИБКА: {err}")

    def _update_bar(self, progress_str: str, speed_str: str):
        try:
            if "%" in progress_str:
                percent = progress_str.split("%")[0].strip()
                self.main_window.player_page.set_buffering_progress(int(float(percent)))
        except Exception:
            pass
        self.main_window.player_page.loader_label.setText(
            f"{progress_str} | {speed_str}"
        )

    # ==================================================================
    #  SKIP
    # ==================================================================
    def _on_skip(self):
        self.loop.create_task(self._do_skip())

    async def _do_skip(self):
        log.info("Пользователь запросил скип")
        if getattr(config, "LEGAL_ONLY_MODE", True):
            # В public нет альтернатив (только archive.org)
            self.main_window.player_page.loader_label.setText(
                "В public-версии альтернатив нет. Попробуйте другой фильм."
            )
            return

        if not self.stream_session:
            return
        alternatives = list(self.stream_session.alternatives)
        try:
            self.playback.player.stop()
        except Exception:
            pass
        await self._stop_resources()
        self._stream_in_progress = False
        if alternatives:
            self.main_window.player_page.show_source_picker(alternatives)
        else:
            self.main_window.player_page.loader_label.setText("Нет альтернатив")

    def _on_source_selected(self, source: dict):
        self.loop.create_task(self._do_select(source))

    async def _do_select(self, source: dict):
        log.info("Пользователь выбрал альтернативу: %s",
                 (source.get("title") or "")[:60])
        await self._stop_resources()
        if not self.libtorrent_session:
            self._on_failed("Libtorrent session не инициализирован")
            return
        self._stream_in_progress = True
        self.main_window.player_page.show_loader()
        self.main_window.player_page.loader_label.setText("ПОДКЛЮЧЕНИЕ...")
        self.stream_session = StreamSession(
            http_session=self.session,
            downloads_dir=str(config.DOWNLOADS_DIR),
            libtorrent_session=self.libtorrent_session,
            progress_cb=self._update_bar,
            finished_cb=self._on_ready,
            failed_cb=self._on_failed,
        )
        await self.stream_session.start([source], year=self._current_year)

    # ==================================================================
    #  BUFFER MONITOR (только private mode / StreamSession)
    # ==================================================================
    def _start_buffer_monitor(self):
        if self._buffer_timer is not None:
            try:
                self._buffer_timer.stop()
            except Exception:
                pass
        self._buffer_timer = QTimer(self.main_window)
        self._buffer_timer.setInterval(self.MONITOR_INTERVAL_MS)
        self._buffer_timer.timeout.connect(self._check_buffering)
        self._buffer_timer.start()
        self._buffer_stopped = False
        self._buffer_pending_since = None
        log.info("Buffer monitor запущен (%dms)", self.MONITOR_INTERVAL_MS)

    def _stop_buffer_monitor(self):
        if self._buffer_timer is not None:
            try:
                self._buffer_timer.stop()
            except Exception:
                pass
            self._buffer_timer = None
        self._buffer_stopped = False
        self._buffer_pending_since = None

    def _check_buffering(self):
        if not self.stream_session or not self.playback:
            return
        try:
            buffering = self.stream_session.is_buffering()
            stats = self.stream_session.stats
        except Exception:
            return

        if buffering and not self._buffer_stopped:
            if self._buffer_pending_since is None:
                self._buffer_pending_since = time.time()
            self.main_window.player_page.loader_label.setText(
                f"БУФЕРИЗАЦИЯ | {stats.connected_peers} пиров | "
                f"{stats.payload_rate / 1024 / 1024:.2f} MB/s"
            )
            if time.time() - self._buffer_pending_since > self.BUFFER_STOP_DELAY:
                log.warning("UI: буферизация %.0fs+ — stop",
                            self.BUFFER_STOP_DELAY)
                try:
                    self.playback.player.stop()
                except Exception:
                    pass
                self._buffer_stopped = True
                self._buffer_pending_since = None
        elif not buffering and self._buffer_stopped:
            log.info("UI: данные пошли — reload")
            try:
                self.playback.reload_url()
            except Exception as e:
                log.warning("reload_url: %s", e)
            self._buffer_stopped = False
            self._buffer_pending_since = None
        elif not buffering:
            self._buffer_pending_since = None

    def _on_demux_error(self):
        now = time.time()
        if now - self._last_demux_error_ts < self.DEMUX_COOLDOWN_SEC:
            return
        self._last_demux_error_ts = now
        log.warning("DEMUX ERROR: stop")
        try:
            self.playback.player.stop()
        except Exception:
            pass
        self._buffer_stopped = True

    async def _stop_resources(self):
        self._stop_buffer_monitor()
        if self.stream_session:
            try:
                await self.stream_session.cancel()
            except Exception as e:
                log.debug("stream_session.cancel: %s", e)
            self.stream_session = None
        self._buffer_stopped = False
        self._buffer_pending_since = None

    def handle_close_player(self, _seconds):
        log.info("Закрытие плеера")
        if self.playback:
            self.playback.stop_and_save()
        self.loop.create_task(self._stop_resources())
        self._stream_in_progress = False
        self.main_window.screen_stack.setCurrentIndex(0)
        self.app.details.check_resume_island()

    async def stop_all(self):
        await self._stop_resources()
