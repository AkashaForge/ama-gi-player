"""
Управление Jackett.

DataFolder выбирается по числу индексаторов (больше = приоритет).
Логируется оба кандидата для прозрачности.
"""

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
import json
import os
import socket

import config
from core.logging_setup import get_logger
from services.process_cleaner import cleanup_zombie_jackett

log = get_logger("torrent_service")


def _count_indexers(data_dir: str) -> int:
    idx_dir = os.path.join(data_dir, "Indexers")
    if not os.path.isdir(idx_dir):
        return 0
    try:
        return sum(
            1 for f in os.listdir(idx_dir)
            if f.endswith(".json") and not f.endswith(".bak")
        )
    except Exception:
        return 0


def _list_indexer_names(data_dir: str) -> list[str]:
    idx_dir = os.path.join(data_dir, "Indexers")
    if not os.path.isdir(idx_dir):
        return []
    try:
        return [
            f.replace(".json", "")
            for f in os.listdir(idx_dir)
            if f.endswith(".json") and not f.endswith(".bak")
        ]
    except Exception:
        return []


class TorrentManager:
    def __init__(self):
        self.jackett_process = None
        self._resolved_data_dir: str | None = None
        self.backend: str | None = None
        self.port: int = 0
        self.api_key: str = ""

    # ==================================================================
    #  СОВМЕСТИМОСТЬ С ORCHESTRATOR
    # ==================================================================
    def get_backend_config(self) -> dict:
        if not self.backend:
            return {}
        return {
            "backend": self.backend,
            "base_url": f"http://127.0.0.1:{self.port}",
            "api_key": self.api_key,
        }

    # ==================================================================
    #  ВЫБОР DATAFOLDER
    # ==================================================================
    def _resolve_data_dir(self) -> str:
        primary = os.path.abspath(str(config.JACKETT_DATA_DIR))
        fallback = os.path.abspath(os.path.join(str(config.JACKETT_DIR), "Data"))

        primary_count = _count_indexers(primary)
        fallback_count = _count_indexers(fallback)
        primary_names = _list_indexer_names(primary)
        fallback_names = _list_indexer_names(fallback)

        log.info("DataFolder кандидаты:")
        log.info(
            "  [1] %s — %d индексаторов: %s",
            primary, primary_count,
            ", ".join(primary_names) if primary_names else "(пусто)",
        )
        log.info(
            "  [2] %s — %d индексаторов: %s",
            fallback, fallback_count,
            ", ".join(fallback_names) if fallback_names else "(пусто)",
        )

        if primary_count > fallback_count:
            log.info("DataFolder выбран: [1] %s (%d индексаторов)",
                     primary, primary_count)
            return primary
        if fallback_count > primary_count:
            log.info("DataFolder выбран: [2] %s (%d индексаторов)",
                     fallback, fallback_count)
            return fallback

        if primary_count > 0:
            log.info("DataFolder выбран: [1] %s (оба равны: %d)",
                     primary, primary_count)
            return primary
        if fallback_count > 0:
            log.info("DataFolder выбран: [2] %s (в primary пусто)", fallback)
            return fallback

        log.warning(
            "DataFolder: ни в одном из кандидатов нет индексаторов. "
            "Использую %s — Jackett создаст пустой конфиг. "
            "Открой http://127.0.0.1:%d/UI/Dashboard и добавь индексаторы.",
            primary, config.JACKETT_PORT,
        )
        return primary

    # ==================================================================
    #  SERVERCONFIG
    # ==================================================================
    def _extract_jackett_api_key(self, data_dir: str) -> str:
        path = os.path.join(data_dir, "ServerConfig.json")
        if not os.path.exists(path):
            return ""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            key = str(data.get("APIKey", "")).strip()
            if key:
                log.info("ServerConfig.json: %s", path)
                log.info("APIKey: *** (len=%d)", len(key))
            return key
        except Exception as e:
            log.warning("ServerConfig.json (%s): %s", path, e)
            return ""

    def _is_port_open(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    # ==================================================================
    #  START
    # ==================================================================
    async def start_services_async(self) -> bool:
        log.info("=== ИНИЦИАЛИЗАЦИЯ P2P ===")

        killed = cleanup_zombie_jackett()
        if killed > 0:
            log.info("Убито зомби Jackett при старте: %d", killed)
        await asyncio.sleep(1.0)

        data_dir = self._resolve_data_dir()
        self._resolved_data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        if not os.path.exists(str(config.JACKETT_EXE)):
            log.error("JackettConsole.exe не найден: %s", config.JACKETT_EXE)
            return False

        log.info("Запуск JackettConsole (DataFolder=%s)...", data_dir)
        try:
            await asyncio.create_subprocess_exec(
                str(config.JACKETT_EXE),
                "--ListenPrivate", "--NoUpdates",
                f"--Port={config.JACKETT_PORT}",
                f"--DataFolder={data_dir}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=0x00000008,
            )
        except Exception as e:
            log.error("Не удалось запустить Jackett: %s", e)
            return False

        detected_key = ""
        port_open = False
        for i in range(40):
            await asyncio.sleep(0.5)
            if not detected_key:
                detected_key = self._extract_jackett_api_key(data_dir)
                if detected_key:
                    log.info("Токен Jackett получен (%d символов)",
                             len(detected_key))
            if not port_open:
                port_open = self._is_port_open(config.JACKETT_PORT)
            if detected_key and port_open:
                break

        if not detected_key:
            log.error(
                "КРИТИЧНО: API-ключ Jackett не получен из %s. "
                "Проверь вручную: http://127.0.0.1:%d/UI/Dashboard",
                os.path.join(data_dir, "ServerConfig.json"),
                config.JACKETT_PORT,
            )
            return False

        if not port_open:
            log.error("КРИТИЧНО: порт %d не открылся", config.JACKETT_PORT)
            return False

        config.JACKETT_API_KEY = detected_key
        self.backend = "jackett"
        self.port = config.JACKETT_PORT
        self.api_key = detected_key
        log.info("Jackett готов, JACKETT_API_KEY установлен в config")
        return True

    def stop_services(self):
        log.info("Остановка Jackett...")
        self.backend = None
        self.port = 0
        self.api_key = ""
        killed = cleanup_zombie_jackett()
        if killed > 0:
            log.info("Убито Jackett: %d", killed)
