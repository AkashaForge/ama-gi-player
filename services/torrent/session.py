"""Создание libtorrent session с настройками для стриминга (libtorrent 2.1.1)."""

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

import libtorrent as lt

from core.logging_setup import get_logger

log = get_logger("lt.session")


def create_session(listen_port: int) -> lt.session:
    """
    Создаёт сессию libtorrent с настройками, оптимизированными для
    низкой задержки и быстрого старта стриминга.
    Основано на рекомендациях из issue #7666.
    """
    settings = {
        'listen_interfaces': f'0.0.0.0:{listen_port},[::]:{listen_port}',
        'enable_dht': True,
        'enable_lsd': True,
        'enable_upnp': True,
        'enable_natpmp': True,
        'download_rate_limit': 0,
        'upload_rate_limit': 0,
        'alert_mask': (
            lt.alert.category_t.error_notification
            | lt.alert.category_t.status_notification
            | lt.alert.category_t.storage_notification
        ),

        # === Ключевые настройки для стриминга ===
        # Отключаем "плавные" соединения, чтобы быстрее подключаться к пирам
        'smooth_connects': False,
        # Увеличиваем скорость установки соединений
        'connection_speed': 200,
        # Даём "буст" новым торрентам для быстрого набора пиров
        'torrent_connect_boost': 100,
        # Минимальное время между переподключениями
        'min_reconnect_time': 1,
        # Таймауты, чтобы быстрее отбрасывать мёртвые соединения
        'peer_connect_timeout': 3,
        'piece_timeout': 10,
        'request_timeout': 10,
        'peer_timeout': 10,
        'urlseed_timeout': 10, # Важно для избежания глитчей при редиректе данных

        # Отключаем дисковый кэш — данные идут напрямую в HTTP-сервер
        'cache_size': 0,
        'cache_expiry': 0,
    }
    ses = lt.session(settings)
    for host in ("router.bittorrent.com", "router.utorrent.com",
                 "dht.transmissionbt.com", "dht.libtorrent.org"):
        try:
            ses.add_dht_router(host, 6881)
        except Exception as e:
            log.warning("DHT %s: %s", host, e)
    log.info("Session OK: port=%d (streaming settings applied)", listen_port)
    return ses
