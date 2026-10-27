"""Лента фильмов.

v2.0.8:
  - защита от бесконечного цикла пагинации: после загрузки карточек
    флаг _is_loading_next не сбрасывается до тех пор, пока QScrollArea
    не пересчитает max_scroll (layout перестраивается асинхронно,
    и старый сброс приводил к valueChanged с новым max при старом
    value → пользователь «в конце» → снова emit → цикл);
  - _end_reached: после has_more=False emit блокируется до нового
    поиска / clear_grid;
  - reset_loading_state() используется только для жёсткого сброса
    (clear_grid / run_search).
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


class MovieFeedWidget(QWidget):
    next_page_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loading_next = False
        self._last_max_scroll = 0
        self._end_reached = False
        self._rendered_kp_ids = set()
        self._init_feed_layout()
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_moved
        )

    def _init_feed_layout(self):
        feed_layout = QVBoxLayout(self)
        feed_layout.setContentsMargins(0, 0, 0, 0)
        feed_layout.setSpacing(25)

        self.title_label = QLabel(
            "ВЕРИФИЦИРОВАННЫЙ КУЛЬТУРНЫЙ ФОНД", self
        )
        self.title_label.setObjectName("sectionTitle")
        feed_layout.addWidget(self.title_label)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { width: 0px; background: transparent; }
            QScrollBar:horizontal { height: 0px; background: transparent; }
        """)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridContainer")

        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 5, 0, 0)
        self.grid_layout.setSpacing(30)

        self.scroll_area.setWidget(self.grid_container)
        feed_layout.addWidget(self.scroll_area)

    def _on_scroll_moved(self, value):
        # Конец ленты — emit запрещён до clear_grid/run_search
        if self._end_reached:
            return

        scrollbar = self.scroll_area.verticalScrollBar()
        max_scroll = scrollbar.maximum()

        if self._is_loading_next:
            # Ждём, пока layout пересчитается (max_scroll вырастет).
            # Только тогда разрешаем новый emit — это ключ к отсутствию
            # цикла (иначе valueChanged от роста max срабатывает с
            # прежним value, и пользователь «остаётся в конце»).
            if max_scroll != self._last_max_scroll:
                self._is_loading_next = False
                self._last_max_scroll = max_scroll
            return

        self._last_max_scroll = max_scroll
        if max_scroll > 0 and (max_scroll - value) < 300:
            self._is_loading_next = True
            self.next_page_requested.emit()

    def reset_loading_state(self):
        """Жёсткий сброс — используется в clear_grid и run_search."""
        self._is_loading_next = False
        self._last_max_scroll = 0

    def mark_end_reached(self):
        """Вызывается контроллером, когда has_more=False.
        Блокирует новые emit до clear_grid / run_search."""
        self._end_reached = True
        self._is_loading_next = False

    def mark_end_not_reached(self):
        """Сбрасывает флаг конца ленты (перед новым поиском)."""
        self._end_reached = False

    def add_card_to_grid(self, card_widget) -> bool:
        kp_id = getattr(card_widget, "kp_id", None)
        if kp_id in self._rendered_kp_ids:
            card_widget.deleteLater()
            return False
        self._rendered_kp_ids.add(kp_id)
        idx = self.grid_layout.count()
        row, col = idx // 4, idx % 4
        self.grid_layout.addWidget(card_widget, row, col)
        # Принудительно пересчитать layout, чтобы QScrollArea быстрее
        # обновила max_scroll (иначе valueChanged придёт с задержкой)
        self.grid_container.adjustSize()
        return True

    def clear_grid(self):
        self._is_loading_next = False
        self._last_max_scroll = 0
        self._end_reached = False
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rendered_kp_ids.clear()
        self.scroll_area.verticalScrollBar().setValue(0)