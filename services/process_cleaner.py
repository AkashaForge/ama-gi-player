"""Очистка зомби-процессов + async обёртки."""

import os
import shutil
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[PROCESS-CLEANER] psutil не установлен — очистка процессов отключена")

import config
from core.logging_setup import get_logger

log = get_logger("cleaner")

_BROWSER_NAMES = ("chrome.exe", "chromium.exe", "msedge.exe", "chrome")


def _is_nodriver_chrome(cmdline: str) -> bool:
    low = cmdline.lower()
    if "--remote-debugging-port=" in low:
        return True
    if "uc_" in low and ("user-data-dir" in low or "nodriver" in low):
        return True
    if "nodriver" in low:
        return True
    return False


def cleanup_nodriver_chrome() -> int:
    if not HAS_PSUTIL:
        return 0
    killed = 0
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.name() or "").lower()
                if name not in _BROWSER_NAMES:
                    continue

                cmdline = " ".join(proc.cmdline() or [])
                if not cmdline:
                    continue

                if not _is_nodriver_chrome(cmdline):
                    continue

                try:
                    for child in proc.children(recursive=True):
                        try:
                            child.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                proc.kill()
                killed += 1
                log.info("Убит nodriver-Chrome pid=%d", proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        log.warning("cleanup_nodriver_chrome: %s", e)
    return killed


def cleanup_zombie_jackett() -> int:
    if not HAS_PSUTIL:
        os.system("taskkill /f /im JackettConsole.exe >nul 2>&1")
        return -1
    killed = 0
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.name().lower() == "jackettconsole.exe":
                    proc.kill()
                    killed += 1
                    log.info("Убит зомби-Jackett pid=%d", proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        log.warning("cleanup_zombie_jackett: %s", e)
    return killed


def cleanup_zombie_prowlarr() -> int:
    if not HAS_PSUTIL:
        os.system("taskkill /f /im Prowlarr.exe >nul 2>&1")
        return -1
    killed = 0
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.name().lower() == "prowlarr.exe":
                    proc.kill()
                    killed += 1
                    log.info("Убит зомби-Prowlarr pid=%d", proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        log.warning("cleanup_zombie_prowlarr: %s", e)
    return killed


def kill_nodriver_profiles() -> int:
    temp = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    if not temp or not os.path.isdir(temp):
        return 0
    removed = 0
    try:
        for entry in os.listdir(temp):
            if not entry.startswith("uc_"):
                continue
            path = os.path.join(temp, entry)
            try:
                shutil.rmtree(path, ignore_errors=True)
                if not os.path.exists(path):
                    removed += 1
            except Exception as e:
                log.debug("rmtree %s: %s", path, e)
    except Exception as e:
        log.warning("kill_nodriver_profiles: %s", e)
    return removed


def _dir_size_bytes(path: str) -> int:
    if not os.path.isdir(path):
        return 0
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except Exception:
        pass
    return total


def cleanup_downloads() -> int:
    downloads = str(config.DOWNLOADS_DIR)
    if not os.path.isdir(downloads):
        return 0
    max_bytes = getattr(config, "DOWNLOADS_MAX_GB", 50) * 1024 ** 3
    current = _dir_size_bytes(downloads)
    if current <= max_bytes:
        return 0

    files = []
    for root, _dirs, names in os.walk(downloads):
        for name in names:
            path = os.path.join(root, name)
            try:
                stat = os.stat(path)
                files.append((stat.st_mtime, stat.st_size, path))
            except OSError:
                pass
    files.sort(key=lambda x: x[0])

    removed = 0
    freed = 0
    target = current - max_bytes + 1024 ** 3
    for mtime, size, path in files:
        if freed >= target:
            break
        try:
            os.remove(path)
            freed += size
            removed += 1
        except OSError:
            pass

    try:
        for root, dirs, _files in os.walk(downloads, topdown=False):
            for d in dirs:
                folder = os.path.join(root, d)
                try:
                    if not os.listdir(folder):
                        os.rmdir(folder)
                except OSError:
                    pass
    except Exception:
        pass

    if removed:
        log.info("Очистка downloads: удалено %d файлов, освобождено %.1f GB",
                 removed, freed / 1024 ** 3)
    return removed


def cleanup_all(kill_browsers: bool = True) -> dict:
    if not HAS_PSUTIL:
        log.warning("psutil не установлен — очистка процессов пропущена")
        return {"browsers": 0, "jackett": 0, "prowlarr": 0, "profiles": 0}

    browsers = cleanup_nodriver_chrome() if kill_browsers else 0
    jackett = cleanup_zombie_jackett()
    prowlarr = cleanup_zombie_prowlarr()

    if browsers > 0:
        time.sleep(0.5)

    profiles = kill_nodriver_profiles()

    log.info("Итого: browsers=%d, jackett=%d, prowlarr=%d, profiles=%d",
             browsers, jackett, prowlarr, profiles)
    return {"browsers": browsers, "jackett": jackett,
            "prowlarr": prowlarr, "profiles": profiles}


def cleanup_startup() -> None:
    cleanup_all()
    if getattr(config, "DOWNLOADS_CLEANUP_ON_START", True):
        try:
            cleanup_downloads()
        except Exception as e:
            log.warning("cleanup_downloads: %s", e)


# ======================================================================
#  ASYNC ОБЁРТКИ (не блокируют UI)
# ======================================================================
async def cleanup_all_async(kill_browsers: bool = True) -> dict:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: cleanup_all(kill_browsers=kill_browsers)
    )


async def cleanup_nodriver_chrome_async() -> int:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, cleanup_nodriver_chrome)


async def kill_nodriver_profiles_async() -> int:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, kill_nodriver_profiles)
