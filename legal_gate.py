"""Модальный дисклеймер с переключением языка.

Показывает 2 вкладки (Terms of Use / Privacy Policy), каждая —
с переключателем языка EN/RU в шапке. При смене языка обе
вкладки обновляются. Пользователь видит все 4 документа
(Disclaimer EN, Disclaimer RU, Privacy EN, Privacy RU),
но интерфейс остаётся 2 вкладки — без визуального мусора.

Кнопка «Accept and continue» активируется через ACCEPT_DELAY_SEC
секунд после открытия — у пользователя есть время прочитать.

Публичный API:
    LegalGateDialog(parent=None, lang=None)
        lang — "en" | "ru" | None (тогда env AMAGI_LEGAL_LANG или "en")
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
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
    SUPPORTED_LANGS,
    get_disclaimer,
    get_privacy,
)

# Сколько секунд кнопка Accept остаётся неактивной после открытия.
ACCEPT_DELAY_SEC = 5


# ---------------------------------------------------------------------------
#  UI-строки на двух языках
# ---------------------------------------------------------------------------
_UI_STRINGS = {
    "en": {
        "window_title": "Terms of Use and Privacy Policy",
        "header_title": "Terms of Use and Privacy Policy",
        "tab_terms": "Terms of Use",
        "tab_privacy": "Privacy Policy",
        "lang_label": "Language:",
        "accept_checkbox": (
            "I accept the Terms of Use and the Privacy Policy"
        ),
        "accept_hint": (
            "I confirm that I have read the Terms of Use and the "
            "Privacy Policy, and I undertake to use the Application "
            "in compliance with the laws of my jurisdiction. I "
            "understand that the Developer is not responsible for "
            "my actions when using the Application."
        ),
        "decline": "Decline",
        "accept": "Accept and continue",
        "countdown": (
            "Please review the document. The 'Accept' button will "
            "become available in {n} sec."
        ),
        "countdown_done": (
            "You may now accept the terms — tick the checkbox below."
        ),
    },
    "ru": {
        "window_title": "Условия использования и Политика конфиденциальности",
        "header_title": "Условия использования и Политика конфиденциальности",
        "tab_terms": "Условия использования",
        "tab_privacy": "Политика конфиденциальности",
        "lang_label": "Язык:",
        "accept_checkbox": (
            "Я принимаю Условия использования и Политику "
            "конфиденциальности"
        ),
        "accept_hint": (
            "Я подтверждаю, что ознакомился с Условиями "
            "использования и Политикой конфиденциальности, и "
            "обязуюсь использовать Приложение в соответствии с "
            "законодательством моей юрисдикции. Я понимаю, что "
            "Разработчик не несёт ответственности за мои действия "
            "при использовании Приложения."
        ),
        "decline": "Отклонить",
        "accept": "Принять и продолжить",
        "countdown": (
            "Пожалуйста, ознакомьтесь с документом. Кнопка "
            "«Принять» станет доступна через {n} сек."
        ),
        "countdown_done": (
            "Теперь вы можете принять условия — поставьте галочку "
            "ниже."
        ),
    },
}


# ---------------------------------------------------------------------------
#  Вкладка с одним документом (TOC + content)
# ---------------------------------------------------------------------------
class _DocumentTab(QWidget):
    """Одна вкладка: список секций слева, текст справа."""

    def __init__(self, document: dict, parent=None):
        """document — результат get_disclaimer() / get_privacy()."""
        super().__init__(parent)
        self._sections = document["sections"]
        self._init_ui()
        self.load_document(document)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        # Слева — оглавление
        self.list = QListWidget()
        self.list.setFixedWidth(300)
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self._on_section_changed)
        splitter.addWidget(self.list)

        # Справа — заголовок секции + текст
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

    def load_document(self, document: dict):
        """Заменяет секции в вкладке (при смене языка)."""
        # Запомнить текущую позицию (чтобы не сбрасывать на первую секцию)
        current_row = self.list.currentRow()
        if current_row < 0:
            current_row = 0

        self.list.blockSignals(True)
        self.list.clear()
        self._sections = document["sections"]
        for section in self._sections:
            item = QListWidgetItem(section["title"])
            item.setData(Qt.ItemDataRole.UserRole, section)
            self.list.addItem(item)
        self.list.blockSignals(False)

        # Восстановить позицию (если секций столько же)
        row = min(current_row, self.list.count() - 1) if self.list.count() else 0
        self.list.setCurrentRow(row)

    def _on_section_changed(self, current, _previous):
        if current is None:
            return
        section = current.data(Qt.ItemDataRole.UserRole)
        if section is None:
            return
        self.section_title.setText(section["title"])
        self.text.setPlainText(section["content"])


# ---------------------------------------------------------------------------
#  Основной диалог
# ---------------------------------------------------------------------------
class LegalGateDialog(QDialog):
    language_changed = pyqtSignal(str)   # "en" | "ru"

    def __init__(self, parent=None, lang: str | None = None):
        super().__init__(parent)

        # Резолвим язык через legal_texts (явный lang → env → "en")
        disclaimer = get_disclaimer(lang)
        privacy = get_privacy(lang)
        self._current_lang = disclaimer.get("lang") or "en"
        self._ui = _UI_STRINGS.get(self._current_lang, _UI_STRINGS["en"])

        self.setWindowTitle(self._ui["window_title"])
        self.setModal(True)
        self.resize(1020, 740)
        self.setMinimumSize(900, 640)

        self._seconds_left = ACCEPT_DELAY_SEC
        self._timer: QTimer | None = None

        self._apply_stylesheet()
        self._build_ui(disclaimer, privacy)
        self._start_countdown()

    # ------------------------------------------------------------------
    #  Стили
    # ------------------------------------------------------------------
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
            QPushButton#langBtn {
                background-color: #1e1e1e;
                color: #aaaaaa;
                font-weight: 700;
                padding: 6px 14px;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#langBtn:checked {
                background-color: #ffffff;
                color: #000000;
                border-color: #ffffff;
            }
            QPushButton#langBtn:hover {
                border-color: #666666;
            }

            QSplitter::handle {
                background-color: #2a2a2a;
            }
        """)

    # ------------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------------
    def _build_ui(self, disclaimer: dict, privacy: dict):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(14)

        # --- Заголовок + переключатель языка ---
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title = QLabel(self._ui["header_title"])
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        header_row.addWidget(title)
        header_row.addStretch()

        lang_label = QLabel(self._ui["lang_label"])
        lang_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 12px;"
        )
        header_row.addWidget(lang_label)

        self.btn_en = QPushButton("EN")
        self.btn_en.setObjectName("langBtn")
        self.btn_en.setCheckable(True)
        self.btn_en.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_en.clicked.connect(lambda: self._set_language("en"))
        header_row.addWidget(self.btn_en)

        self.btn_ru = QPushButton("RU")
        self.btn_ru.setObjectName("langBtn")
        self.btn_ru.setCheckable(True)
        self.btn_ru.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ru.clicked.connect(lambda: self._set_language("ru"))
        header_row.addWidget(self.btn_ru)

        root.addLayout(header_row)

        # --- Вкладки ---
        self.tabs = QTabWidget()
        self.terms_tab = _DocumentTab(disclaimer)
        self.privacy_tab = _DocumentTab(privacy)
        self.tabs.addTab(self.terms_tab, self._ui["tab_terms"])
        self.tabs.addTab(self.privacy_tab, self._ui["tab_privacy"])
        root.addWidget(self.tabs, stretch=1)

        # --- Countdown ---
        self.countdown_label = QLabel("")
        self.countdown_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px;"
        )
        root.addWidget(self.countdown_label)

        # --- Checkbox ---
        self.accept_checkbox = QCheckBox(self._ui["accept_checkbox"])
        self.accept_checkbox.setEnabled(False)
        self.accept_checkbox.stateChanged.connect(self._update_accept_button)
        root.addWidget(self.accept_checkbox)

        # --- Hint ---
        hint = QLabel(self._ui["accept_hint"])
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px; "
            "line-height: 16px; padding-left: 24px;"
        )
        root.addWidget(hint)

        # --- Кнопки ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.decline_btn = QPushButton(self._ui["decline"])
        self.decline_btn.setObjectName("declineBtn")
        self.decline_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.decline_btn)

        self.accept_btn = QPushButton(self._ui["accept"])
        self.accept_btn.setEnabled(False)
        self.accept_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.accept_btn)

        root.addLayout(btn_row)

        # Начальное состояние кнопок языка
        self._update_lang_buttons()

    # ------------------------------------------------------------------
    #  Переключение языка
    # ------------------------------------------------------------------
    def _set_language(self, lang: str):
        if lang == self._current_lang:
            self._update_lang_buttons()
            return
        if lang not in SUPPORTED_LANGS:
            return

        self._current_lang = lang
        self._ui = _UI_STRINGS.get(lang, _UI_STRINGS["en"])

        # Подтягиваем документы на новом языке
        disclaimer = get_disclaimer(lang)
        privacy = get_privacy(lang)

        # Обновляем содержимое вкладок (сохраняя позицию в TOC)
        self.terms_tab.load_document(disclaimer)
        self.privacy_tab.load_document(privacy)

        # Обновляем тексты интерфейса
        self.setWindowTitle(self._ui["window_title"])
        self.tabs.setTabText(0, self._ui["tab_terms"])
        self.tabs.setTabText(1, self._ui["tab_privacy"])
        self.accept_checkbox.setText(self._ui["accept_checkbox"])
        self.decline_btn.setText(self._ui["decline"])
        self.accept_btn.setText(self._ui["accept"])

        # Обновляем countdown (если ещё идёт) или финальный текст
        if self._seconds_left > 0:
            self._update_countdown_label()
        else:
            self.countdown_label.setText(self._ui["countdown_done"])

        # Обновляем hint: пересобираем через поиск QLabel
        for child in self.findChildren(QLabel):
            if "line-height" in child.styleSheet():
                child.setText(self._ui["accept_hint"])
                break

        self._update_lang_buttons()
        self.language_changed.emit(lang)

    def _update_lang_buttons(self):
        self.btn_en.setChecked(self._current_lang == "en")
        self.btn_ru.setChecked(self._current_lang == "ru")

    def current_language(self) -> str:
        """Возвращает текущий выбранный язык диалога."""
        return self._current_lang

    # ------------------------------------------------------------------
    #  Таймер (5 секунд)
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
            if self._timer:
                self._timer.stop()
            self.accept_checkbox.setEnabled(True)
            self.countdown_label.setText(self._ui["countdown_done"])
        else:
            self._update_countdown_label()

    def _update_countdown_label(self):
        self.countdown_label.setText(
            self._ui["countdown"].format(n=self._seconds_left)
        )

    def _update_accept_button(self, _state=None):
        ready = (
            self._seconds_left <= 0
            and self.accept_checkbox.isChecked()
        )
        self.accept_btn.setEnabled(ready)