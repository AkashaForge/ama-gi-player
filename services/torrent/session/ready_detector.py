"""ReadyDetector v2.0.22 — не блокирует event loop.

Изменения:
  - piece_length кэшируется в HandleInfo
  - kill через callback (StreamSession делает async_remove_torrent)
  - _score_round не вызывает get_torrent_info() если piece_length уже кэширован
"""
import asyncio
import math
import time

import config
from core.logging_setup import get_logger
from services.torrent.session.handle_registry import HandleRegistry
from services.torrent.session.file_picker import RETRY, NO_VIDEO

log = get_logger("lt.session.ready_detector")


class ReadyDetector:
    def __init__(self, registry: HandleRegistry,
                 file_picker, on_prioritize, on_kill):
        self.registry = registry
        self.file_picker = file_picker
        self._on_prioritize = on_prioritize
        self._on_kill = on_kill

        self.grace = getattr(config, "STREAM_READY_GRACE_PERIOD_SEC", 5.0)
        self.margin = getattr(config, "STREAM_READY_BEST_SCORE_MARGIN", 2.0)
        self.kill_dead = getattr(config, "STREAM_KILL_DEAD_HANDLE_SEC", 10.0)
        self.kill_meta = getattr(config, "STREAM_KILL_DEAD_META_SEC", 30.0)
        self.kill_no_first = getattr(
            config, "STREAM_KILL_NO_FIRST_PIECE_SEC", 45.0
        )
        self.min_rate = getattr(config, "PROBE_MIN_RATE_MB", 0.2) * 1024 * 1024
        self.min_peers = getattr(config, "PROBE_MIN_PEERS", 10)
        self.poll_sec = 1.0

    async def detect(self, timeout: float, cancelled_check):
        start = time.time()
        last_log = 0.0
        first_ready_ts = None
        best_info = None
        best_score = -1.0
        best_key = -1

        while time.time() - start < timeout and not cancelled_check():
            await asyncio.sleep(self.poll_sec)
            now = time.time()

            self._kill_dead(now)

            winner = self._score_round()
            if winner is None:
                if len(self.registry) == 0:
                    return None
                if now - last_log > 3.0:
                    self._log_state(now - start)
                    last_log = now
                continue

            info, score = winner

            if first_ready_ts is None:
                first_ready_ts = now
                best_info = info
                best_score = score
                best_key = info.key
                log.info(
                    "First ready: %d peers, %.2f MB/s, has_first=%s, "
                    "piece=%dMB, size=%.0fMB, score=%.0f, grace %.0fs — '%s'",
                    info.last_peers, info.last_rate / 1024 / 1024,
                    info.last_has_first,
                    info.piece_length // (1024 * 1024),
                    info.size_declared / 1024 / 1024 if info.size_declared else 0,
                    score, self.grace, info.title[:50],
                )
            elif score > best_score * self.margin:
                if info.key != best_key:
                    log.info(
                        "Better (switch): %.0f → %.0f (peers=%d, %.2f MB/s, "
                        "has_first=%s) — '%s'",
                        best_score, score, info.last_peers,
                        info.last_rate / 1024 / 1024, info.last_has_first,
                        info.title[:50],
                    )
                    best_info = info
                    best_score = score
                    best_key = info.key
                    first_ready_ts = now
                else:
                    best_score = score

            elapsed = now - first_ready_ts
            if elapsed >= self.grace and self._pending_no_meta() == 0:
                log.info(
                    "Grace expired — chose: %d peers, %.2f MB/s, "
                    "has_first=%s, piece=%dMB — '%s'",
                    best_info.last_peers,
                    best_info.last_rate / 1024 / 1024,
                    best_info.last_has_first,
                    best_info.piece_length // (1024 * 1024),
                    best_info.title[:50],
                )
                return best_info
            elif elapsed >= self.grace * 2:
                log.info("Extended grace — using current best")
                return best_info

            if now - last_log > 3.0:
                self._log_state(now - start)
                last_log = now

        log.warning("Ready timeout %.0fs", timeout)
        return best_info

    # ==================================================================
    #  СКОРИНГ
    # ==================================================================
    def _score_round(self):
        best = None
        best_score = -1.0

        for info in self.registry:
            if info.is_rejected:
                continue
            handle = info.handle
            try:
                if not handle.is_valid():
                    continue
                if not handle.has_metadata():
                    continue
            except Exception:
                continue

            # Pick + кэш piece_length (только один раз)
            if info.file_idx == -1 or info.piece_length == 0:
                try:
                    ti = handle.get_torrent_info()
                except Exception as e:
                    log.debug("[score] get_torrent_info: %s", e)
                    continue
                if ti is None:
                    continue

                if info.file_idx == -1:
                    file_idx = self.file_picker.pick(ti)
                    if file_idx == RETRY:
                        continue
                    if file_idx == NO_VIDEO:
                        log.info("[score] %s: NO_VIDEO → rejected", info.key)
                        info.mark_rejected()
                        continue
                    if file_idx < 0:
                        log.info("[score] %s: pick=%d → rejected",
                                 info.key, file_idx)
                        info.mark_rejected()
                        continue
                    info.file_idx = file_idx
                    try:
                        info.first_piece = self._on_prioritize(handle, ti, file_idx)
                    except Exception as e:
                        log.warning("[score] prioritize: %s", e)

                try:
                    info.piece_length = ti.piece_length()
                except Exception:
                    info.piece_length = 0

            try:
                st = handle.status()
                num_peers = st.num_peers
                rate = int(st.download_payload_rate or 0)
            except Exception:
                continue
            if num_peers < 1:
                continue

            try:
                has_first = handle.have_piece(info.first_piece) \
                    if info.first_piece >= 0 else False
            except Exception:
                has_first = False

            info.last_peers = num_peers
            info.last_rate = rate
            info.last_has_first = has_first

            is_ready = has_first or (
                rate > self.min_rate and num_peers >= self.min_peers
            )
            has_first_mult = 1.5 if is_ready else 1.0

            piece_mult = self._piece_multiplier(
                info.piece_length or 1024 * 1024
            )

            peer_f = 1.0 + math.log10(max(1, num_peers))
            score = (rate / 1024.0) * peer_f * has_first_mult * piece_mult

            if score > best_score:
                best_score = score
                best = (info, score)

        return best

    def _piece_multiplier(self, piece_len: int) -> float:
        if piece_len <= 1 * 1024 * 1024:
            return 1.2
        if piece_len <= 2 * 1024 * 1024:
            return 1.0
        if piece_len <= 4 * 1024 * 1024:
            return 0.7
        if piece_len <= 8 * 1024 * 1024:
            return 0.4
        return 0.2

    # ==================================================================
    #  KILL DEAD — через callback (StreamSession делает async_remove_torrent)
    # ==================================================================
    def _kill_dead(self, now: float) -> None:
        to_remove = []
        for info in self.registry:
            age = now - info.first_seen
            try:
                if not info.handle.is_valid():
                    to_remove.append((info, "invalid"))
                    continue
                st = info.handle.status()
                rate = int(st.download_payload_rate or 0)
                peers = st.num_peers
                has_meta = info.handle.has_metadata()

                if rate > self.min_rate or peers > 5:
                    continue

                if has_meta and not info.is_rejected:
                    if info.first_piece >= 0:
                        try:
                            has_first = info.handle.have_piece(info.first_piece)
                        except Exception:
                            has_first = False
                        if has_first:
                            info.first_piece_seen = now
                        else:
                            fp_age = now - (info.first_piece_seen or info.first_seen)
                            if (peers == 0 and st.total_done == 0
                                    and age > self.kill_dead):
                                to_remove.append((info, f"no peers {age:.0f}s"))
                                continue
                            if fp_age > self.kill_no_first:
                                to_remove.append((info, f"no first {fp_age:.0f}s"))
                                continue
                elif not has_meta:
                    if age > self.kill_meta:
                        to_remove.append((info, f"no metadata {age:.0f}s"))
            except Exception:
                continue

        for info, reason in to_remove:
            log.info("Kill %s: %s", info.key, reason)
            self._on_kill(info.handle)          # callback — async_remove_torrent
            self.registry.remove(info.handle)

    def _pending_no_meta(self) -> int:
        count = 0
        for info in self.registry:
            try:
                if (not info.handle.has_metadata()
                        and info.handle.status().num_peers > 0):
                    count += 1
            except Exception:
                pass
        return count

    def _log_state(self, elapsed: float) -> None:
        parts = []
        for i, info in enumerate(self.registry):
            try:
                st = info.handle.status()
                hm = "Y" if info.handle.has_metadata() else "N"
                fp = ""
                if info.first_piece >= 0:
                    try:
                        fp = " first=Y" if info.handle.have_piece(info.first_piece) else " first=N"
                    except Exception:
                        pass
                fi = f" idx={info.file_idx}" if info.file_idx >= 0 else ""
                rj = " REJ" if info.is_rejected else ""
                r = st.download_payload_rate / 1024 / 1024
                parts.append(
                    f"[{i}] meta={hm} peers={st.num_peers} "
                    f"rate={r:.2f}MB/s done={st.total_done/1024/1024:.1f}MB"
                    f"{fi}{fp}{rj}"
                )
            except Exception:
                parts.append(f"[{i}] ?")
        log.info("wait_ready %.1fs: %s", elapsed, " | ".join(parts))