"""P2P-модуль Amagi-Player (libtorrent 2.1.1, time-critical mode)."""

from .session import create_session
from .stream_session import StreamSession

__all__ = ["create_session", "StreamSession"]
