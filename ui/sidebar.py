from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import Signal


class Sidebar(QWidget):
    navigation_requested = Signal(str)  # Сигнал для переключения экрана

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.buttons = {}

        pages = {
            "races": "🏁 Гонки",
            "drivers": "👨‍✈️ Гонщики",
            "teams": "🚗 Команды",
            "compare": "⚔️ Сравнение",
            "manufacturers": "🏭 Производители"
        }

        for page_key, label in pages.items():
            button = QPushButton(label)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda checked, key=page_key: self._on_button_clicked(key))
            layout.addWidget(button)
            self.buttons[page_key] = button

        layout.addStretch()

    def _on_button_clicked(self, page_key):
        self.navigation_requested.emit(page_key)
