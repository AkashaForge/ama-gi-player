from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


class MovieFeedWidget(QWidget):
    """
    Контейнер ленты фильмов. Управляет отображением заголовка,
    прокручиваемой сеткой карточек и генерирует сигналы автоподгрузки страниц.
    """
    # Сигнал срабатывает, когда пользователь долистал ленту почти до самого низа
    next_page_requested = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loading_next = False
        self._rendered_kp_ids = set()  # дедупликация
        self._init_feed_layout()
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_moved)

    # ... остальное без изменений ...
    def _init_feed_layout(self):
        """Собирает внутреннюю структуру ленты."""
        # Главный вертикальный макет самой ленты
        feed_layout = QVBoxLayout(self)
        feed_layout.setContentsMargins(0, 0, 0, 0)
        feed_layout.setSpacing(25) # Отступ от заголовка до сетки

        # 1. ПАФОСНЫЙ БЕЛОЙ ЗАГОЛОВК РАЗДЕЛА (В СТИЛЕ ЛОГОТИПА AMAGI)
        self.title_label = QLabel("ВЕРИФИЦИРОВАННЫЙ КУЛЬТУРНЫЙ ФОНД", self)
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 4px;
        """)
        feed_layout.addWidget(self.title_label)

        # 2. ОБЛАСТЬ ПРОКРУТКИ С КИНЕМАТОГРАФИЧНЫМ СКРОЛЛОМ
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # Полностью скрываем системный скроллбар через QSS
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { width: 0px; background: transparent; }
            QScrollBar:horizontal { height: 0px; background: transparent; }
        """)

        # 3. ВНУТРЕННИЙ КОНТЕЙНЕР ДЛЯ АДАПТИВНОЙ СЕТКИ
        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridContainer")

        # Сетка, куда мы будем укладывать карточки MovieCardWidget
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 5, 0, 0)
        self.grid_layout.setSpacing(30) # Комфортные просторные отступы между постерами

        self.scroll_area.setWidget(self.grid_container)
        feed_layout.addWidget(self.scroll_area)

    def _on_scroll_moved(self, value):
        """
        Проверяет положение ползунка. Генерирует сигнал на подгрузку,
        когда до конца страницы остается меньше 150 пикселей.
        """
        scrollbar = self.scroll_area.verticalScrollBar()
        max_scroll = scrollbar.maximum()

        # Если максимальный скролл доступен и до низа осталось менее 150 пикселей
        if max_scroll > 0 and (max_scroll - value) < 150:
            # Защита от дублирования вызовов: отправляем сигнал только один раз за проход
            if not self._is_loading_next:
                self._is_loading_next = True
                self.next_page_requested.emit()

    def reset_loading_state(self):
        """
        Снимает внутреннюю блокировку. Метод вызывается оркестратором (main.py)
        после того, как новые карточки были физически отрендерены в UI.
        """
        self._is_loading_next = False

    def add_card_to_grid(self, card_widget) -> bool:
        """Добавляет карточку, если её kp_id ещё не показывался. Возвращает True при успехе."""
        kp_id = getattr(card_widget, "kp_id", None)
        if kp_id in self._rendered_kp_ids:
            card_widget.deleteLater()
            return False

        self._rendered_kp_ids.add(kp_id)
        idx = self.grid_layout.count()
        row, col = idx // 4, idx % 4
        self.grid_layout.addWidget(card_widget, row, col)
        return True

    def clear_grid(self):
        self._is_loading_next = False
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rendered_kp_ids.clear()
        self.scroll_area.verticalScrollBar().setValue(0)
