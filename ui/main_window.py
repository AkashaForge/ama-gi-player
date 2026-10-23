"""Главное окно Amagi-Player."""

import os
import random

from PyQt6.QtCore import QEvent, QPoint, QPropertyAnimation, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import config
from ui.widgets.details_widget import MovieDetailsWidget
from ui.widgets.feed_widget import MovieFeedWidget
from ui.widgets.player_widget import MoviePlayerWidget


class MainWindow(QMainWindow):
    theme_toggle_requested = pyqtSignal()
    settings_opened = pyqtSignal()
    resume_movie_requested = pyqtSignal(int)
    resume_dismiss_requested = pyqtSignal(int)
    language_changed = pyqtSignal(str)  # "en" | "ru"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amagi-Player")
        self._current_resume_id = None
        self._current_lang = getattr(config, "SEARCH_LANGUAGE", "en")

        # Состояние темы
        self._is_light_theme = False
        self._noise_pixmap = None  # Кэш
        self._active_animations = {}  # Кэш

        self._init_ui_core()
        self._load_stylesheet()
        self.resize(1150, 820)

    def _init_ui_core(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        base_layout = QVBoxLayout(central_widget)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(0)

        # ==================================================================
        # 1. ВЕРХНЯЯ ШАПКА
        # ==================================================================
        self.header_bar = QWidget(central_widget)
        self.header_bar.setObjectName("headerBar")
        self.header_bar.setFixedHeight(75)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(40, 0, 40, 0)

        logo_label = QLabel("AMAGI", self.header_bar)
        logo_label.setObjectName("logoLabel")
        header_layout.addWidget(logo_label)
        header_layout.addSpacing(60)

        self.search_bar = QLineEdit(self.header_bar)
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("ПОИСК ПО КУЛЬТУРНОМУ ФОНДУ...")
        self.search_bar.setFixedWidth(400)
        header_layout.addWidget(self.search_bar)

        header_layout.addStretch()

        # --- Кнопка переключения языка поиска ---
        self.language_btn = QPushButton(self._current_lang.upper(), self.header_bar)
        self.language_btn.setObjectName("languageButton")
        self.language_btn.setFixedSize(48, 32)
        self.language_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language_btn.setToolTip(
            "Язык поиска:\n"
            "EN — только фильмы на английском\n"
            "RU — только на русском (более медленный)"
        )
        self.language_btn.setStyleSheet("""
            QPushButton#languageButton {
                background-color: transparent;
                color: rgba(255,255,255,0.75);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 2px;
                padding: 0px;
            }
            QPushButton#languageButton:hover {
                color: #ffffff;
                border-color: rgba(255,255,255,0.5);
            }
            QPushButton#languageButton:pressed {
                background-color: rgba(255,255,255,0.05);
            }
        """)
        self.language_btn.clicked.connect(self._on_language_btn_clicked)
        header_layout.addWidget(self.language_btn)

        base_layout.addWidget(self.header_bar)

        # ==================================================================
        # 2. РАБОЧАЯ ЗОНА
        # ==================================================================
        content_wrapper = QWidget(central_widget)
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(40, 35, 40, 25)
        content_layout.setSpacing(20)

        self.screen_stack = QStackedWidget(content_wrapper)
        self.feed_page = MovieFeedWidget(content_wrapper)
        self.details_page = MovieDetailsWidget(content_wrapper)
        self.player_page = MoviePlayerWidget(content_wrapper)

        # Заглушка настроек
        self.settings_page_placeholder = QWidget()
        settings_layout = QVBoxLayout(self.settings_page_placeholder)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_back_btn = QPushButton("← НАЗАД В ЛЕНТУ")
        settings_back_btn.setObjectName("sysButton")
        settings_back_btn.clicked.connect(lambda: self.screen_stack.setCurrentIndex(0))
        settings_layout.addWidget(settings_back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        settings_label = QLabel("ЭКРАН НАСТРОЕК (В РАЗРАБОТКЕ)")
        settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_label.setStyleSheet(
            "color: rgba(255,255,255,0.4); font-size: 14px; letter-spacing: 3px;"
        )
        settings_layout.addStretch()
        settings_layout.addWidget(settings_label)
        settings_layout.addStretch()

        self.screen_stack.addWidget(self.feed_page)                 # 0
        self.screen_stack.addWidget(self.details_page)              # 1
        self.screen_stack.addWidget(self.player_page)               # 2
        self.screen_stack.addWidget(self.settings_page_placeholder) # 3
        content_layout.addWidget(self.screen_stack)
        # Нижняя панель
        bottom_bar = QWidget(content_wrapper)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()

        # Кнопка смены темы
        self.theme_btn = QPushButton("✦ СВЕТЛАЯ ТЕМА", bottom_bar)
        self.theme_btn.setObjectName("sysButton")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme_internal)
        bottom_layout.addWidget(self.theme_btn)

        self.settings_btn = QPushButton("Настройки", bottom_bar)
        self.settings_btn.setObjectName("sysButton")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        bottom_layout.addWidget(self.settings_btn)

        content_layout.addWidget(bottom_bar)
        base_layout.addWidget(content_wrapper)

        # ==================================================================
        # 3. ПАРЯЩИЙ ОСТРОВ ИСТОРИИ
        # ==================================================================
        self.resume_island = QFrame(central_widget)
        self.resume_island.setObjectName("continueIsland")
        self.resume_island.setFixedSize(420, 96)

        island_layout = QVBoxLayout(self.resume_island)
        island_layout.setContentsMargins(20, 15, 20, 15)
        island_layout.setSpacing(10)

        self.resume_label = QLabel("НАЗВАНИЕ ФИЛЬМА...", self.resume_island)
        self.resume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resume_label.setWordWrap(True)
        island_layout.addWidget(self.resume_label)

        self.resume_action_btn = QPushButton("Продолжить просмотр", self.resume_island)
        self.resume_action_btn.setObjectName("islandActionButton")

        self.resume_action_btn.clicked.connect(self._on_resume_action_triggered)
        island_layout.addWidget(self.resume_action_btn)

        self.resume_close_btn = QPushButton("×", self.resume_island)
        self.resume_close_btn.setObjectName("closeIslandButton")
        self.resume_close_btn.setFixedSize(20, 20)
        self.resume_close_btn.move(395, 5)
        self.resume_close_btn.clicked.connect(self._on_resume_close_clicked)

        self.resume_island.hide()

    # ==================================================================
    #  ЯЗЫК ПОИСКА
    # ==================================================================
    def _on_language_btn_clicked(self):
        new_lang = "ru" if self._current_lang == "en" else "en"
        self._current_lang = new_lang
        self.language_btn.setText(new_lang.upper())
        print(f"[LANG] Переключено на: {new_lang.upper()}")
        self.language_changed.emit(new_lang)

    def set_language(self, lang: str):
        self.language_btn.setText((lang or "en").upper())

    def get_language(self) -> str:
        return self._current_lang

    # ==================================================================
    #  RESIZE / PAINT
    # ==================================================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "resume_island") and self.resume_island.isVisible():
            self._reposition_resume_island()
        self._noise_pixmap = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._is_light_theme and hasattr(self, "header_bar"):
            painter = QPainter(self)
            header_rect = self.header_bar.geometry()

            if self._noise_pixmap is None:
                self._noise_pixmap = QPixmap(header_rect.width(), header_rect.height())
                self._noise_pixmap.fill(QColor(0, 0, 0, 0))

                noise_painter = QPainter(self._noise_pixmap)
                for x in range(header_rect.width()):
                    for y in range(header_rect.height()):
                        if random.random() < 0.15:  # Усиленный хай-тек шум
                            alpha = random.randint(5, 12)
                            noise_painter.setPen(QColor(255, 255, 255, alpha))
                            noise_painter.drawPoint(x, y)
                noise_painter.end()

            painter.drawPixmap(header_rect.topLeft(), self._noise_pixmap)
            painter.end()

    def _reposition_resume_island(self):
        x = (self.width() - self.resume_island.width()) // 2
        y = self.height() - self.resume_island.height() - 95
        self.resume_island.move(QPoint(x, y))

    def _load_stylesheet(self):
        qss_path = os.path.join(config.BASE_DIR, "ui", "styles.qss")
        if os.path.exists(qss_path):
            with open(qss_path, encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _on_settings_clicked(self):
        self.screen_stack.setCurrentIndex(3)
        self.settings_opened.emit()

    def _on_resume_action_triggered(self):
        if self._current_resume_id is not None:
            self.resume_movie_requested.emit(self._current_resume_id)

    def _on_resume_close_clicked(self):
        if self._current_resume_id is not None:
            self.resume_dismiss_requested.emit(self._current_resume_id)
        self.resume_island.hide()

    def show_resume_bar(self, movie_id: int, movie_title: str):
        self._current_resume_id = movie_id
        self.resume_label.setText(f"<b>{movie_title.upper()}</b>")
        self.resume_island.show()
        self._reposition_resume_island()

    # ==================================================================
    #  ДИНАМИЧЕСКИЙ ОБРАБОТЧИК ТЕМЫ И ФИЗИЧЕСКИХ АНИМАЦИЙ SCALE
    # ==================================================================
    def eventFilter(self, obj, event):
        """Плавная физическая анимация масштабирования (Scale) при наведении."""
        if self._is_light_theme and obj.inherits("QWidget") and obj.objectName() == "":
            if obj.__class__.__name__ == "MovieCardWidget":
                if event.type() == QEvent.Type.Enter:
                    self._animate_card_scale(obj, expand=True)
                elif event.type() == QEvent.Type.Leave:
                    self._animate_card_scale(obj, expand=False)
        return super().eventFilter(obj, event)

    def _animate_card_scale(self, card_widget, expand: bool):
        """Плавно изменяет геометрию карточки, создавая яблочный эффект левитации."""
        # Сохраняем исходную геометрию, если она ещё не была зафиксирована
        if not hasattr(card_widget, "_original_geometry"):
            card_widget._original_geometry = card_widget.geometry()

        if card_widget in self._active_animations:
            self._active_animations[card_widget].stop()

        orig = card_widget._original_geometry
        # Рассчитываем целевую увеличенную рамку (+8 пикселей во все стороны)
        target_rect = QRect(orig.x() - 4, orig.y() - 4, orig.width() + 8, orig.height() + 8)

        anim = QPropertyAnimation(card_widget, b"geometry", self)
        anim.setDuration(150)  # Быстрый премиальный отклик интерфейса

        if expand:
            anim.setStartValue(card_widget.geometry())
            anim.setEndValue(target_rect)
        else:
            anim.setStartValue(card_widget.geometry())
            anim.setEndValue(orig)

        self._active_animations[card_widget] = anim
        anim.start()

    def _toggle_theme_internal(self):
        """Переключает тему UI между OLED-dark и хай-тек Space Gray."""
        self._is_light_theme = not self._is_light_theme
        self._noise_pixmap = None

        if self._is_light_theme:
            self.setProperty("theme", "light")
            self.theme_btn.setText("✦ ТЕМНАЯ ТЕМА")
        else:
            self.setProperty("theme", "dark")
            self.theme_btn.setText("✦ СВЕТЛАЯ ТЕМА")

        self.style().unpolish(self)
        self.style().polish(self)

        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

            # Подключаем нативный событийный фильтр для анимации карточек
            if widget.__class__.__name__ == "MovieCardWidget":
                if self._is_light_theme:
                    widget.installEventFilter(self)
                else:
                    widget.removeEventFilter(self)
                    # Если возвращаемся в темную тему, сбрасываем размеры в дефолт
                    if hasattr(widget, "_original_geometry"):
                        widget.setGeometry(widget._original_geometry)

            if widget.objectName() == "coverPlaceholder" and not widget.__class__.__name__ == "MovieCardWidget":
                if self._is_light_theme:
                    widget.setStyleSheet("background-color: rgba(0, 0, 0, 0.4); border-radius: 24px;")
                else:
                    widget.setStyleSheet("background-color: rgba(0, 0, 0, 0.2); border-radius: 18px;")

        self.update()
        self.theme_toggle_requested.emit()
