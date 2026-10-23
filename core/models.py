"""Модели данных."""

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Source:
    type: str
    url: str
    title: str
    seeders: int = 0
    size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(
            type=d.get("type", "magnet"),
            url=d.get("url", ""),
            title=d.get("title", "Без названия"),
            seeders=int(d.get("seeders", 0) or 0),
            size=int(d.get("size", 0) or 0),
        )

    def is_valid(self) -> bool:
        return bool(self.url) and self.type in ("magnet", "torrent_url")
