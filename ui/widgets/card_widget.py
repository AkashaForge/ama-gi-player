"""Карточка фильма — Bento style.

v2.0.5:
  - постер заполняет верх (220×260), закруглён сверху;
  - снизу сплошная плашка #cardInfoBar (220×80) с title+year;
  - в light-теме плашка тёмная, при hover — терракотовая;
  - без inline-стилей, все цвета через QSS.
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

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


_CARD_W = 220
_CARD_H = 340
_POSTER_H = 260
_BAR_H = 80


class MovieCardWidget(QWidget):
    play_requested = pyqtSignal(int)

    def __init__(self, kp_id: int, title: str, year: str,
                 cover_path: str, parent=None):
        super().__init__(parent)
        self.kp_id = kp_id
        self.title = title
        self.year = year
        self.cover_path = cover_path
        self._init_card_layout()

    def _init_card_layout(self):
        self.setFixedSize(_CARD_W, _CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Постер — верхняя часть, закруглён сверху
        self.cover_label = QLabel(self)
        self.cover_label.setGeometry(0, 0, _CARD_W, _POSTER_H)
        self.cover_label.setScaledContents(True)
        self.cover_label.setObjectName("coverPlaceholder")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if self.cover_path and os.path.exists(self.cover_path):
            pix = QPixmap(self.cover_path)
            if not pix.isNull():
                self.cover_label.setPixmap(pix)
            else:
                self._show_placeholder()
        else:
            self._show_placeholder()

        # Инфо-плашка — нижняя часть, закруглена снизу
        self.info_bar = QWidget(self)
        self.info_bar.setGeometry(0, _POSTER_H, _CARD_W, _BAR_H)
        self.info_bar.setObjectName("cardInfoBar")

        bar_layout = QVBoxLayout(self.info_bar)
        bar_layout.setContentsMargins(14, 12, 14, 12)
        bar_layout.setSpacing(4)

        self.title_label = QLabel(self.title.upper(), self.info_bar)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setWordWrap(True)
        bar_layout.addWidget(self.title_label)

        self.year_label = QLabel(f"{self.year}", self.info_bar)
        self.year_label.setObjectName("cardYear")
        bar_layout.addWidget(self.year_label)

        bar_layout.addStretch()

    def _show_placeholder(self):
        self.cover_label.setText("🎬\n\nОБЛОЖКА\nНЕДОСТУПНА")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_requested.emit(self.kp_id)
        super().mousePressEvent(event)

    def update_poster(self, cover_path: str):
        if not cover_path or not os.path.exists(cover_path):
            return
        pix = QPixmap(cover_path)
        if pix.isNull():
            return
        self.cover_path = cover_path
        self.cover_label.setText("")
        self.cover_label.setPixmap(pix)