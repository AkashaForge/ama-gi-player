"""Диалог выбора альтернативного источника."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class SourcePickerDialog(QDialog):
    source_selected = pyqtSignal(dict)

    def __init__(self, alternatives: list[dict], parent=None):
        super().__init__(parent)
        self._alternatives = alternatives
        self.setWindowTitle("Выбор источника")
        self.setMinimumWidth(650)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Доступные альтернативные раздачи:")
        title.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        self.list_widget = QListWidget(self)
        for src in self._alternatives:
            self._add_item(src)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        play_btn = QPushButton("Смотреть", self)
        play_btn.clicked.connect(self._on_play)
        btn_row.addWidget(play_btn)

        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _add_item(self, src: dict):
        title = src.get("title", "Без названия")
        seeders = src.get("seeders", 0) or 0
        size_gb = (src.get("size", 0) or 0) / 1024 ** 3
        src_type = src.get("type", "?")
        quality = self._detect_quality(title)

        text = f"{title}\n   [{src_type}]  Сидов: {seeders}  |  " \
               f"Размер: {size_gb:.2f} GB  |  Качество: {quality}"

        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, src)
        self.list_widget.addItem(item)

    @staticmethod
    def _detect_quality(title: str) -> str:
        low = title.lower()
        if "2160p" in low or "4k" in low:
            return "4K"
        if "1080p" in low:
            return "1080p"
        if "720p" in low:
            return "720p"
        if "480p" in low or "dvdrip" in low:
            return "SD"
        return "?"

    def _on_play(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        src = item.data(Qt.ItemDataRole.UserRole)
        self.source_selected.emit(src)
        self.accept()

    def _on_double_click(self, item):
        src = item.data(Qt.ItemDataRole.UserRole)
        self.source_selected.emit(src)
        self.accept()
