from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

import config
from services.torrent_service import TorrentManager


class P2PInitialSetupWizard(QWidget):
    """Штатное окно первоначальной настройки трекеров Jackett при старте"""
    def __init__(self, async_loop, on_success_callback):
        super().__init__()
        self.loop = async_loop
        self.on_success_callback = on_success_callback

        self.setWindowTitle("Amagi-Player — Настройка P2P сетей")
        self.resize(1050, 750)
        self.setStyleSheet("background-color: #000000; color: #FFFFFF;")

        self.manager = TorrentManager()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        self.status_label = QLabel("Развертывание изолированных фоновых P2P-модулей... Ожидайте.")
        self.status_label.setStyleSheet("font-size: 13px; color: #00FF00; font-weight: bold;")
        self.layout.addWidget(self.status_label)

        self.browser = QWebEngineView()
        self.layout.addWidget(self.browser)
        self.browser.hide()

        self.btn_confirm = QPushButton("Я АКТИВИРОВАЛ ВСЕ НЕОБХОДИМЫЕ ТРЕКЕРЫ, ЗАПУСТИТЬ ПЛЕЕР")
        self.btn_confirm.setStyleSheet("""
            QPushButton { padding: 12px; font-weight: 800; background-color: #ffffff; color: #000000; border: none; }
            QPushButton:disabled { background-color: #222222; color: #555555; }
        """)
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.clicked.connect(self._on_setup_confirmed)
        self.layout.addWidget(self.btn_confirm)

        self.loop.create_task(self._boot_backend_services())

    async def _boot_backend_services(self):
        try:
            success = await self.manager.start_services_async()
            if success:
                self.status_label.setText("СЕТЬ ГОТОВА: Нажмите '+ Add Indexer', активируйте трекеры и подтвердите выбор.")
                self.browser.setUrl(QUrl(f"http://127.0.0.1:{config.JACKETT_PORT}"))
                self.browser.show()
                self.btn_confirm.setEnabled(True)
            else:
                self.status_label.setText("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось запустить P2P модули.")
        except Exception as e:
            self.status_label.setText(f"❌ АВАРИЙНЫЙ СБОЙ БЭКЕНДА: {e}")

    def _on_setup_confirmed(self):
        self.hide()
        self.on_success_callback(self.manager)

    def closeEvent(self, event):
        self.manager.stop_services()
        event.accept()
