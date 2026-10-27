"""Shim для обратной совместимости. Реальный код — в services.torrent."""

from services.torrent import LibtorrentStreamWorker

__all__ = ["LibtorrentStreamWorker"]
