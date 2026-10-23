"""Модальное окно дисклеймера с навигацией по разделам.

Показывается ДО инициализации сети. Две вкладки — Условия
использования и Политика конфиденциальности. В каждой вкладке:
оглавление слева, содержимое раздела справа.

Кнопка «Принять» становится доступной через ACCEPT_DELAY_SEC секунд
после открытия окна — это даёт Пользователю время на ознакомление,
но не заставляет прокликивать каждый раздел вручную.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from legal_texts import (
    DISCLAIMER_SECTIONS,
    DISCLAIMER_TITLE,
    PRIVACY_SECTIONS,
    PRIVACY_TITLE,
)

# Сколько секунд кнопка «Принять» недоступна после открытия окна.
ACCEPT_DELAY_SEC = 5


class _DocumentTab(QWidget):
    """Вкладка с одним документом: список разделов + содержимое."""

    def __init__(self, sections, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        # Левая панель — оглавление
        self.list = QListWidget()
        self.list.setFixedWidth(300)
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self._on_section_changed)
        for section in sections:
            item = QListWidgetItem(section["title"])
            item.setData(Qt.ItemDataRole.UserRole, section)
            self.list.addItem(item)
        splitter.addWidget(self.list)

        # Правая панель — заголовок + содержимое
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 12, 16, 12)
        right_layout.setSpacing(8)

        self.section_title = QLabel("")
        self.section_title.setWordWrap(True)
        self.section_title.setStyleSheet(
            "color: #ffffff; font-size: 15px; font-weight: 700; "
            "padding-bottom: 4px; border-bottom: 1px solid #2a2a2a;"
        )
        right_layout.addWidget(self.section_title)

        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setStyleSheet(
            "QTextBrowser {"
            "  background-color: #151515;"
            "  color: #cccccc;"
            "  border: none;"
            "  padding: 4px;"
            "  font-size: 12px;"
            "}"
        )
        right_layout.addWidget(self.text, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Открываем первый раздел
        if sections:
            self.list.setCurrentRow(0)

    def _on_section_changed(self, current, _previous):
        if current is None:
            return
        section = current.data(Qt.ItemDataRole.UserRole)
        if section is None:
            return
        self.section_title.setText(section["title"])
        self.text.setPlainText(section["content"])


class LegalGateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(DISCLAIMER_TITLE)
        self.setModal(True)
        self.resize(1020, 740)
        self.setMinimumSize(900, 640)

        self._seconds_left = ACCEPT_DELAY_SEC
        self._timer = None

        self._apply_stylesheet()
        self._build_ui()
        self._start_countdown()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog { background-color: #0d0d0d; color: #eeeeee; }
            QLabel  { color: #eeeeee; background-color: transparent; }
            QCheckBox { color: #ffffff; font-size: 13px; font-weight: 600; }
            QCheckBox:disabled { color: #666666; }

            QTabWidget::pane {
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                top: -1px;
                background-color: #151515;
            }
            QTabBar::tab {
                background-color: #141414;
                color: #888888;
                padding: 10px 20px;
                border: 1px solid #2a2a2a;
                border-bottom: none;
                margin-right: 2px;
                font-size: 12px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #1a1a1a;
                color: #cccccc;
            }

            QListWidget {
                background-color: #141414;
                color: #dddddd;
                border: none;
                border-right: 1px solid #2a2a2a;
                padding: 8px 4px;
                outline: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 7px 10px;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: #1e1e1e;
            }
            QListWidget::item:selected {
                background-color: #2a2a2a;
                color: #ffffff;
            }

            QPushButton {
                background-color: #ffffff;
                color: #000000;
                font-weight: 800;
                padding: 10px 24px;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
            QPushButton#declineBtn {
                background-color: #1e1e1e;
                color: #aaaaaa;
                font-weight: 600;
                padding: 10px 20px;
            }
            QPushButton#declineBtn:hover {
                background-color: #2a2a2a;
                color: #dddddd;
            }

            QSplitter::handle {
                background-color: #2a2a2a;
            }
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(14)

        title = QLabel(DISCLAIMER_TITLE)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.disclaimer_tab = _DocumentTab(DISCLAIMER_SECTIONS)
        self.privacy_tab = _DocumentTab(PRIVACY_SECTIONS)
        self.tabs.addTab(self.disclaimer_tab, "Условия использования")
        self.tabs.addTab(self.privacy_tab, PRIVACY_TITLE)
        root.addWidget(self.tabs, stretch=1)

        self.countdown_label = QLabel("")
        self.countdown_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px;"
        )
        root.addWidget(self.countdown_label)

        self.accept_checkbox = QCheckBox(
            "Я принимаю Условия использования и Политику конфиденциальности"
        )
        self.accept_checkbox.setEnabled(False)
        self.accept_checkbox.stateChanged.connect(self._update_accept_button)
        root.addWidget(self.accept_checkbox)

        hint = QLabel(
            "Я подтверждаю, что ознакомился с Условиями использования "
            "и Политикой конфиденциальности, и обязуюсь использовать "
            "Приложение в соответствии с законодательством моей "
            "юрисдикции. Я понимаю, что Разработчик не несёт "
            "ответственности за мои действия при использовании "
            "Приложения."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px; "
            "line-height: 16px; padding-left: 24px;"
        )
        root.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.decline_btn = QPushButton("Отклонить")
        self.decline_btn.setObjectName("declineBtn")
        self.decline_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.decline_btn)

        self.accept_btn = QPushButton("Принять и продолжить")
        self.accept_btn.setEnabled(False)
        self.accept_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.accept_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Таймер на 5 секунд
    # ------------------------------------------------------------------

    def _start_countdown(self):
        self._seconds_left = ACCEPT_DELAY_SEC
        self._update_countdown_label()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._seconds_left -= 1
        if self._seconds_left <= 0:
            self._timer.stop()
            self.accept_checkbox.setEnabled(True)
            self.countdown_label.setText(
                "Можете принять условия — отметьте галочку ниже."
            )
        else:
            self._update_countdown_label()

    def _update_countdown_label(self):
        self.countdown_label.setText(
            f"Ознакомьтесь с документом. Кнопка «Принять» станет "
            f"доступна через {self._seconds_left} сек."
        )

    def _update_accept_button(self, _state=None):
        ready = (
            self._seconds_left <= 0
            and self.accept_checkbox.isChecked()
        )
        self.accept_btn.setEnabled(ready)
