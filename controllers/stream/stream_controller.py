"""StreamController — координатор. ~150 строк."""
import asyncio

from controllers.stream.buffer_monitor import BufferMonitor
from controllers.stream.cascade import CascadeExecutor
from controllers.stream.fallback import FallbackHandler
from core.logging_setup import get_logger

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
        self.libtorrent_session = getattr(app, "libtorrent_session", None)
        self.balancer_client = getattr(app, "balancer_client", None)

        self.stream_session = None
        self.stream_in_progress = False
        self._current_movie_id = None
        self._current_movie_title = ""
        self._current_year = ""

        # Fallback-состояние
        self._online_sources: list[dict] = []
        self._p2p_fallback: list[dict] = []
        self._direct_fallback: list[dict] = []

        # Компоненты
        self.buffer = BufferMonitor(
            self.main_window, self.playback,
            on_fallback=self._on_buffer_fallback,
        )
        self.fallback = FallbackHandler(self)
        self.cascade = CascadeExecutor(self)

        self._connect_signals()

    def _connect_signals(self):
        try:
            self.main_window.player_page.skip_requested.connect(self._on_skip)
        except Exception as e:
            log.debug("skip connect: %s", e)
        try:
            self.main_window.player_page.source_selected.connect(
                self._on_source_selected
            )
        except Exception as e:
            log.debug("source_selected connect: %s", e)
        try:
            self.playback.demux_error.connect(self._on_demux_error)
        except Exception:
            pass

    # ==================================================================
    #  PUBLIC API
    # ==================================================================
    def handle_stream_start(self, kp_id: int):
        log.info("Старт стрима kp_id=%s", kp_id)
        if self.stream_in_progress:
            return
        meta = self.app.details.current_movie_metadata
        if not meta or meta.get("kp_id") != kp_id:
            self.app.details.open(kp_id)
            return

        self.stream_in_progress = True
        self._current_movie_id = kp_id
        self._current_movie_title = meta.get("title", "Без названия")
        self._current_year = (meta.get("year") or "").strip()
        self.fallback.reset()
        self._online_sources = []
        self._p2p_fallback = []
        self._direct_fallback = []

        self.main_window.screen_stack.setCurrentIndex(2)
        self.main_window.player_page.show_loader()
        self.main_window.player_page.p2p_progress.setValue(0)
        self.main_window.player_page.loader_label.setText("ПОИСК ПОТОКОВ...")
        self.loop.create_task(self.cascade.execute(
            meta, self._current_movie_id,
            self._current_movie_title, self._current_year,
        ))

    def handle_close_player(self, _seconds):
        log.info("Закрытие плеера")
        if self.playback:
            self.playback.stop_and_save()
        self.loop.create_task(self._stop_resources())
        self.stream_in_progress = False
        self.fallback.reset()
        self._online_sources = []
        self.main_window.screen_stack.setCurrentIndex(0)
        self.app.details.check_resume_island()

    async def stop_all(self):
        await self._stop_resources()

    # ==================================================================
    #  CALLBACKS от StreamSession
    # ==================================================================
    def on_ready(self, session):
        if not session.http_server:
            self.on_failed("HTTP server не создан")
            return
        # Запускаем HTTP-сервер (в новом StreamSession это отложено)
        self.loop.create_task(self._start_http_and_play(session))

    async def _start_http_and_play(self, session):
        url = await session.http_server.start()
        log.info("Стрим готов: %s", url)
        session._ready = True
        session.monitor.start()
        self.playback.play_url(
            url, self._current_movie_id, self._current_movie_title
        )
        self.buffer.start_p2p(lambda: self.stream_session)

    def on_failed(self, err: str):
        log.error("FAILED: %s", err)
        self.stream_in_progress = False
        self.buffer.stop()
        if self.stream_session:
            self.loop.create_task(self.stream_session.cancel())
            self.stream_session = None
        self.main_window.player_page.loader_label.setText(f"ОШИБКА: {err}")

    def _update_bar(self, progress_str: str, speed_str: str):
        try:
            if "%" in progress_str:
                percent = progress_str.split("%")[0].strip()
                self.main_window.player_page.set_buffering_progress(
                    int(float(percent))
                )
        except Exception:
            pass
        self.main_window.player_page.loader_label.setText(
            f"{progress_str} | {speed_str}"
        )

    # ==================================================================
    #  КНОПКИ
    # ==================================================================
    def _on_skip(self):
        self.loop.create_task(self._do_skip())

    async def _do_skip(self):
        log.info("Skip")
        if self.app.LEGAL_ONLY_MODE:
            self.main_window.player_page.loader_label.setText(
                "В public-версии альтернатив нет."
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
        self.stream_in_progress = False
        self.fallback.reset()
        if alternatives:
            self.main_window.player_page.show_source_picker(alternatives)
        else:
            self.main_window.player_page.loader_label.setText("Нет альтернатив")

    def _on_source_selected(self, source: dict):
        self.loop.create_task(self._do_select(source))

    async def _do_select(self, source: dict):
        log.info("Alternative: %s", (source.get("title") or "")[:60])
        await self._stop_resources()
        if not self.libtorrent_session:
            self.on_failed("Libtorrent session не инициализирован")
            return
        self.stream_in_progress = True
        self.fallback.reset()
        self.main_window.player_page.show_loader()
        self.main_window.player_page.loader_label.setText("ПОДКЛЮЧЕНИЕ...")
        self.stream_session = self._create_session()
        await self.stream_session.start([source], year=self._current_year)

    def _create_session(self):
        from services.torrent.session import StreamSession
        import config as _c
        return StreamSession(
            http_session=self.session,
            downloads_dir=str(_c.DOWNLOADS_DIR),
            libtorrent_session=self.libtorrent_session,
            progress_cb=self._update_bar,
            finished_cb=self.on_ready,
            failed_cb=self.on_failed,
        )

    # ==================================================================
    #  DEMUX / BUFFER
    # ==================================================================
    def _on_demux_error(self):
        self.fallback.on_demux_error()

    def _on_buffer_fallback(self, force: bool):
        self.buffer.stop()
        if force:
            self.fallback.do_auto_fallback()
        else:
            # online не заиграл — переключиться на p2p
            self.loop.create_task(self._online_to_p2p())

    async def _online_to_p2p(self):
        log.info("Online → p2p")
        self._online_sources = []
        if self._p2p_fallback and self.libtorrent_session:
            self.stream_in_progress = True
            self.stream_session = self._create_session()
            await self.stream_session.start(
                self._p2p_fallback, year=self._current_year
            )
            return
        if self._direct_fallback:
            self._direct_fallback.sort(
                key=lambda s: s.get("size", 0) or 0, reverse=True
            )
            chosen = self._direct_fallback[0]
            self.playback.play_url(
                chosen["url"], self._current_movie_id,
                self._current_movie_title,
            )
            return
        self.main_window.player_page.loader_label.setText(
            "ОНЛАЙН НЕ РАБОТАЕТ, ТОРРЕНТОВ НЕТ"
        )

    async def _stop_resources(self):
        self.buffer.stop()
        if self.stream_session:
            try:
                await self.stream_session.cancel()
            except Exception as e:
                log.debug("cancel: %s", e)
            self.stream_session = None