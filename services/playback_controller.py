"""Контроллер воспроизведения. Demuxing error → сигнал."""

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

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QWidget


class PlaybackController(QObject):
    demux_error = pyqtSignal()

    def __init__(self, player_page, main_window=None, parent=None):
        super().__init__(parent)
        self.player_page = player_page
        self.main_window = main_window or parent

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self._resume_seconds = 0
        self._resume_hook_connected = False
        self._current_url = ""

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick_ui)

        self.current_movie_id = None
        self.current_movie_title = ""
        self._is_fullscreen = False
        self._saved_geometry = None

        try:
            self.player.errorOccurred.connect(self._on_player_error)
        except Exception:
            pass

        self._bind_ui_controls()

    def _bind_ui_controls(self):
        if hasattr(self.player_page, "play_pause_button"):
            self.player_page.play_pause_button.clicked.connect(self.toggle_play_pause)
        if hasattr(self.player_page, "fullscreen_button"):
            self.player_page.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        if hasattr(self.player_page, "seek_requested"):
            self.player_page.seek_requested.connect(self._handle_manual_seek)
        if self.main_window:
            self.main_window.keyPressEvent = self._handle_key_press

    def _on_player_error(self, error, error_string):
        from core.logging_setup import get_logger
        try:
            get_logger("playback").warning("player error: %s %s",
                                             error, error_string)
        except Exception:
            pass
        self.demux_error.emit()

    def play_url(self, stream_url: str, movie_id: int, title: str):
        self.current_movie_id = movie_id
        self.current_movie_title = title
        self._current_url = stream_url

        from database.history_repo import HistoryRepository
        self._resume_seconds = HistoryRepository.get_seconds_for_movie(movie_id)

        self.player_page.set_buffering_progress(100)
        self.player_page.show_video()
        self.player.setVideoOutput(self.player_page.video_widget)

        if self._resume_seconds > 5 and not self._resume_hook_connected:
            self._resume_hook_connected = True
            self.player.mediaStatusChanged.connect(self._on_media_status_seek)

        self.player.setSource(QUrl(stream_url))
        self.player.play()
        self._timer.start()

        if hasattr(self.player_page, "play_pause_button"):
            self.player_page.play_pause_button.setText("⏸")

    def reload_url(self):
        if not self._current_url:
            return
        from core.logging_setup import get_logger
        get_logger("playback").info("Перезагрузка URL: %s",
                                      self._current_url[:80])
        self.player.setSource(QUrl(self._current_url))
        self.player.play()

    def toggle_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            if hasattr(self.player_page, "play_pause_button"):
                self.player_page.play_pause_button.setText("▶")
        else:
            self.player.play()
            if hasattr(self.player_page, "play_pause_button"):
                self.player_page.play_pause_button.setText("⏸")

    def _handle_manual_seek(self, slider_value: int):
        duration = self.player.duration()
        if duration > 0:
            target_ms = int((slider_value / 1000) * duration)
            self.player.setPosition(target_ms)

    def stop_stream(self, save: bool = False):
        self._timer.stop()
        real_seconds = (max(0, self.player.position() // 1000)
                        if self.player.source().isValid() else 0)

        if self._is_fullscreen:
            self.toggle_fullscreen()

        self.player.stop()
        self.player.setSource(QUrl())
        self._current_url = ""

        if save and self.current_movie_id is not None and real_seconds > 5:
            from database.history_repo import HistoryRepository
            HistoryRepository.save_timestamp(
                self.current_movie_id, self.current_movie_title, real_seconds,
            )

        self._resume_seconds = 0

    def stop_and_save(self):
        self.stop_stream(save=True)

    def toggle_fullscreen(self):
        if not self.main_window:
            return

        if not self._is_fullscreen:
            self._is_fullscreen = True
            self._saved_geometry = self.main_window.geometry()
            if hasattr(self.main_window, "header_bar"):
                self.main_window.header_bar.hide()
            self.main_window.setWindowFlags(
                Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
            )
            self.main_window.showMaximized()
            self.main_window.show()
        else:
            self._is_fullscreen = False
            self.main_window.setWindowFlags(Qt.WindowType.Window)
            self.main_window.showNormal()
            if self._saved_geometry is not None:
                self.main_window.setGeometry(self._saved_geometry)
                self._saved_geometry = None
            if hasattr(self.main_window, "header_bar"):
                self.main_window.header_bar.show()

    def _handle_key_press(self, event):
        if event.key() == Qt.Key.Key_Escape and self._is_fullscreen:
            self.toggle_fullscreen()
        else:
            QWidget.keyPressEvent(self.main_window, event)

    def _on_media_status_seek(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._resume_seconds > 5:
            self.player.setPosition(self._resume_seconds * 1000)
            self._resume_seconds = 0
            try:
                self.player.mediaStatusChanged.disconnect(
                    self._on_media_status_seek
                )
            except Exception:
                pass
            self._resume_hook_connected = False

    def _tick_ui(self):
        if not hasattr(self.player_page, "time_label"):
            return

        pos_ms = self.player.position()
        pos = max(0, pos_ms // 1000) if pos_ms else 0
        duration_ms = self.player.duration()

        if duration_ms > 0:
            dur_sec = duration_ms // 1000
            d_mm, d_ss = divmod(dur_sec, 60)
            duration_str = f"{d_mm:02d}:{d_ss:02d}"
            if (hasattr(self.player_page, "timeline_slider")
                    and not self.player_page._slider_moving):
                slider_pos = int((pos_ms / duration_ms) * 1000)
                self.player_page.timeline_slider.setValue(slider_pos)
        else:
            duration_str = "--:--"

        mm, ss = divmod(pos, 60)
        self.player_page.time_label.setText(f"{mm:02d}:{ss:02d} / {duration_str}")
