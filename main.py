"""Amagi-Player — точка входа."""

# Amagi-Player — desktop media player for public-domain content
# Copyright (C) 2026 AkashaForge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys

if sys.platform == "win32":
    import builtins
    import io
    _orig_io_open = io.open
    def _utf8_open(file, mode="r", buffering=-1, encoding=None,
                   errors=None, newline=None, closefd=True, opener=None):
        if isinstance(mode, str) and "b" not in mode and encoding is None:
            encoding = "utf-8"
        return _orig_io_open(file, mode, buffering, encoding,
                             errors, newline, closefd, opener)
    io.open = _utf8_open
    builtins.open = _utf8_open

import asyncio
import atexit
import os
import signal
import threading

import qasync
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from controllers.orchestrator import AmagiApplicationOrchestrator
from core.logging_setup import get_logger, setup_logging
from services.process_cleaner import cleanup_all, kill_nodriver_profiles

setup_logging()
log = get_logger("main")

# Защита от двойного shutdown
_shutdown_started = False
_shutdown_done = False


def _atexit_cleanup():
    """Финальная очистка процессов. Безопасна при повторном вызове."""
    try:
        cleanup_all()
        kill_nodriver_profiles()
    except Exception:
        pass


atexit.register(_atexit_cleanup)


def _signal_cleanup(signum, frame):
    def _do():
        try:
            cleanup_all()
            kill_nodriver_profiles()
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()
    try:
        QApplication.quit()
    except Exception:
        pass


try:
    signal.signal(signal.SIGINT, _signal_cleanup)
except (ValueError, OSError):
    pass
try:
    signal.signal(signal.SIGTERM, _signal_cleanup)
except (ValueError, OSError):
    pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    orchestrator = AmagiApplicationOrchestrator(loop)
    orchestrator.start_orchestration()

    async def _graceful_shutdown(reason: str):
        """Единственный путь завершения. Выполняется ровно один раз."""
        global _shutdown_started, _shutdown_done
        if _shutdown_started:
            log.debug("shutdown already started (reason: %s), skip", reason)
            return
        _shutdown_started = True

        log.info("Начинаю graceful shutdown (%s)...", reason)

        try:
            await orchestrator.shutdown_async()
        except Exception as e:
            log.warning("shutdown_async: %s", e)

        try:
            _atexit_cleanup()
        except Exception:
            pass

        _shutdown_done = True
        log.info("Shutdown завершён (%s)", reason)

    def _on_last_window_closed():
        log.info("Окно закрыто пользователем")

        async def _run():
            await _graceful_shutdown("window closed")
            try:
                loop.stop()
            except Exception:
                pass

        asyncio.ensure_future(_run(), loop=loop)

    app.lastWindowClosed.connect(_on_last_window_closed)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt")

    # Гарантированный shutdown, если его не сделал _on_last_window_closed
    if not _shutdown_done:
        try:
            loop.run_until_complete(_graceful_shutdown("finally"))
        except Exception as e:
            log.warning("shutdown (finally): %s", e)
    else:
        log.debug("shutdown уже выполнен в _on_last_window_closed")

    try:
        loop.close()
    except Exception:
        pass

    _atexit_cleanup()
    log.info("Выход")