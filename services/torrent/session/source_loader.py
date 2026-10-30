"""SourceLoader — добавление magnet/torrent_url с pre-merge."""
import aiohttp
import libtorrent as lt

import config
from core.logging_setup import get_logger
from services.torrent.session.file_picker import (
    FilePicker, RETRY, NO_VIDEO,
)
from services.torrent.session.handle_registry import HandleRegistry
from services.torrent.swarm_grouper import extract_trackers

log = get_logger("lt.session.loader")


class SourceLoader:
    def __init__(self, http_session: aiohttp.ClientSession,
                 lt_session: lt.session,
                 registry: HandleRegistry,
                 file_picker: FilePicker,
                 on_prioritize):
        self.http_session = http_session
        self.session = lt_session
        self.registry = registry
        self.file_picker = file_picker
        self._on_prioritize = on_prioritize

    async def load(self, source: dict, save_dir: str,
                    is_primary: bool = False):
        url = source.get("url", "")
        if not url:
            return None

        is_magnet = url.startswith("magnet:")
        params = await self._parse_source(url, is_magnet,
                                           "primary" if is_primary else "alt")
        if params is None:
            return None

        pre = self._pre_merge(params, is_magnet, url)
        if pre is not None:
            return pre, False

        handle = self._add_torrent(params, save_dir)
        if handle is None:
            return None

        if not is_magnet and params.ti is not None:
            if not self._initial_pick(handle, params.ti):
                try:
                    self.session.async_remove_torrent(handle)  # non-blocking
                except Exception:
                    pass
                return None

        info = self.registry.add(
            handle=handle,
            save_dir=save_dir,
            title=source.get("title", ""),
            source_type="magnet" if is_magnet else "torrent_url",
            seeders=source.get("seeders", 0) or 0,
            size=source.get("size", 0) or 0,
        )

        if is_magnet:
            for tr in extract_trackers(url):
                try:
                    handle.add_tracker({"url": tr, "tier": 0})
                except Exception:
                    pass

        return info, True

    async def _parse_source(self, url: str, is_magnet: bool, label: str):
        try:
            if is_magnet:
                return lt.parse_magnet_uri(url)

            data = await self._download_torrent(url)
            if data is None:
                return None

            if data[:7] == b"magnet:":
                magnet = data.decode("utf-8", errors="ignore").strip()
                return lt.parse_magnet_uri(magnet)

            if data[:1] != b"d":
                log.warning("not bencode (%s): %r", label, data[:1])
                return None

            params = lt.add_torrent_params()
            params.ti = lt.torrent_info(data)
            return params
        except Exception as e:
            log.warning("parse (%s): %s: %s", label, type(e).__name__, e)
            return None

    async def _download_torrent(self, url: str) -> bytes | None:
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.http_session.get(
                url, timeout=timeout, allow_redirects=False
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    loc = resp.headers.get("Location", "")
                    if loc.startswith("magnet:"):
                        return loc.encode("utf-8")
                    async with self.http_session.get(
                        loc, timeout=timeout
                    ) as resp2:
                        if resp2.status == 200:
                            return await resp2.read()
                elif resp.status == 200:
                    return await resp.read()
        except Exception as e:
            log.warning("download .torrent: %s", e)
        return None

    def _pre_merge(self, params, is_magnet: bool, url: str):
        try:
            pre_hash = None
            if is_magnet:
                try:
                    pre_hash = str(params.info_hash)
                except Exception:
                    pass
            elif params.ti is not None:
                try:
                    pre_hash = str(params.ti.info_hash())
                except Exception:
                    pass

            if not pre_hash:
                return None

            existing = self.registry.find_by_hash(pre_hash)
            if existing is None or not existing.is_valid():
                return None

            log.info("Pre-merge %s hash=%s",
                     "magnet" if is_magnet else "torrent",
                     pre_hash[:12])

            trackers = []
            if is_magnet:
                trackers = extract_trackers(url)
            else:
                try:
                    for tr in params.ti.trackers():
                        try:
                            trackers.append(tr.url)
                        except Exception:
                            pass
                except Exception:
                    pass

            if hasattr(existing, "add_tracker"):
                for tr in trackers:
                    try:
                        existing.add_tracker({"url": tr, "tier": 0})
                    except Exception:
                        pass
            return existing
        except Exception as e:
            log.debug("pre-merge: %s", e)
            return None

    def _add_torrent(self, params, save_dir: str):
        params.save_path = save_dir
        params.storage_mode = lt.storage_mode_t.storage_mode_sparse
        params.flags |= lt.torrent_flags.auto_managed
        params.flags &= ~lt.torrent_flags.paused
        try:
            handle = self.session.add_torrent(params)
            return handle if handle is not None else None
        except Exception as e:
            log.warning("add_torrent: %s", e)
            return None

    def _initial_pick(self, handle, ti) -> bool:
        try:
            file_idx = self.file_picker.pick(ti)
        except Exception as e:
            log.debug("pick exception: %s", e)
            return True

        if file_idx == RETRY:
            log.debug("Handle %s: RETRY (incomplete ti)", id(handle))
            return True

        if file_idx == NO_VIDEO or file_idx < 0:
            log.info("Handle %s: no video file (pick=%d)",
                     id(handle), file_idx)
            return False

        info = self.registry.get(handle)
        if info is not None:
            info.file_idx = file_idx
            try:
                info.piece_length = ti.piece_length()
            except Exception:
                info.piece_length = 0
            try:
                info.first_piece = self._on_prioritize(handle, ti, file_idx)
            except Exception as e:
                log.warning("initial prioritize: %s", e)
        return True