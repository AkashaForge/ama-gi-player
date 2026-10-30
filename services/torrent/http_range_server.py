"""HTTP Range-сервер с кэшем пиесов и неблокирующим чтением."""

# Amagi-Player — desktop media player for public-domain content
# Copyright (C) 2026 AkashaForge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import re
import time
from collections import OrderedDict

from aiohttp import web

import config
from core.logging_setup import get_logger

log = get_logger("lt.http_range")

_RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)')


class HttpRangeServer:
    def __init__(self, session):
        self.session = session
        self.host = "127.0.0.1"
        self.port = 0
        self._runner = None
        self._site = None
        self._allowed_hosts = set()
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._cache_limit = getattr(config, "HTTP_RANGE_CACHE_PIECES", 8)
        self.chunk_size = getattr(
            config, "HTTP_RANGE_CHUNK_SIZE", 1024 * 1024
        )
        self.poll_sec = getattr(config, "HTTP_RANGE_POLL_SEC", 0.05)

    async def start(self) -> str:
        app = web.Application()
        app.router.add_get("/stream", self._handle_stream)
        app.router.add_get("/health", self._handle_health)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        socks = self._site._server.sockets
        if socks:
            s = socks[0].getsockname()
            self.port = s[1] if isinstance(s, tuple) else s
        else:
            self.port = 8080
        self._allowed_hosts = {
            f"127.0.0.1:{self.port}",
            f"localhost:{self.port}",
            f"[::1]:{self.port}",
        }
        return f"http://{self.host}:{self.port}/stream"

    async def _handle_health(self, request):
        return web.Response(text="OK")

    def _check_host(self, request):
        """Защита от Host-header bypass.

        Раньше пустой/отсутствующий Host считался «своим». Теперь — нет:
        запрос без Host или с чужим Host отклоняется (403).
        """
        host = request.headers.get("Host", "")
        if not host:
            return False
        return host in self._allowed_hosts

    @staticmethod
    def _parse_range(header, file_size):
        if not header:
            return None, None
        m = _RANGE_RE.match(header.strip())
        if not m:
            return None, None
        start_s, end_s = m.group(1), m.group(2)
        if start_s == "" and end_s == "":
            return None, None
        if start_s == "":
            suffix = int(end_s)
            if suffix <= 0:
                return None, None
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            return None, None
        return start, end

    def _cache_get(self, piece):
        if piece in self._cache:
            self._cache.move_to_end(piece)
            return self._cache[piece]
        return None

    def _cache_put(self, piece, data):
        self._cache[piece] = data
        self._cache.move_to_end(piece)
        while len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)

    async def _handle_stream(self, request):
        if not self._check_host(request):
            return web.Response(status=403, text="Forbidden")

        session = self.session
        if not session or not session.is_active():
            return web.Response(status=503, text="Stream not active")

        file_size = session.file_size
        range_header = request.headers.get("Range")

        if range_header:
            start, end = self._parse_range(range_header, file_size)
            if start is None:
                raise web.HTTPRequestRangeNotSatisfiable(
                    headers={"Content-Range": f"bytes */{file_size}"}
                )
            status = 206
        else:
            start, end = 0, file_size - 1
            status = 200

        headers = {
            "Content-Type": session.content_type,
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        response = web.StreamResponse(status=status, headers=headers)
        await response.prepare(request)

        if start > 0:
            session.scheduler.on_seek(start)

        transport = request.transport
        current = start
        bytes_left = end - start + 1
        current_piece = -1
        current_data = b""
        data_offset = 0
        current_piece_byte_start = -1
        current_piece_byte_end = -1

        def is_client_alive():
            return transport is not None and not transport.is_closing()

        try:
            while bytes_left > 0:
                if not session.is_active():
                    log.info("Stream stopped by session")
                    break
                if not is_client_alive():
                    log.info("Client disconnected")
                    break

                if (current_piece >= 0
                        and current_piece_byte_start <= current < current_piece_byte_end):
                    piece = current_piece
                else:
                    piece = session.geometry.piece_for_byte(current)
                    if piece < 0:
                        await asyncio.sleep(self.poll_sec)
                        continue

                if piece != current_piece:
                    session.scheduler.on_position(current)

                    wait_start = time.time()
                    ok = await session.wait_for_piece(piece, is_client_alive)
                    wait_elapsed = time.time() - wait_start

                    if not ok:
                        log.warning(
                            "wait_piece %d FAILED after %.1fs (client dead or cancelled)",
                            piece, wait_elapsed,
                        )
                        break

                    if wait_elapsed > 2.0:
                        stats = session.stats
                        log.warning(
                            "piece %d готов через %.1fs (conn=%d, rate=%.2f MB/s)",
                            piece, wait_elapsed, stats.connected_peers,
                            stats.payload_rate / 1024 / 1024,
                        )

                    data = self._cache_get(piece)
                    if data is None:
                        data = await session.read_piece(piece)
                        if data is None:
                            await asyncio.sleep(self.poll_sec)
                            continue
                        self._cache_put(piece, data)

                    current_piece = piece
                    current_data = data
                    start_in_file, end_in_file = session.geometry.byte_range_for_piece(piece)
                    current_piece_byte_start = start_in_file
                    current_piece_byte_end = end_in_file
                    data_offset = max(0, current - start_in_file)

                available = len(current_data) - data_offset
                if available <= 0:
                    current_piece = -1
                    current_piece_byte_start = -1
                    current_piece_byte_end = -1
                    continue

                this_chunk = min(self.chunk_size, bytes_left, available)
                data_out = current_data[data_offset:data_offset + this_chunk]
                try:
                    await response.write(data_out)
                except (ConnectionResetError, ConnectionAbortedError) as e:
                    log.info("Client disconnected during write: %s", e)
                    break
                current += len(data_out)
                data_offset += len(data_out)
                bytes_left -= len(data_out)

            if bytes_left == 0:
                try:
                    await response.write_eof()
                except Exception:
                    pass

        except (ConnectionResetError, ConnectionAbortedError, asyncio.CancelledError):
            log.info("Client connection lost")
        except Exception as e:
            log.error("HTTP stream: %s: %s", type(e).__name__, e)

        return response

    async def stop(self):
        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception:
                pass
        self._runner = None
        self._site = None
        self._cache.clear()