"""FallbackHandler — переключение на альтернативы."""
import asyncio
import time

import config
from core.logging_setup import get_logger
from services.torrent.source_selector import SourceSelector

log = get_logger("stream.fallback")


class FallbackHandler:
    def __init__(self, controller):
        """
        controller — StreamController, имеет:
          .stream_session, .loop, .playback,
          ._do_select(), ._stop_resources(),
          .main_window.player_page
        """
        self.controller = controller
        self.loop = controller.loop
        self._last_demux_ts = 0.0
        self._reload_attempts = 0
        self._auto_attempts = 0
        self._auto_max = 3
        self.DEMUX_COOLDOWN = config.STREAM_DEMUX_ERROR_COOLDOWN_SEC
        self.RELOAD_DELAY = config.STREAM_DEMUX_RELOAD_DELAY_SEC
        self.MAX_RELOADS = config.STREAM_MAX_RELOADS_BEFORE_FALLBACK

    def reset(self):
        self._reload_attempts = 0
        self._auto_attempts = 0
        self._last_demux_ts = 0.0

    # ==================================================================
    #  DEMUX
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

        if not config.STREAM_AUTO_FALLBACK_ON_DEMUX_ERROR:
            return
        if config.LEGAL_ONLY_MODE:
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

    # ==================================================================
    #  AUTO FALLBACK
    # ==================================================================
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