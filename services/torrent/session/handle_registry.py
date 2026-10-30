"""HandleRegistry — управление набором HandleInfo.

Заменяет словари:
    _handle_dirs, _handle_titles, _handle_first_seen,
    _handle_first_piece_seen, _file_cache
"""
import time

import libtorrent as lt

from core.logging_setup import get_logger
from services.torrent.session.handle_info import HandleInfo

log = get_logger("lt.session.registry")


class HandleRegistry:
    def __init__(self):
        self._handles: dict[int, HandleInfo] = {}
        self._by_hash: dict[str, lt.torrent_handle] = {}

    # ==================================================================
    #  СОЗДАНИЕ
    # ==================================================================
    def add(self, handle, save_dir: str, title: str,
            source_type: str, seeders: int, size: int) -> HandleInfo:
        info = HandleInfo(
            handle=handle,
            save_dir=save_dir,
            title=title,
            source_type=source_type,
            seeders_declared=seeders,
            size_declared=size,
            first_seen=time.time(),
        )
        self._handles[info.key] = info
        try:
            h = str(handle.info_hash())
            self._by_hash[h] = handle
        except Exception:
            pass
        return info

    def register_hash(self, hash_str: str, handle) -> None:
        self._by_hash[hash_str] = handle

    def find_by_hash(self, hash_str: str):
        return self._by_hash.get(hash_str)

    # ==================================================================
    #  ДОСТУП
    # ==================================================================
    def all(self) -> list[HandleInfo]:
        return list(self._handles.values())

    def get(self, handle) -> HandleInfo | None:
        return self._handles.get(id(handle))

    def get_by_key(self, key: int) -> HandleInfo | None:
        return self._handles.get(key)

    def __len__(self) -> int:
        return len(self._handles)

    def __iter__(self):
        return iter(list(self._handles.values()))

    # ==================================================================
    #  УДАЛЕНИЕ
    # ==================================================================
    def remove(self, handle) -> HandleInfo | None:
        info = self._handles.pop(id(handle), None)
        if info is not None:
            try:
                h = str(handle.info_hash())
                self._by_hash.pop(h, None)
            except Exception:
                pass
        return info

    def clear(self) -> None:
        self._handles.clear()
        self._by_hash.clear()