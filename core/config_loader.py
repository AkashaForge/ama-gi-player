"""Загрузчик пользовательских источников из data/sources.txt."""

from pathlib import Path

import config
from core.logging_setup import get_logger

log = get_logger("config_loader")

_EXPECTED_FIELDS = 7


def _parse_line(line: str, line_num: int) -> dict | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = [p.strip() for p in line.split("|")]
    if len(parts) != _EXPECTED_FIELDS:
        log.warning("sources.txt:%d — ожидалось %d полей, получено %d",
                    line_num, _EXPECTED_FIELDS, len(parts))
        return None

    source_id = parts[0].lower()
    if not source_id.replace("-", "").replace("_", "").isalnum():
        log.warning("sources.txt:%d — некорректный id: %s",
                    line_num, source_id)
        return None

    return {
        "id": source_id,
        "name": parts[1],
        "url_template": parts[2],
        "ready_selector": parts[3],
        "magnet_selector": parts[4],
        "title_selector": parts[5],
        "seeders_selector": parts[6],
    }


def load_custom_sources() -> list[dict]:
    path = Path(config.CUSTOM_SOURCES_FILE)
    if not path.exists():
        log.info("sources.txt отсутствует — пользовательские источники отключены")
        return []

    sources = []
    try:
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                parsed = _parse_line(line, line_num)
                if parsed is not None:
                    sources.append(parsed)
    except Exception as e:
        log.warning("sources.txt: ошибка чтения: %s", e)
        return []

    if sources:
        log.info("Загружено пользовательских источников: %d", len(sources))
    else:
        log.info("sources.txt пуст — пользовательские источники не активны")

    return sources
