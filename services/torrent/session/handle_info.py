"""HandleInfo — dataclass, заменяет 5 словарей старого StreamSession."""
from dataclasses import dataclass

import libtorrent as lt


@dataclass(slots=True)
class HandleInfo:
    handle: lt.torrent_handle
    save_dir: str
    title: str
    source_type: str
    seeders_declared: int
    size_declared: int

    first_seen: float = 0.0
    first_piece_seen: float = 0.0

    file_idx: int = -1
    first_piece: int = -1
    piece_length: int = 0          # ← кэш

    last_rate: int = 0
    last_peers: int = 0
    last_has_first: bool = False

    @property
    def key(self) -> int:
        return id(self.handle)

    @property
    def is_rejected(self) -> bool:
        return self.file_idx < 0 and self.first_piece == -2

    def mark_rejected(self) -> None:
        self.file_idx = -1
        self.first_piece = -2