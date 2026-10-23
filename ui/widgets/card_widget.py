"""Карточка фильма."""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


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
        self.setFixedSize(220, 360)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(210, 300)
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
        layout.addWidget(self.cover_label)

        self.title_label = QLabel(self.title.upper(), self)
        self.title_label.setStyleSheet(
            "color: #FFFFFF; font-size: 12px; "
            "font-weight: 800; letter-spacing: 1px;"
        )
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(32)
        layout.addWidget(self.title_label)

        self.year_label = QLabel(f"{self.year} ГОД", self)
        self.year_label.setStyleSheet(
            "color: rgba(255,255,255,0.4); "
            "font-size: 10px; font-weight: 700;"
        )
        layout.addWidget(self.year_label)

        layout.addStretch()

    def _show_placeholder(self):
        self.cover_label.setText(
            "🎬\n\nОБЛОЖКА\nНЕДОСТУПНА"
        )
        self.cover_label.setStyleSheet("""
            background-color: #111111;
            color: rgba(255,255,255,0.5);
            font-weight: 700; font-size: 13px;
            border: 1px solid rgba(255,255,255,0.05);
        """)

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
        self.cover_label.setStyleSheet("")
        self.cover_label.setPixmap(pix)
