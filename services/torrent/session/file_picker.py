"""FilePicker v2.0.20 — либеральный выбор видеофайла.

Принципы:
  - Не отбраковывает по году (только предпочитает правильный).
  - Если по расширению ничего нет — берёт ЛЮБОЙ файл ≥ 20 MB (fallback).
  - Пустой/неполный torrent_info (num_files=0) — возвращает специальный код RETRY.
  - Логирует причины на INFO.
"""
import os
import re

import config
from core.logging_setup import get_logger

log = get_logger("lt.session.file_picker")

_YEAR_RE = re.compile(r'\b(19\d{2}|20\d{2})\b')

RETRY = -2      # torrent_info неполный, попробовать позже
NO_VIDEO = -1   # в торренте нет видеофайла


class FilePicker:
    MULTI_FILE_THRESHOLD_GB = getattr(config, "MULTI_FILE_THRESHOLD_GB", 5)
    MULTI_FILE_MAX_COUNT = getattr(config, "MULTI_FILE_MAX_COUNT", 2)
    MAX_STREAMABLE_FILE_GB = getattr(config, "MAX_STREAMABLE_FILE_GB", 35)
    MIN_FILE_MB = 20

    def __init__(self, year: str = ""):
        self.year = (year or "").strip()
        self._exts = tuple(getattr(config, "LIBTORRENT_STREAMABLE_EXTS", (
            ".mp4", ".mkv", ".webm", ".m4v", ".mov", ".wmv", ".flv"
        )))
        self._reject = tuple(getattr(config, "LIBTORRENT_REJECT_EXTS", (
            ".vob", ".ifo", ".bup", ".ts", ".m2ts", ".mts", ".mpg",
            ".mpeg", ".rmvb", ".divx", ".asf", ".3gp", ".ogv", ".f4v", ".avi"
        )))
        self._allow_ts = getattr(config, "LIBTORRENT_ALLOW_TS_FALLBACK", True)
        self._ts_exts = (".ts", ".m2ts", ".mts")
        self._debug = getattr(config, "DEBUG_PICK_FILE", False)

    def pick(self, info) -> int:
        """
        Возвращает:
          >= 0   — индекс видеофайла
          NO_VIDEO (-1) — в торренте точно нет видео
          RETRY (-2) — torrent_info неполный, попробовать позже
        """
        # === Проверка на неполный torrent_info ===
        try:
            num_files = info.files().num_files()
        except Exception as e:
            log.debug("[pick] files() error: %s", e)
            return RETRY

        if num_files == 0:
            log.debug("[pick] torrent_info incomplete (num_files=0) → RETRY")
            return RETRY

        min_size = self.MIN_FILE_MB * 1024 * 1024
        max_streamable = self.MAX_STREAMABLE_FILE_GB * 1024 ** 3
        big_threshold = self.MULTI_FILE_THRESHOLD_GB * 1024 ** 3

        candidates: list[tuple[int, int]] = []       # видео с правильным годом
        candidates_wrong_year: list[tuple[int, int]] = []
        ts_candidates: list[tuple[int, int]] = []
        any_big_files: list[tuple[int, int, str]] = []  # fallback
        big_count = 0

        for i in range(num_files):
            try:
                fp = info.files().file_path(i)
                size = info.files().file_size(i)
            except Exception as e:
                log.debug("[pick] file_path(%d): %s", i, e)
                continue

            basename = os.path.basename(fp)
            p = fp.lower()

            # Мусор — сразу мимо
            if size < min_size:
                continue
            if size > max_streamable:
                continue

            # Fallback кандидат — самый большой файл, если вообще ничего не найдём
            any_big_files.append((i, size, basename))

            is_ts = any(p.endswith(ext) for ext in self._ts_exts)
            is_video = p.endswith(self._exts)
            is_reject_ext = p.endswith(self._reject)

            if is_ts:
                if not self._allow_ts:
                    continue
                ts_candidates.append((i, size))
                if self._debug:
                    log.info("[pick] [%d] %s → TS fallback (%d MB)",
                             i, basename[:60], size // 1024 // 1024)
                continue

            if is_reject_ext:
                if self._debug:
                    log.info("[pick] [%d] %s → REJECT (ext)", i, basename[:60])
                continue

            if not is_video:
                if self._debug:
                    log.info("[pick] [%d] %s → not video ext", i, basename[:60])
                continue

            # Проверка года — только предпочтение, не reject
            year_ok = True
            if self.year:
                fy = _YEAR_RE.findall(basename)
                if fy:
                    try:
                        expected = int(self.year)
                        year_ok = any(abs(int(y) - expected) <= 1 for y in fy)
                    except ValueError:
                        year_ok = True

            if year_ok:
                candidates.append((i, size))
                if size > big_threshold:
                    big_count += 1
                if self._debug:
                    log.info("[pick] [%d] %s → candidate (%d MB)",
                             i, basename[:60], size // 1024 // 1024)
            else:
                candidates_wrong_year.append((i, size))
                if self._debug:
                    log.info("[pick] [%d] %s → wrong year (fallback)",
                             i, basename[:60])

        # === Мультифайл-детектор ===
        if big_count > self.MULTI_FILE_MAX_COUNT:
            log.warning("[pick] %d big files → collection, reject", big_count)
            return NO_VIDEO

        # === Приоритеты ===
        if candidates:
            best = max(candidates, key=lambda c: c[1])
            if self._debug:
                log.info("[pick] CHOSEN: idx=%d (%.1f MB) [correct year]",
                         best[0], best[1] / 1024 / 1024)
            return best[0]

        if candidates_wrong_year:
            best = max(candidates_wrong_year, key=lambda c: c[1])
            log.warning("[pick] only wrong-year files, using idx=%d (%.1f MB)",
                        best[0], best[1] / 1024 / 1024)
            return best[0]

        if ts_candidates:
            best = max(ts_candidates, key=lambda c: c[1])
            log.info("[pick] TS fallback: idx=%d (%.1f MB)",
                     best[0], best[1] / 1024 / 1024)
            return best[0]

        # === Fallback: любой большой файл (а вдруг это видео с экзотическим ext) ===
        if any_big_files:
            # Если файлов >= 10 и все небольшие — вероятно не фильм
            if len(any_big_files) >= 10 and len(any_big_files) > num_files // 2:
                log.warning("[pick] %d non-video files → not a movie",
                            len(any_big_files))
                return NO_VIDEO
            best = max(any_big_files, key=lambda c: c[1])
            log.warning("[pick] no recognized video ext — using biggest "
                        "file idx=%d (%.1f MB) as fallback",
                        best[0], best[1] / 1024 / 1024)
            return best[0]

        log.warning("[pick] no suitable file in torrent (num_files=%d)",
                    num_files)
        return NO_VIDEO