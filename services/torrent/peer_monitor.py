"""Периодический сбор статистики по пирам."""

import asyncio
import time
from dataclasses import dataclass, field

import config
from core.logging_setup import get_logger

log = get_logger("lt.peer_monitor")


@dataclass
class PeerStats:
    total_peers: int = 0
    connected_peers: int = 0
    peers_with_piece: int = 0
    top_peer_rates: list[int] = field(default_factory=list)
    sum_top_rates: int = 0
    payload_rate: int = 0
    total_done: int = 0
    timestamp: float = 0.0


class PeerMonitor:
    def __init__(self, geometry, interval: float = None):
        self.geometry = geometry
        self.interval = interval or getattr(config, "PEER_MONITOR_INTERVAL_SEC", 2.0)
        self.latest = PeerStats()
        self._task = None
        self._running = False

    def start(self):
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running and self.geometry.handle:
            try:
                await asyncio.sleep(self.interval)
                if not self.geometry.handle:
                    break
                self.latest = self._collect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("PeerMonitor: %s", e)

    def _collect(self) -> PeerStats:
        handle = self.geometry.handle
        if not handle:
            return PeerStats()
        try:
            st = handle.status()
            total_peers = st.num_peers
            payload_rate = int(st.download_payload_rate or 0)
            total_done = int(st.total_done or 0)
        except Exception:
            return PeerStats()

        try:
            peer_info = handle.get_peer_info()
        except Exception:
            peer_info = []

        connected = 0
        with_piece = 0
        current_piece = self.geometry.current_piece
        rates = []

        for p in peer_info:
            try:
                if p.flags & p.connecting or p.flags & p.handshake:
                    continue
                connected += 1
                rate = int(p.payload_down_speed or 0)
                if rate > 0:
                    rates.append(rate)
                if current_piece >= 0 and p.pieces.get_bit(current_piece):
                    with_piece += 1
            except Exception:
                continue

        rates.sort(reverse=True)
        top_n = rates[: getattr(config, "PEER_MONITOR_TOP_N", 5)]
        return PeerStats(
            total_peers=total_peers,
            connected_peers=connected,
            peers_with_piece=with_piece,
            top_peer_rates=top_n,
            sum_top_rates=sum(top_n),
            payload_rate=payload_rate,
            total_done=total_done,
            timestamp=time.time(),
        )

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
