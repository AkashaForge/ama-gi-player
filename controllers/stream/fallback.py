"""FallbackHandler — переключение на альтернативы (public + private)."""
import asyncio
import time

from PyQt6.QtCore import QTimer

import config
from core.logging_setup import get_logger
from services.torrent.source_selector import SourceSelector

log = get_logger("stream.fallback")

_PUBLIC_RETRY_DELAY_MS = 5000
_PUBLIC_MAX_RETRIES = 1


class FallbackHandler:
    def __init__(self, controller):
        self.controller = controller
        self.loop = controller.loop
        self._last_demux_ts = 0.0
        self._reload_attempts = 0
        self._auto_attempts = 0
        self._auto_max = 3

        # --- PUBLIC state (изолирован от private) ---
        self._public_index = 0
        self._public_retry_attempt = 0
        self._public_retry_pending = False
        self._public_epoch = 0

        self.DEMUX_COOLDOWN = config.STREAM_DEMUX_ERROR_COOLDOWN_SEC
        self.RELOAD_DELAY = config.STREAM_DEMUX_RELOAD_DELAY_SEC
        self.MAX_RELOADS = config.STREAM_MAX_RELOADS_BEFORE_FALLBACK

    def reset(self):
        # private
        self._reload_attempts = 0
        self._auto_attempts = 0
        self._last_demux_ts = 0.0
        # public — сбрасываем epoch, чтобы «старые» QTimer'ы
        # не выстрелили в новый стрим
        self._public_index = 0
        self._public_retry_attempt = 0
        self._public_retry_pending = False
        self._public_epoch += 1

    # ==================================================================
    #  DEMUX — точка входа
    # ==================================================================
    def on_demux_error(self):
        now = time.time()
        if now - self._last_demux_ts < self.DEMUX_COOLDOWN:
            return
        self._last_demux_ts = now
        log.warning("DEMUX ERROR")

        try:
            self.controller.playback.player.stop()
        except Exception:
            pass
        self.controller.buffer.mark_stopped()

        # ============================================================
        #  PUBLIC: отдельная ветка. Private НЕ доходит сюда.
        # ============================================================
        if config.LEGAL_ONLY_MODE:
            self._on_public_demux_error()
            return

        # ============================================================
        #  PRIVATE: оригинальная логика, БЕЗ изменений.
        # ============================================================
        if not config.STREAM_AUTO_FALLBACK_ON_DEMUX_ERROR:
            return
        if not self.controller.stream_session:
            return

        if self._reload_attempts < self.MAX_RELOADS:
            self._reload_attempts += 1
            log.info("DEMUX → reload #%d (%.0fs)",
                     self._reload_attempts, self.RELOAD_DELAY)
            self.loop.create_task(self._reload_after_delay())
            return

        self.do_auto_fallback()

    # ==================================================================
    #  PUBLIC: retry 5s → следующий direct_url
    # ==================================================================
    def _on_public_demux_error(self):
        c = self.controller

        if self._public_retry_pending:
            log.debug("public DEMUX: retry already pending, ignore")
            return

        direct = getattr(c, "_direct_fallback", None) or []
        if not direct:
            log.warning("public DEMUX: _direct_fallback пуст")
            return

        if self._public_index >= len(direct):
            log.warning("public DEMUX: все %d источников испробованы",
                        len(direct))
            c.main_window.player_page.loader_label.setText(
                "ИСТОЧНИК НЕ РАБОТАЕТ. Все варианты испробованы."
            )
            return

        # --- Попытка 1: retry того же URL через 5 сек ---
        if self._public_retry_attempt < _PUBLIC_MAX_RETRIES:
            self._public_retry_attempt += 1
            self._public_retry_pending = True
            epoch = self._public_epoch
            url = direct[self._public_index]["url"]
            log.info("public DEMUX → retry in 5s (attempt %d/%d): %s",
                     self._public_retry_attempt, _PUBLIC_MAX_RETRIES,
                     url[:80])
            c.main_window.player_page.loader_label.setText(
                f"ПОВТОР {self._public_retry_attempt}/{_PUBLIC_MAX_RETRIES} через 5с..."
            )
            QTimer.singleShot(
                _PUBLIC_RETRY_DELAY_MS,
                lambda: self._do_public_retry(epoch),
            )
            return

        # --- Попытка 2: retry не помог → следующий direct_url ---
        self._public_retry_attempt = 0
        self._public_index += 1
        if self._public_index >= len(direct):
            log.warning("public: все %d источников испробованы", len(direct))
            c.main_window.player_page.loader_label.setText(
                "ИСТОЧНИК НЕ РАБОТАЕТ. Все варианты испробованы."
            )
            return

        next_src = direct[self._public_index]
        log.info("public → next direct %d/%d: %s (priority=%s, %.1f MB)",
                 self._public_index + 1, len(direct),
                 next_src["url"][:80],
                 next_src.get("priority", "?"),
                 (next_src.get("size", 0) or 0) / 1e6)
        c.main_window.player_page.show_loader()
        c.main_window.player_page.loader_label.setText(
            f"ИСТОЧНИК {self._public_index + 1}/{len(direct)}..."
        )
        c.playback.play_url(
            next_src["url"], c._current_movie_id, c._current_movie_title
        )

    def _do_public_retry(self, epoch: int):
        self._public_retry_pending = False

        # epoch-guard: если пользователь закрыл/перезапустил стрим за эти 5с —
        # QTimer от старого стрима не должен трогать новый
        if epoch != self._public_epoch:
            log.info("public retry: stream was reset (epoch %d != %d), skip",
                     epoch, self._public_epoch)
            return

        c = self.controller
        if not c.stream_in_progress:
            log.info("public retry: stream_in_progress=False, skip")
            return

        direct = getattr(c, "_direct_fallback", None) or []
        if not direct or self._public_index >= len(direct):
            return

        url = direct[self._public_index]["url"]
        log.info("public retry: %s", url[:80])
        c.main_window.player_page.show_loader()
        c.playback.play_url(url, c._current_movie_id, c._current_movie_title)

    # ==================================================================
    #  PRIVATE — ОРИГИНАЛ, НЕ ТРОНУТ
    # ==================================================================
    async def _reload_after_delay(self):
        await asyncio.sleep(self.RELOAD_DELAY)
        session = self.controller.stream_session
        if not session or not session.is_active():
            return
        log.info("DEMUX reload")
        try:
            self.controller.playback.reload_url()
            self.controller.buffer.mark_stopped()
        except Exception as e:
            log.warning("reload: %s", e)
            self.do_auto_fallback()

    def do_auto_fallback(self):
        session = self.controller.stream_session
        if not session:
            return
        if self._auto_attempts >= self._auto_max:
            log.warning("auto-fallback exhausted")
            self.controller.main_window.player_page.loader_label.setText(
                "РАЗДАЧА БИТАЯ. Все альтернативы испробованы."
            )
            return

        alternatives = [
            a for a in session.alternatives
            if a.get("type") in ("magnet", "torrent_url")
        ]
        if not alternatives:
            self.controller.main_window.player_page.loader_label.setText(
                "РАЗДАЧА БИТАЯ. Альтернатив нет."
            )
            return

        try:
            sel = SourceSelector(
                self.controller._current_year,
                language=config.SEARCH_LANGUAGE,
            )
            scored = [(sel.score(a), a) for a in alternatives]
            scored.sort(key=lambda x: x[0], reverse=True)
            next_src = scored[0][1]
            next_score = scored[0][0]
        except Exception:
            next_src = alternatives[0]
            next_score = 0

        self._auto_attempts += 1
        self._reload_attempts = 0
        log.warning("auto-fallback [%d/%d]: '%s' (%.1f)",
                    self._auto_attempts, self._auto_max,
                    (next_src.get("title") or "")[:60], next_score)
        self.loop.create_task(self.controller._do_select(next_src))