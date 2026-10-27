"""Amagi-Player — точка входа."""

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


def _atexit_cleanup():
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

    # --- ОБНОВЛЕНИЕ: Перехват закрытия окна ---
    # Как только пользователь закрывает последнее окно интерфейса,
    # срабатывает этот лямбда-вызов: запускается очистка и прерывается цикл run_forever()
    app.lastWindowClosed.connect(lambda: [
        log.info("Окно закрыто пользователем. Запуск очистки процессов..."),
        _atexit_cleanup(),
        loop.stop()
    ])
    # ------------------------------------------

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt")
    finally:
        try:
            loop.run_until_complete(orchestrator.shutdown_async())
        except Exception as e:
            log.warning("shutdown_async: %s", e)
        try:
            loop.close()
        except Exception:
            pass
        _atexit_cleanup()
        log.info("Выход")
