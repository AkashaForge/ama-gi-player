"""Создание libtorrent session с настройками для стриминга.

Переименован из session.py → lt_session.py, чтобы не конфликтовать
с пакетом services/torrent/session/.
"""
import libtorrent as lt

import config
from core.logging_setup import get_logger

log = get_logger("lt.session")


def create_session(listen_port: int) -> lt.session:
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
        'smooth_connects': config.LIBTORRENT_SMOOTH_CONNECTS,
        'connection_speed': config.LIBTORRENT_CONNECTION_SPEED,
        'torrent_connect_boost': config.LIBTORRENT_TORRENT_CONNECT_BOOST,
        'min_reconnect_time': config.LIBTORRENT_MIN_RECONNECT_TIME,
        'peer_connect_timeout': config.LIBTORRENT_PEER_CONNECT_TIMEOUT,
        'piece_timeout': config.LIBTORRENT_PIECE_TIMEOUT,
        'request_timeout': config.LIBTORRENT_REQUEST_TIMEOUT,
        'peer_timeout': config.LIBTORRENT_PEER_TIMEOUT,
        'urlseed_timeout': 10,
        'cache_size': config.LIBTORRENT_CACHE_SIZE,
        'cache_expiry': config.LIBTORRENT_CACHE_EXPIRY,
    }
    ses = lt.session(settings)
    for host in ("router.bittorrent.com", "router.utorrent.com",
                 "dht.transmissionbt.com", "dht.libtorrent.org"):
        try:
            ses.add_dht_router(host, 6881)
        except Exception as e:
            log.warning("DHT %s: %s", host, e)
    log.info("Session OK: port=%d", listen_port)
    return ses