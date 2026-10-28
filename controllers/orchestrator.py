"""
Оркестратор. PUBLIC: без Jackett/libtorrent. PRIVATE: полный стек.
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

import aiohttp
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog

import config
from controllers.details_controller import DetailsController
from controllers.feed_controller import FeedController
from controllers.stream_controller import StreamController
from core.logging_setup import get_logger
from database.connection import init_db
from database.whitelist_db import init_whitelist_db
from legal_gate import LegalGateDialog
from search.archive_org_searcher import ArchiveOrgSearcher
from search.jackett_client import JackettClient
from search.prowlarr_client import ProwlarrClient
from search.web_fetcher import WebFetcher
from services.kp_service import KPService
from services.playback_controller import PlaybackController
from services.process_cleaner import (
    cleanup_all,
    cleanup_startup,
)
from ui.main_window import MainWindow
from ui.setup_wizard import P2PInitialSetupWizard

log = get_logger("orchestrator")


class AmagiApplicationOrchestrator:
    def __init__(self, async_loop):
        self.loop = async_loop
        self.manager = None
        self.session: aiohttp.ClientSession | None = None
        self.libtorrent_session = None

        self.backend = None
        self.jackett = None
        self.prowlarr = None
        self.yts_client = None

        self.web_fetcher = WebFetcher()
        self.archive_org = ArchiveOrgSearcher()
        self.kp_service = KPService()

        self.playback = None
        self.main_window = None
        self.feed = None
        self.details = None
        self.stream = None
        self.search_debounce = None
        self._cleanup_timer = None
        self._jackett_ready = False

        log.info("Очистка зомби-процессов и диска...")
        cleanup_startup()

        init_db()
        init_whitelist_db()

    # ==================================================================
    #  СТАРТ
    # ==================================================================
    def start_orchestration(self):
        """
        ВАЖНО: этот метод вызывается ДО loop.run_forever() (см. main.py).
        Поэтому любые действия, требующие running loop (aiohttp.ClientSession,
        asyncio.create_task), должны быть отложены через QTimer.singleShot.
        """
        if not getattr(config, "LEGAL_DISCLAIMER_ACCEPTED", False):
            log.info("Показ дисклеймера...")
            dialog = LegalGateDialog()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                log.info("Пользователь отклонил условия. Выход.")
                QApplication.quit()
                return
            config.LEGAL_DISCLAIMER_ACCEPTED = True
            log.info("Пользователь принял условия.")

        legal_only = getattr(config, "LEGAL_ONLY_MODE", True)

        if legal_only:
            # PUBLIC: пропускаем P2P wizard. Откладываем инициализацию
            # до запуска loop (main.py вызовет loop.run_forever()).
            log.info("PUBLIC mode: пропускаю P2P wizard (Jackett не нужен)")
            QTimer.singleShot(0, self._on_public_boot)
            return

        # PRIVATE: показываем wizard (он сам вызывает _on_success_setup
        # при нажатии кнопки, когда loop уже работает)
        self.wizard = P2PInitialSetupWizard(self.loop, self._on_success_setup)
        self.wizard.show()

    def _on_public_boot(self):
        """Отложенный старт public режима — loop уже работает."""
        log.info("PUBLIC boot: loop работает, инициализирую UI")
        self._on_success_setup(None)

    def _init_backend_client(self):
        if not self.manager:
            self.backend = None
            return
        cfg = self.manager.get_backend_config()
        if not cfg:
            self.backend = None
            log.info("Бэкенд не запущен — только archive.org и sources.txt")
            return

        self.backend = cfg["backend"]
        if self.backend == "jackett":
            self.jackett = JackettClient(
                base_url=cfg["base_url"], api_key=cfg["api_key"]
            )
            log.info("Используем Jackett-клиент")
        elif self.backend == "prowlarr":
            self.prowlarr = ProwlarrClient(
                base_url=cfg["base_url"], api_key=cfg["api_key"]
            )
            log.info("Используем Prowlarr-клиент")

    # ==================================================================
    #  ИНИЦИАЛИЗАЦИЯ ПОСЛЕ WIZARD (или сразу в public)
    # ==================================================================
    def _on_success_setup(self, active_manager):
        """
        Вызывается:
          - В public: отложенно через QTimer.singleShot (loop уже работает).
          - В private: из wizard после нажатия кнопки (loop работает).
        """
        self.session = aiohttp.ClientSession()
        log.info("HTTP-сессия создана")

        legal_only = getattr(config, "LEGAL_ONLY_MODE", True)

        if not legal_only:
            # ========================================================
            #  PRIVATE: Jackett + libtorrent
            # ========================================================
            self.manager = active_manager
            self._init_backend_client()

            from services.torrent.session import create_session
            try:
                self.libtorrent_session = create_session(
                    getattr(config, "LIBTORRENT_PORT", 6881)
                )
                log.info("Libtorrent session создан (shared)")
            except Exception as e:
                log.exception("Не удалось создать libtorrent session: %s", e)
                self.libtorrent_session = None

            # YTS (только для EN)
            try:
                from search.yts_client import YTSClient
                self.yts_client = YTSClient()
                log.info(
                    "YTS client: %s",
                    "enabled" if self.yts_client.is_enabled() else "disabled",
                )
            except Exception as e:
                log.warning("YTS init: %s", e)
                self.yts_client = None
        else:
            # ========================================================
            #  PUBLIC: только archive.org
            # ========================================================
            log.info(
                "PUBLIC mode: Jackett и libtorrent НЕ запущены "
                "(только archive.org)"
            )
            self.manager = None
            self.jackett = None
            self.prowlarr = None
            self.libtorrent_session = None
            self.yts_client = None

        # ============================================================
        #  UI — одинаково в обоих режимах
        # ============================================================
        self.main_window = MainWindow()
        self.playback = PlaybackController(
            self.main_window.player_page, self.main_window
        )

        self.feed = FeedController(self)
        self.details = DetailsController(self)
        self.stream = StreamController(self)

        self.main_window.feed_page.next_page_requested.connect(
            self.feed.load_next_page
        )
        self.main_window.player_page.close_player_requested.connect(
            self.stream.handle_close_player
        )
        self.main_window.resume_movie_requested.connect(
            self.details.handle_resume_playback
        )
        self.main_window.resume_dismiss_requested.connect(
            self.details.handle_resume_dismiss
        )
        self.main_window.details_page.back_to_feed_requested.connect(
            self.details.handle_back_to_feed
        )
        self.main_window.details_page.start_streaming_requested.connect(
            self.stream.handle_stream_start
        )

        if hasattr(self.main_window, "language_changed"):
            self.main_window.language_changed.connect(self._on_language_changed)
            self.main_window.set_language(config.SEARCH_LANGUAGE)
            log.info("Язык: %s", config.SEARCH_LANGUAGE.upper())

        self.search_debounce = QTimer(self.main_window)
        self.search_debounce.setSingleShot(True)
        self.search_debounce.setInterval(400)
        self.search_debounce.timeout.connect(self.feed.run_search)
        self.main_window.search_bar.textChanged.connect(
            self.feed.on_search_text_changed
        )

        log.info("Сигналы подключены")
        self.main_window.show()
        self._start_periodic_cleanup()

        # Прогрев Jackett только в private
        if not legal_only:
            self.loop.create_task(self._warmup_jackett())

        self.loop.create_task(self._async_boot())

    def _on_language_changed(self, lang: str):
        lang = (lang or "en").lower()
        if lang not in ("en", "ru"):
            return
        config.SEARCH_LANGUAGE = lang
        log.info("Язык: %s", lang.upper())

    async def _warmup_jackett(self):
        if self.jackett is None:
            self._jackett_ready = True
            log.info("Jackett не настроен — прогрев не нужен")
            return

        log.info("Прогрев Jackett (20 сек)...")
        await asyncio.sleep(20.0)

        try:
            info = await self.jackett.diagnose(self.session)
            available = info.get("available", 0)
            if available > 0:
                log.info("Jackett прогрелся: %d индексаторов активны", available)
            else:
                log.warning(
                    "Jackett: после прогрева 0 индексаторов. "
                    "Проверь http://127.0.0.1:%d/UI/Dashboard",
                    config.JACKETT_PORT,
                )
        except Exception as e:
            log.warning("warmup Jackett: %s: %s", type(e).__name__, e)

        self._jackett_ready = True
        log.info("Jackett готов к поиску")

    async def _async_boot(self):
        await self.feed.load_feed(clear_grid=True)
        self.details.check_resume_island()

    def _start_periodic_cleanup(self):
        if self._cleanup_timer is not None:
            self._cleanup_timer.stop()
        self._cleanup_timer = QTimer(self.main_window)
        self._cleanup_timer.setInterval(60000)
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._cleanup_timer.start()
        log.info("Периодическая очистка браузеров: каждые 60 сек")

    def _periodic_cleanup(self):
        if self.web_fetcher is not None:
            try:
                if getattr(self.web_fetcher, "_browser", None) is not None:
                    return
            except Exception:
                pass

        from services.process_cleaner import (
            cleanup_nodriver_chrome_async,
            kill_nodriver_profiles_async,
        )

        async def _cleanup():
            try:
                killed = await cleanup_nodriver_chrome_async()
                removed = await kill_nodriver_profiles_async()
                if killed > 0 or removed > 0:
                    log.info(
                        "Периодическая очистка: browsers=%d, profiles=%d",
                        killed, removed,
                    )
            except Exception as e:
                log.warning("periodic cleanup: %s", e)

        self.loop.create_task(_cleanup())

    # ==================================================================
    #  SHUTDOWN
    # ==================================================================
    async def shutdown_async(self):
        log.info("Остановка...")

        if self._cleanup_timer is not None:
            try:
                self._cleanup_timer.stop()
            except Exception:
                pass
            self._cleanup_timer = None

        if self.feed:
            try:
                self.feed.shutdown()
            except Exception:
                pass

        if self.kp_service:
            self.kp_service.log_stats()
        if self.stream:
            try:
                await self.stream.stop_all()
            except Exception as e:
                log.debug("stream.stop_all: %s", e)
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                log.debug("session.close: %s", e)
            self.session = None
        if self.web_fetcher:
            try:
                await self.web_fetcher.close()
            except Exception as e:
                log.debug("web_fetcher.close: %s", e)
        if self.archive_org:
            try:
                await self.archive_org.close()
            except Exception as e:
                log.debug("archive_org.close: %s", e)
        if self.manager:
            try:
                self.manager.stop_services()
            except Exception as e:
                log.debug("manager.stop: %s", e)

        if getattr(self, "libtorrent_session", None):
            try:
                for h in self.libtorrent_session.get_torrents():
                    try:
                        self.libtorrent_session.remove_torrent(h)
                    except Exception:
                        pass
            except Exception:
                pass
            self.libtorrent_session = None
            log.info("Libtorrent session очищен")

        log.info("Финальная очистка зомби...")
        cleanup_all()

    def shutdown(self):
        log.info("shutdown() вызван — cleanup в main.py finally")
