"""AlertPump — читает pop_alerts() и раскидывает по обработчикам."""
import asyncio

import libtorrent as lt

from core.logging_setup import get_logger

log = get_logger("lt.session.alert_pump")


class AlertPump:
    def __init__(self, lt_session, on_read_piece):
        self.session = lt_session
        self._on_read_piece = on_read_piece
        self._task: asyncio.Task | None = None
        self._cancelled = False

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._cancelled = False
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while not self._cancelled and self.session:
            try:
                alerts = self.session.pop_alerts()
                for alert in alerts:
                    if isinstance(alert, lt.read_piece_alert):
                        self._on_read_piece(alert)
                    elif isinstance(alert, lt.metadata_received_alert):
                        log.info("ALERT: metadata_received")
                    elif isinstance(alert, lt.metadata_failed_alert):
                        log.warning("ALERT: metadata_failed")
                    elif isinstance(alert, lt.torrent_error_alert):
                        log.error("ALERT: torrent_error: %s", alert.message())
            except Exception:
                pass
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None