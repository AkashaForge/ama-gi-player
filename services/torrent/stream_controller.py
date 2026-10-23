"""Контроллер P2P-стрима. Использует StreamSession + кнопку «Скипнуть»."""

import config
from core.logging_setup import get_logger
from search.aggregator import find_torrent_stream
from search.yts_client import YTSClient
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

        self.stream_session: StreamSession | None = None
        self._stream_in_progress = False
        self._current_movie_id = None
        self._current_movie_title = ""
        self._current_year = ""

        self.yts_client = YTSClient()
        log.info("YTS client: %s",
                 "enabled" if self.yts_client.is_enabled() else "disabled")
        # Подключение кнопки скипа
        try:
            self.main_window.player_page.skip_requested.connect(self._on_skip)
        except Exception as e:
            log.debug("connect skip_requested: %s", e)

        try:
            self.playback.demux_error.connect(self._on_demux_error)
        except Exception:
            pass

    def handle_stream_start(self, kp_id: int):
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
        self.main_window.player_page.loader_label.setText("ПОИСК P2P-ПОТОКОВ...")
        self.loop.create_task(self._execute_cascade(meta))

    async def _execute_cascade(self, meta: dict):
        try:
            title_ru = (meta.get("title") or "").strip()
            year = (meta.get("year") or "").strip()
            kp_id = meta.get("kp_id") or meta.get("kinopoiskId")
            imdb_id = str(meta.get("imdbId") or "").strip()
            title_en = str(meta.get("nameOriginal") or meta.get("title_en") or "").strip()

            if not imdb_id and kp_id and kp_id > 0:
                imdb_id, title_en = await self._fetch_imdb(kp_id, title_en)

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
                yts_client=self.yts_client,
            )

            if not sources:
                self.main_window.player_page.loader_label.setText(ui_msg)
                self._stream_in_progress = False
                return

            p2p = [s for s in sources if s.get("type") in ("magnet", "torrent_url")]
            if not p2p:
                self._stream_in_progress = False
                return

            await self._stop_resources()
            self.stream_session = StreamSession(
                http_session=self.session,
                downloads_dir=str(config.DOWNLOADS_DIR),
                progress_cb=self._update_bar,
                finished_cb=self._on_ready,
                failed_cb=self._on_failed,
            )
            await self.stream_session.start(p2p, year=year)

        except Exception as e:
            log.exception("Каскад: %s", e)
            self._on_failed(str(e))

    def _on_ready(self, session: StreamSession):
        url = session.http_server and session.http_server._site and None
        # URL уже сохранён в http_server
        stream_url = f"http://127.0.0.1:{session.http_server.port}/stream"
        self.playback.play_url(stream_url, self._current_movie_id, self._current_movie_title)
        self._start_buffer_monitor()

    def _on_failed(self, err: str):
        self._stream_in_progress = False
        self.main_window.player_page.loader_label.setText(f"ОШИБКА: {err}")
        self.loop.create_task(self._stop_resources())

    async def _on_skip(self):
        log.info("Пользователь запросил скип раздачи")
        if not self.stream_session:
            return
        alternatives = self.stream_session.alternatives
        await self._stop_resources()
        if alternatives:
            self.main_window.player_page.show_source_picker(alternatives)
        else:
            self.main_window.player_page.loader_label.setText("Нет альтернативных раздач")

    async def _stop_resources(self):
        if self.stream_session:
            await self.stream_session.cancel()
            self.stream_session = None
        self._stream_in_progress = False

    async def stop_all(self):
        await self._stop_resources()

    # _fetch_imdb, _update_bar, _on_demux_error, _start_buffer_monitor — как раньше,
    # но _check_buffering использует self.stream_session.is_buffering()
