"""Загрузка .torrent / magnet. Логирование каждого источника."""

import os
import re
import tempfile

import aiohttp
import libtorrent as lt

from core.logging_setup import get_logger

log = get_logger("lt.source")


class SourceLoader:
    VIDEO_EXTS = (
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.ts',
        '.m2ts', '.mts', '.mpg', '.mpeg', '.vob', '.wmv', '.flv',
        '.3gp', '.ogv', '.rmvb', '.divx', '.asf', '.f4v',
    )
    MIN_FILE_SIZE = 20 * 1024 * 1024

    def __init__(self, http_session: aiohttp.ClientSession | None,
                 downloads_dir: str, tmp_files: list):
        self.http_session = http_session
        self.downloads_dir = downloads_dir
        self._tmp_files = tmp_files

    async def _download_torrent_file(self, url: str, idx: int) -> tuple | None:
        if not self.http_session:
            log.warning("race[%d]: нет http_session", idx)
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.http_session.get(
                url, timeout=timeout, allow_redirects=False
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if location.startswith("magnet:"):
                        log.info("race[%d]: .torrent → magnet (redirect)", idx)
                        return ("magnet", location)
                    async with self.http_session.get(
                        location, timeout=timeout
                    ) as resp2:
                        if resp2.status != 200:
                            log.warning("race[%d]: redirect HTTP %d",
                                        idx, resp2.status)
                            return None
                        data = await resp2.read()
                elif resp.status == 200:
                    data = await resp.read()
                    if data[:7] == b"magnet:":
                        magnet = data.decode("utf-8", errors="ignore").strip()
                        log.info("race[%d]: .torrent → magnet (тело)", idx)
                        return ("magnet", magnet)
                else:
                    log.warning("race[%d]: .torrent HTTP %d", idx, resp.status)
                    return None

            if not data:
                return None

            if data[:1] == b"d":
                os.makedirs(self.downloads_dir, exist_ok=True)
                fd, path = tempfile.mkstemp(
                    suffix=".torrent", dir=self.downloads_dir
                )
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(data)
                except Exception:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                    raise
                self._tmp_files.append(path)
                log.info("race[%d]: .torrent OK (%d байт)", idx, len(data))
                return ("torrent_path", path)

            return None
        except Exception as e:
            log.warning("race[%d]: .torrent error: %s: %s",
                        idx, type(e).__name__, e)
            return None

    @staticmethod
    def _magnet_diagnostics(magnet: str) -> dict:
        result = {"hash": "?", "trackers": 0, "dn": ""}
        try:
            m = re.search(r'btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})', magnet)
            if m:
                result["hash"] = m.group(1)[:12] + "..."
            result["trackers"] = len(re.findall(r'[&?]tr=', magnet))
            dn = re.search(r'[&?]dn=([^&]+)', magnet)
            if dn:
                from urllib.parse import unquote
                try:
                    result["dn"] = unquote(dn.group(1))[:60]
                except Exception:
                    result["dn"] = dn.group(1)[:60]
        except Exception:
            pass
        return result

    async def add_source(self, source, idx: int,
                          session: lt.session) -> tuple | None:
        kind = ""
        value = ""

        if isinstance(source, str):
            if source.startswith("magnet:"):
                kind, value = "magnet", source
            elif source.startswith(("http://", "https://")):
                kind, value = "torrent_url", source
            else:
                return None
        elif isinstance(source, dict):
            kind = (source.get("type") or "").strip().lower()
            value = (source.get("url") or source.get("MagnetUri") or "").strip()
            if not value:
                return None
            if not kind:
                if value.startswith("magnet:"):
                    kind = "magnet"
                elif value.startswith(("http://", "https://")):
                    kind = "torrent_url"
            if kind not in ("magnet", "torrent_url"):
                return None
        else:
            return None

        diag = {}
        try:
            if kind == "magnet":
                diag = self._magnet_diagnostics(value)
                params = lt.parse_magnet_uri(value)
            else:
                log.info("race[%d]: скачиваю .torrent: %s...", idx, value[:70])
                result = await self._download_torrent_file(value, idx)
                if not result:
                    return None
                rk, rv = result
                if rk == "magnet":
                    diag = self._magnet_diagnostics(rv)
                    params = lt.parse_magnet_uri(rv)
                else:
                    params = lt.add_torrent_params()
                    params.ti = lt.torrent_info(rv)
        except Exception as e:
            log.warning("race[%d]: parse error: %s: %s",
                        idx, type(e).__name__, e)
            return None

        params.save_path = self.downloads_dir
        params.storage_mode = lt.storage_mode_t.storage_mode_sparse
        params.flags |= lt.torrent_flags.auto_managed
        params.flags &= ~lt.torrent_flags.paused

        try:
            handle = session.add_torrent(params)
        except Exception as e:
            log.warning("race[%d]: add_torrent failed: %s", idx, e)
            return None

        if handle is None:
            return None

        try:
            handle.set_sequential_download(False)
        except Exception:
            pass

        try:
            info = handle.torrent_file()
            if info is not None:
                for i in range(info.files().num_files()):
                    handle.file_priority(i, 0)
        except Exception:
            pass

        if kind == "magnet":
            log.info(
                "race[%d]: добавлен magnet hash=%s trackers=%d dn='%s'",
                idx, diag.get("hash", "?"), diag.get("trackers", 0),
                diag.get("dn", ""),
            )
        else:
            try:
                info = handle.torrent_file()
                if info is not None:
                    log.info(
                        "race[%d]: добавлен .torrent '%s' (%d файлов, %.1f MB)",
                        idx, info.name(), info.num_files(),
                        info.total_size() / 1024 / 1024,
                    )
                else:
                    log.info("race[%d]: добавлен .torrent (metadata pending)", idx)
            except Exception:
                log.info("race[%d]: добавлен .torrent", idx)

        return (handle, idx, source)
