"""StreamController — координатор."""
import asyncio

from PyQt6.QtCore import QTimer

import config
from controllers.stream.buffer_monitor import BufferMonitor
from controllers.stream.cascade import CascadeExecutor
from controllers.stream.fallback import FallbackHandler
from core.logging_setup import get_logger

log = get_logger("stream")

# Таймаут на остановку при закрытии. cancel() yield'ит через
# asyncio.sleep, поэтому wait_for реально сработает.
_CLOSE_STOP_TIMEOUT_SEC = 25.0

# Watchdog: если _closing_in_progress залип дольше — сбрасываем.
_CLOSING_WATCHDOG_MS = 30000

# Задержка между stop_and_save() и cancel() — даём QMediaPlayer
# отпустить file handle на Windows. libtorrent не может удалить
# torrent, пока storage открыт.
_PLAYER_RELEASE_DELAY_MS = 200


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
        self._closing_in_progress = False
        self._pending_start_kp_id = None
        self._current_movie_id = None
        self._current_movie_title = ""
        self._current_year = ""

        # Fallback-состояние
        self._online_sources: list[dict] = []
        self._p2p_fallback: list[dict] = []
        self._direct_fallback: list[dict] = []
        self._direct_index: int = 0

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

        if self._closing_in_progress:
            log.info("Старт отложен: идёт остановка, kp_id=%s", kp_id)
            self._pending_start_kp_id = kp_id
            return
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
        self._direct_index = 0

        self.main_window.screen_stack.setCurrentIndex(2)
        self.main_window.player_page.show_loader()
        self.main_window.player_page.p2p_progress.setValue(0)
        self.main_window.player_page.loader_label.setText("ПОИСК ПОТОКОВ...")
        self.loop.create_task(self.cascade.execute(
            meta, self._current_movie_id,
            self._current_movie_title, self._current_year,
        ))

    def handle_close_player(self, _seconds):
        """Закрытие в 2 фазы.

        Фаза 1: stop_and_save() — QMediaPlayer отпускает file handle.
                На Windows это async внутри QMediaPlayer, но setSource
                стартует процесс.
        Фаза 2 (через 200ms): _start_close_async — запускает cancel()
                стрима. За это время QMediaPlayer обычно отпускает
                file handle, и libtorrent может удалить torrent.
                Без этой паузы async_remove_torrent висит до 30s
                (storage не закрыт).
        """
        log.info("Закрытие плеера")
        self._closing_in_progress = True
        QTimer.singleShot(_CLOSING_WATCHDOG_MS, self._closing_watchdog)

        # Фаза 1: отпускаем file handle
        if self.playback:
            try:
                self.playback.stop_and_save()
            except Exception as e:
                log.debug("stop_and_save: %s", e)

        # Фаза 2: через 200ms — async cancel
        QTimer.singleShot(_PLAYER_RELEASE_DELAY_MS, self._start_close_async)

    def _start_close_async(self):
        self.loop.create_task(self._close_player_async())

    def _closing_watchdog(self):
        if not self._closing_in_progress:
            return
        log.warning("WATCHDOG: _closing_in_progress залип >%dms, сбрасываю",
                    _CLOSING_WATCHDOG_MS)
        self._closing_in_progress = False
        pending = self._pending_start_kp_id
        self._pending_start_kp_id = None
        if pending is not None:
            log.info("WATCHDOG: запуск отложенного старта kp_id=%s", pending)
            self.handle_stream_start(pending)

    async def _close_player_async(self):
        try:
            await asyncio.wait_for(
                self._stop_resources(),
                timeout=_CLOSE_STOP_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            log.warning(
                "close_player: _stop_resources timeout %.0fs",
                _CLOSE_STOP_TIMEOUT_SEC,
            )
        except Exception as e:
            log.debug("close_player stop: %s", e)
        finally:
            self.stream_in_progress = False
            self.fallback.reset()
            self._online_sources = []
            self._p2p_fallback = []
            self._direct_fallback = []
            self._direct_index = 0
            self.main_window.screen_stack.setCurrentIndex(0)
            self.app.details.check_resume_island()
            self._closing_in_progress = False
            log.info("Плеер закрыт, ресурсы освобождены")

            pending = self._pending_start_kp_id
            self._pending_start_kp_id = None
            if pending is not None:
                log.info("Запуск отложенного старта kp_id=%s", pending)
                self.handle_stream_start(pending)

    async def stop_all(self):
        await self._stop_resources()

    # ==================================================================
    #  PUBLIC FALLBACK
    # ==================================================================
    def _player_is_active(self) -> bool:
        try:
            return self.main_window.screen_stack.currentIndex() == 2
        except Exception:
            return False

    def _try_next_direct(self):
        if not self._player_is_active():
            log.info("direct: player not active, skip")
            return

        self._direct_index += 1
        if (not self._direct_fallback
                or self._direct_index >= len(self._direct_fallback)):
            log.warning("direct: все %d источников испробованы",
                        len(self._direct_fallback))
            self.main_window.player_page.loader_label.setText(
                "ИСТОЧНИК НЕ РАБОТАЕТ. Все варианты испробованы."
            )
            return

        chosen = self._direct_fallback[self._direct_index]
        log.info("direct: переключение на %d/%d — %s (priority=%s, %.1f MB)",
                 self._direct_index + 1, len(self._direct_fallback),
                 chosen["url"][:80],
                 chosen.get("priority", "?"),
                 (chosen.get("size", 0) or 0) / 1e6)
        self.main_window.player_page.show_loader()
        self.main_window.player_page.loader_label.setText(
            f"ИСТОЧНИК {self._direct_index + 1}/{len(self._direct_fallback)}..."
        )
        self.fallback.reset()
        self.playback.play_url(
            chosen["url"], self._current_movie_id, self._current_movie_title
        )

    # ==================================================================
    #  P2P CALLBACKS
    # ==================================================================
    def on_ready(self, session):
        if not session.http_server:
            self.on_failed("HTTP server не создан")
            return
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
        """Без QMessageBox и без create_task в этом же тике.

        QMessageBox — вложенный Qt event loop. Если on_failed
        вызван синхронно из StreamSession.start() (внутри
        CascadeExecutor.execute), вложенный цикл пытается крутить
        pending-таски, пока execute() ещё в __step → RuntimeError
        "Cannot enter into task X while another task Y is being
        executed". Откладываем всё на следующий тик.
        """
        log.error("FAILED: %s", err)
        self.stream_in_progress = False
        self.buffer.stop()
        QTimer.singleShot(0, lambda e=err: self._finalize_failure(e))

    def _finalize_failure(self, err: str):
        self.loop.create_task(self._stop_resources())
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
        if config.LEGAL_ONLY_MODE:
            if not self._direct_fallback:
                self.main_window.player_page.loader_label.setText(
                    "Альтернативных источников нет."
                )
                return
            if self._direct_index >= len(self._direct_fallback) - 1:
                log.info("Skip: последний источник, начинаем с первого")
                self._direct_index = -1
            self.fallback.reset()
            self._try_next_direct()
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
        return StreamSession(
            http_session=self.session,
            downloads_dir=str(config.DOWNLOADS_DIR),
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
                key=lambda s: (s.get("priority", 0), s.get("size", 0) or 0),
                reverse=True,
            )
            self._direct_index = 0
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
        """Идемпотентно.

        Отвязываем ссылку ДО await, второй вызов сразу увидит None.
        Это предотвращает двойной await session.cancel() при
        параллельных вызовах (close + cascade._dispatch).
        """
        self.buffer.stop()
        session = self.stream_session
        self.stream_session = None
        if session is not None:
            try:
                await session.cancel()
            except Exception as e:
                log.debug("cancel: %s", e)