"""Плеер: QStackedLayout (video_widget ↔ loader) с баром управления и кнопкой Skip."""

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

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)


class MoviePlayerWidget(QWidget):
    close_player_requested = pyqtSignal(int)
    seek_requested = pyqtSignal(int)
    skip_requested = pyqtSignal()
    source_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_seconds = 0
        self._slider_moving = False
        self._init_layout()

    def _init_layout(self):
        self.setStyleSheet("background-color: #000000;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(10)

        # Верхняя панель
        top_bar = QHBoxLayout()
        self.exit_btn = QPushButton("✕ ЗАКРЫТЬ ТРАНСЛЯЦИЮ", self)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setStyleSheet("""
            QPushButton { padding: 6px 12px; color: rgba(255,255,255,0.6); font-weight: bold; }
            QPushButton:hover { color: #ffffff; }
        """)
        self.exit_btn.clicked.connect(
            lambda: self.close_player_requested.emit(self._current_seconds)
        )
        top_bar.addWidget(self.exit_btn)
        top_bar.addStretch()
        self.main_layout.addLayout(top_bar)

        # Центральная зона
        self.center_stack = QStackedLayout()

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.center_stack.addWidget(self.video_widget)

        self.loader_container = QWidget()
        self.loader_container.setStyleSheet("background-color: #000000;")
        loader_layout = QVBoxLayout(self.loader_container)
        loader_layout.setSpacing(15)
        loader_layout.addStretch()

        self.loader_label = QLabel("ПОСЛЕДОВАТЕЛЬНАЯ БУФЕРИЗАЦИЯ P2P ПОТОКА...",
                                    self.loader_container)
        self.loader_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loader_label.setStyleSheet(
            "color: #FFFFFF; font-size: 12px; font-weight: 800; letter-spacing: 3px;"
        )
        loader_layout.addWidget(self.loader_label)

        self.p2p_progress = QProgressBar(self.loader_container)
        self.p2p_progress.setFixedHeight(2)
        self.p2p_progress.setTextVisible(False)
        self.p2p_progress.setStyleSheet("""
            QProgressBar { background-color: rgba(255,255,255,0.1); border: none; }
            QProgressBar::chunk { background-color: #FFFFFF; }
        """)
        self.p2p_progress.setValue(0)
        loader_layout.addWidget(self.p2p_progress)

        loader_layout.addStretch()
        self.center_stack.addWidget(self.loader_container)

        center_widget = QWidget(self)
        center_widget.setLayout(self.center_stack)
        self.main_layout.addWidget(center_widget, stretch=1)

        # Нижний бар
        self.controls_bar = QWidget(self)
        self.controls_bar.setStyleSheet("""
            QWidget { background-color: #050505; }
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 18px;
                font-weight: bold;
                min-width: 35px;
                min-height: 35px;
            }
            QPushButton:hover { color: #00adb5; }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00adb5;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 12px;
                height: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
        """)

        controls_layout = QVBoxLayout(self.controls_bar)
        controls_layout.setContentsMargins(10, 5, 10, 5)
        controls_layout.setSpacing(5)

        self.timeline_slider = QSlider(Qt.Orientation.Horizontal, self.controls_bar)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.sliderPressed.connect(self._on_slider_pressed)
        self.timeline_slider.sliderReleased.connect(self._on_slider_released)
        controls_layout.addWidget(self.timeline_slider)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        self.play_pause_button = QPushButton("⏸", self.controls_bar)
        self.play_pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons_layout.addWidget(self.play_pause_button)

        self.time_label = QLabel("00:00 / --:--", self.controls_bar)
        self.time_label.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 12px; font-weight: 700;"
        )
        buttons_layout.addWidget(self.time_label)
        buttons_layout.addStretch()

        self.skip_button = QPushButton("⏭", self.controls_bar)
        self.skip_button.setToolTip("Скипнуть раздачу")
        self.skip_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_button.clicked.connect(self.skip_requested.emit)
        buttons_layout.addWidget(self.skip_button)

        self.fullscreen_button = QPushButton("⛶", self.controls_bar)
        self.fullscreen_button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons_layout.addWidget(self.fullscreen_button)

        controls_layout.addLayout(buttons_layout)
        self.main_layout.addWidget(self.controls_bar)

    def _on_slider_pressed(self):
        self._slider_moving = True

    def _on_slider_released(self):
        self._slider_moving = False
        self.seek_requested.emit(self.timeline_slider.value())

    def show_loader(self):
        self.center_stack.setCurrentIndex(1)

    def show_video(self):
        self.center_stack.setCurrentIndex(0)

    def set_buffering_progress(self, percentage: int):
        self.p2p_progress.setValue(percentage)
        if percentage >= 100:
            self.loader_label.setText("ВОСПРОИЗВЕДЕНИЕ")

    def show_source_picker(self, alternatives: list[dict]):
        from ui.source_picker_dialog import SourcePickerDialog
        dlg = SourcePickerDialog(alternatives, self)
        dlg.source_selected.connect(self.source_selected.emit)
        dlg.exec()
