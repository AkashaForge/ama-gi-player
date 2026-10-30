"""Параллельные задачи поиска."""
from .jackett import safe_jackett
from .web_fetcher import safe_web_fetcher
from .archive_org import safe_archive_org
from .yts import safe_yts
from .balancers import safe_balancers
from .torapi import safe_torapi

__all__ = [
    "safe_jackett",
    "safe_web_fetcher",
    "safe_archive_org",
    "safe_yts",
    "safe_balancers",
    "safe_torapi",
]