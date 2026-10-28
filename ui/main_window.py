"""Главное окно Amagi-Player.

v2.0.5 (Gallery Editorial):
  - hover карточек в light-теме: мягкая индиго-тень (QGraphicsDropShadowEffect);
  - resume island анимированно выезжает снизу (fade + slide-up);
  - кнопка темы: терракотовый пульс на клик (анимация color);
  - event-filter ставится на карточки автоматически по QTimer (300 мс);
  - при выходе из light-темы эффекты полностью удаляются.
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
import random

from PyQt6.QtCore import (
    QEvent,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
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
    language_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amagi-Player")
        self._current_resume_id = None
        self._current_lang = getattr(config, "SEARCH_LANGUAGE", "en")

        self._is_light_theme = False
        self._noise_pixmap = None
        self._active_animations = {}
        self._island_effect = None

        self._init_ui_core()
        self._load_stylesheet()
        self.resize(1150, 820)

        self._card_filter_timer = QTimer(self)
        self._card_filter_timer.setInterval(300)
        self._card_filter_timer.timeout.connect(self._sync_card_filters)
        self._card_filter_timer.start()

    def _init_ui_core(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        base_layout = QVBoxLayout(central_widget)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(0)

        # ================= HEADER =================
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

        self.language_btn = QPushButton(self._current_lang.upper(), self.header_bar)
        self.language_btn.setObjectName("languageButton")
        self.language_btn.setFixedSize(48, 32)
        self.language_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language_btn.setToolTip(
            "Язык поиска:\n"
            "EN — только фильмы на английском\n"
            "RU — только на русском (более медленный)"
        )
        self.language_btn.clicked.connect(self._on_language_btn_clicked)
        header_layout.addWidget(self.language_btn)

        base_layout.addWidget(self.header_bar)

        # ================= CONTENT =================
        content_wrapper = QWidget(central_widget)
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(40, 35, 40, 25)
        content_layout.setSpacing(20)

        self.screen_stack = QStackedWidget(content_wrapper)
        self.feed_page = MovieFeedWidget(content_wrapper)
        self.details_page = MovieDetailsWidget(content_wrapper)
        self.player_page = MoviePlayerWidget(content_wrapper)

        self.settings_page_placeholder = QWidget()
        settings_layout = QVBoxLayout(self.settings_page_placeholder)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_back_btn = QPushButton("← НАЗАД В ЛЕНТУ")
        settings_back_btn.setObjectName("sysButton")
        settings_back_btn.clicked.connect(lambda: self.screen_stack.setCurrentIndex(0))
        settings_layout.addWidget(settings_back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        settings_label = QLabel("ЭКРАН НАСТРОЕК (В РАЗРАБОТКЕ)")
        settings_label.setObjectName("settingsPlaceholder")
        settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addStretch()
        settings_layout.addWidget(settings_label)
        settings_layout.addStretch()

        self.screen_stack.addWidget(self.feed_page)
        self.screen_stack.addWidget(self.details_page)
        self.screen_stack.addWidget(self.player_page)
        self.screen_stack.addWidget(self.settings_page_placeholder)
        content_layout.addWidget(self.screen_stack)

        bottom_bar = QWidget(content_wrapper)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()

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

        # ================= RESUME ISLAND =================
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

    # ================= LANGUAGE =================
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

    # ================= RESIZE / PAINT =================
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
                        if random.random() < 0.15:
                            alpha = random.randint(5, 12)
                            noise_painter.setPen(QColor(120, 100, 70, alpha))
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
        self._reposition_resume_island()
        self._animate_resume_island_in()

    def _animate_resume_island_in(self):
        if self._island_effect is None:
            self._island_effect = QGraphicsOpacityEffect(self.resume_island)
            self.resume_island.setGraphicsEffect(self._island_effect)

        self._island_effect.setOpacity(0.0)
        base_y = self.height() - self.resume_island.height() - 95
        base_x = (self.width() - self.resume_island.width()) // 2
        self.resume_island.move(QPoint(base_x, base_y + 12))
        self.resume_island.show()

        group = QParallelAnimationGroup(self)

        anim_op = QPropertyAnimation(self._island_effect, b"opacity")
        anim_op.setDuration(260)
        anim_op.setStartValue(0.0)
        anim_op.setEndValue(1.0)
        anim_op.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(anim_op)

        anim_pos = QPropertyAnimation(self.resume_island, b"pos")
        anim_pos.setDuration(260)
        anim_pos.setStartValue(QPoint(base_x, base_y + 12))
        anim_pos.setEndValue(QPoint(base_x, base_y))
        anim_pos.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(anim_pos)

        group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    # ================= HOVER =================
    def _sync_card_filters(self):
        for widget in self.findChildren(QWidget):
            if widget.__class__.__name__ == "MovieCardWidget":
                if not getattr(widget, "_hover_filter_installed", False):
                    widget.installEventFilter(self)
                    widget._hover_filter_installed = True
                    if self._is_light_theme:
                        self._ensure_card_shadow(widget)

    def _ensure_card_shadow(self, card_widget) -> QGraphicsDropShadowEffect:
        effect = card_widget.graphicsEffect()
        if not isinstance(effect, QGraphicsDropShadowEffect):
            effect = QGraphicsDropShadowEffect(card_widget)
            effect.setBlurRadius(0)
            effect.setOffset(0, 0)
            effect.setColor(QColor(60, 50, 40, 0))
            card_widget.setGraphicsEffect(effect)
        return effect

    def eventFilter(self, obj, event):
        if self._is_light_theme and obj.__class__.__name__ == "MovieCardWidget":
            if event.type() == QEvent.Type.Enter:
                self._animate_card_scale(obj, expand=True)
            elif event.type() == QEvent.Type.Leave:
                self._animate_card_scale(obj, expand=False)
        return super().eventFilter(obj, event)

    def _animate_card_scale(self, card_widget, expand: bool):
        """Hover: тёплая коричневая тень, карточка не тускнеет."""
        effect = self._ensure_card_shadow(card_widget)
        effect.setColor(QColor(60, 50, 40, 75))

        prev = self._active_animations.pop(card_widget, None)
        if prev is not None:
            prev.stop()

        ease = (
            QEasingCurve.Type.OutCubic if expand
            else QEasingCurve.Type.InOutQuad
        )

        group = QParallelAnimationGroup(self)

        anim_blur = QPropertyAnimation(effect, b"blurRadius")
        anim_blur.setDuration(280)
        anim_blur.setEasingCurve(ease)
        anim_blur.setStartValue(float(effect.blurRadius()))
        anim_blur.setEndValue(26.0 if expand else 0.0)
        group.addAnimation(anim_blur)

        anim_offset = QPropertyAnimation(effect, b"offset")
        anim_offset.setDuration(280)
        anim_offset.setEasingCurve(ease)
        anim_offset.setStartValue(effect.offset())
        anim_offset.setEndValue(
            QPointF(0.0, 7.0) if expand else QPointF(0.0, 0.0)
        )
        group.addAnimation(anim_offset)

        self._active_animations[card_widget] = group
        group.start()

    # ================= THEME =================
    def _animate_theme_btn_press(self):
        """Терракотовый пульс на клик кнопки темы."""
        effect = self.theme_btn.graphicsEffect()
        if not isinstance(effect, QGraphicsDropShadowEffect):
            effect = QGraphicsDropShadowEffect(self.theme_btn)
            effect.setOffset(0, 0)
            effect.setBlurRadius(20)
            effect.setColor(QColor(196, 85, 59, 0))
            self.theme_btn.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"color")
        anim.setDuration(400)
        anim.setStartValue(QColor(196, 85, 59, 140))
        anim.setEndValue(QColor(196, 85, 59, 0))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    def _toggle_theme_internal(self):
        self._animate_theme_btn_press()

        self._is_light_theme = not self._is_light_theme
        self._noise_pixmap = None

        if self._is_light_theme:
            self.setProperty("theme", "light")
            self.theme_btn.setText("✦ ТЁМНАЯ ТЕМА")
        else:
            self.setProperty("theme", "dark")
            self.theme_btn.setText("✦ СВЕТЛАЯ ТЕМА")

        self.style().unpolish(self)
        self.style().polish(self)

        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

            if widget.__class__.__name__ == "MovieCardWidget":
                if self._is_light_theme:
                    self._ensure_card_shadow(widget)
                else:
                    prev = self._active_animations.pop(widget, None)
                    if prev is not None:
                        prev.stop()
                    widget.setGraphicsEffect(None)
                    widget._hover_filter_installed = False

        self.update()
        self.theme_toggle_requested.emit()