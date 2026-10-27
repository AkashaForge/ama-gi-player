import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


_MAX_DESC_DISPLAY_CHARS = 450


def _truncate_for_display(text: str, max_chars: int = _MAX_DESC_DISPLAY_CHARS) -> str:
    """Режет по границе слова и ставит троеточие."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


class MovieDetailsWidget(QWidget):
    start_streaming_requested = pyqtSignal(int)
    back_to_feed_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_kp_id = None
        self._last_metadata = {}
        self._init_details_layout()

    def _init_details_layout(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(30)

        nav_layout = QHBoxLayout()
        self.back_btn = QPushButton("← НАЗАД К ФОНДУ", self)
        self.back_btn.setObjectName("sysButton")
        self.back_btn.clicked.connect(self.back_to_feed_requested.emit)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        main_layout.addLayout(nav_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(50)

        self.big_cover = QLabel(self)
        self.big_cover.setFixedSize(300, 450)
        self.big_cover.setScaledContents(True)
        self.big_cover.setObjectName("coverPlaceholder")
        self.big_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_cover.setText("ЗАГРУЗКА...")
        # ФИКС 1: AlignTop — постер прижат к верху, не центрируется
        content_layout.addWidget(
            self.big_cover, alignment=Qt.AlignmentFlag.AlignTop
        )

        text_layout = QVBoxLayout()
        text_layout.setSpacing(15)

        self.title_label = QLabel("НАЗВАНИЕ ФИЛЬМА", self)
        self.title_label.setStyleSheet(
            "color: #FFFFFF; font-size: 28px; font-weight: 900; letter-spacing: 2px;"
        )
        self.title_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)

        self.year_label = QLabel("---- ГОД", self)
        self.year_label.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 14px; font-weight: 700; letter-spacing: 1px;"
        )
        text_layout.addWidget(self.year_label)

        self.desc_label = QLabel("Загрузка описания...", self)
        self.desc_label.setStyleSheet(
            "color: rgba(255,255,255,0.8); font-size: 15px; line-height: 24px;"
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        # ФИКС 2: ограничение высоты — описание не вылезает за постер
        self.desc_label.setMaximumHeight(220)
        text_layout.addWidget(self.desc_label)

        text_layout.addSpacing(20)

        self.play_btn = QPushButton("ЗАПУСТИТЬ ТРАНСЛЯЦИЮ", self)
        self.play_btn.setObjectName("actionButton")
        self.play_btn.setFixedHeight(46)
        self.play_btn.setFixedWidth(280)
        self.play_btn.clicked.connect(self._on_play_clicked)
        text_layout.addWidget(self.play_btn)

        text_layout.addStretch()
        content_layout.addLayout(text_layout)
        main_layout.addLayout(content_layout)

    def set_movie_id(self, kp_id: int):
        self._current_kp_id = kp_id

    def update_movie_details(self, metadata: dict):
        self._last_metadata = dict(metadata or {})
        kp_id = metadata.get("kp_id")
        if kp_id is not None:
            self._current_kp_id = kp_id

        print(
            f"[DETAILS] update: kp_id={self._current_kp_id}, "
            f"title='{metadata.get('title')}'"
        )

        self.title_label.setText(str(metadata.get("title", "Без названия")).upper())
        self.year_label.setText(f"{metadata.get('year', '----')} ГОД")

        desc = (metadata.get("description") or "").strip()
        if desc:
            self.update_description(desc)
        else:
            self.desc_label.setText("Загрузка описания...")

        cover_path = metadata.get("cover_path", "") or ""
        if cover_path and os.path.exists(cover_path):
            self.update_cover(cover_path)
        else:
            self.big_cover.clear()
            self.big_cover.setText("ЗАГРУЗКА ОБЛОЖКИ...")

    def update_cover(self, cover_path: str | None):
        if not cover_path or not os.path.exists(cover_path):
            self.big_cover.clear()
            self.big_cover.setText("ОБЛОЖКА\nНЕДОСТУПНА")
            return

        pixmap = QPixmap(cover_path)
        if pixmap.isNull():
            self.big_cover.clear()
            self.big_cover.setText("ОБЛОЖКА\nНЕДОСТУПНА")
            return

        self.big_cover.setText("")
        self.big_cover.setPixmap(pixmap)
        print(f"[DETAILS] Постер {pixmap.width()}x{pixmap.height()} ← {cover_path}")

    def update_description(self, text: str | None):
        clean = (text or "").strip()
        if not clean:
            title = self._last_metadata.get("title", "Этот фильм")
            year = self._last_metadata.get("year", "")
            fallback = str(title)
            if year and str(year) != "----":
                fallback += f" ({year})"
            fallback += ". Источник — открытый архив Internet Archive."
            self.desc_label.setText(fallback)
            return

        # Обрезка троеточием — описание не вылезает за постер
        clean = _truncate_for_display(clean)

        letters = [c for c in clean if c.isalpha()]
        if letters:
            cyrillic = sum(1 for c in letters if "\u0400" <= c <= "\u04FF")
            is_russian = (cyrillic / len(letters)) > 0.30
        else:
            is_russian = True

        if is_russian:
            self.desc_label.setText(clean)
        else:
            self.desc_label.setText(
                f"<i style='color: rgba(255,255,255,0.45); "
                f"font-size: 12px; letter-spacing: 1px;'>(English)</i>"
                f"<br>{clean}"
            )

    def _on_play_clicked(self):
        kp_id = self._current_kp_id or self._last_metadata.get("kp_id")
        print(f"[DETAILS] 🖱️ _on_play_clicked: kp_id={kp_id}")
        if kp_id is not None:
            self.start_streaming_requested.emit(kp_id)
        else:
            print("[DETAILS] ❌ Нет kp_id")