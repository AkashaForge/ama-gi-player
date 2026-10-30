"""BufferMonitor — watchdog для P2P и online-потоков."""
import time

from PyQt6.QtCore import QTimer

import config
from core.logging_setup import get_logger

log = get_logger("stream.buffer_monitor")


class BufferMonitor:
    def __init__(self, main_window, playback, on_fallback):
        self.main_window = main_window
        self.playback = playback
        self._on_fallback = on_fallback

        self._timer: QTimer | None = None
        self._stopped = False
        self._pending_since: float | None = None
        self._playback_start_ts = 0.0
        self._is_online = False

        self.INTERVAL_MS = config.STREAM_MONITOR_INTERVAL_MS
        self.STOP_DELAY = config.STREAM_BUFFER_STOP_DELAY_SEC
        self.WATCHDOG_SEC = config.STREAM_BUFFERING_WATCHDOG_SEC
        self.WATCHDOG_RATE = config.STREAM_BUFFERING_WATCHDOG_RATE_MB

    def start_p2p(self, stream_session_getter):
        """Запуск для P2P (stream_session)."""
        self._is_online = False
        self._playback_start_ts = time.time()
        self._start_timer(lambda: self._check_p2p(stream_session_getter))

    def start_online(self):
        """Запуск для online (direct_url из балансеров)."""
        self._is_online = True
        self._playback_start_ts = time.time()
        self._start_timer(self._check_online)

    def _start_timer(self, callback):
        self.stop()
        self._timer = QTimer(self.main_window)
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(callback)
        self._timer.start()
        self._stopped = False
        self._pending_since = None
        log.info("Buffer monitor запущен")

    def stop(self):
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None
        self._stopped = False
        self._pending_since = None

    def mark_stopped(self):
        self._stopped = True
        self._pending_since = None

    # ==================================================================
    #  P2P
    # ==================================================================
    def _check_p2p(self, stream_session_getter):
        session = stream_session_getter()
        if not session or not self.playback:
            return
        try:
            buffering = session.is_buffering()
            stats = session.stats
            buf_dur = session.buffering_duration()
        except Exception:
            return

        # Watchdog
        if (buffering and buf_dur > self.WATCHDOG_SEC
                and stats.payload_rate / 1024 / 1024 < self.WATCHDOG_RATE):
            log.warning("WATCHDOG: %.0fs, rate=%.2f, peers=%d → fallback",
                        buf_dur, stats.payload_rate / 1024 / 1024,
                        stats.connected_peers)
            self._stopped = True
            self._pending_since = None
            try:
                self.playback.player.stop()
            except Exception:
                pass
            self._on_fallback(force=True)
            return

        if buffering and not self._stopped:
            if self._pending_since is None:
                self._pending_since = time.time()
            self.main_window.player_page.loader_label.setText(
                f"БУФЕРИЗАЦИЯ | {stats.connected_peers} пиров | "
                f"{stats.payload_rate / 1024 / 1024:.2f} MB/s"
            )
            if time.time() - self._pending_since > self.STOP_DELAY:
                log.warning("Buffer %.0fs — stop", self.STOP_DELAY)
                try:
                    self.playback.player.stop()
                except Exception:
                    pass
                self._stopped = True
                self._pending_since = None
        elif not buffering and self._stopped:
            log.info("Данные пошли — reload")
            try:
                self.playback.reload_url()
            except Exception as e:
                log.warning("reload: %s", e)
            self._stopped = False
            self._pending_since = None
        elif not buffering:
            self._pending_since = None

    # ==================================================================
    #  ONLINE
    # ==================================================================
    def _check_online(self):
        if self._playback_start_ts <= 0:
            return
        elapsed = time.time() - self._playback_start_ts
        if elapsed > 30.0 and self._stopped:
            log.warning("ONLINE: 30s без воспроизведения → fallback")
            self._on_fallback(force=False)