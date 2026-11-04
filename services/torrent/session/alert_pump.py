"""AlertPump — читает pop_alerts() и раскидывает по обработчикам.

v2.0.24:
  - stop() теперь async: yield перед task.cancel(), чтобы pump
    успел обработать последнюю порцию pop_alerts (важно для
    async_remove_torrent в StreamSession.cancel()).
  - Логирование ошибок pop_alerts (раньше silently pass).
"""
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
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.debug("alert_pump pop_alerts: %s", e)
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise

    async def stop(self) -> None:
        """Async stop: yield перед cancel, чтобы pump успел доделать.

        task.cancel() поднимает CancelledError в момент await
        asyncio.sleep(0.1). Между этим моментом и cancel() pump
        мог бы обработать ещё одну порцию pop_alerts — включая
        async_remove_torrent из StreamSession.cancel(). Поэтому
        сначала даём один тик (sleep 0.05), потом уже cancel.
        """
        self._cancelled = True
        # Даём pump один тик на финальный pop_alerts
        try:
            await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None