from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal

class TopBar(QWidget):
    season_changed = Signal(int)
    series_changed = Signal(str)

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

        self.season_combo.currentTextChanged.connect(
        lambda val: self.season_changed.emit(int(val))
        )

        self.series_combo.currentTextChanged.connect(
            lambda val: self.series_changed.emit(val)
        )

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        self.season_label = QLabel("Сезон:")
        self.season_combo = QComboBox()
        self.season_combo.addItems([str(y) for y in range(2025, 1948, -1)])  # 2025..1949

        self.series_label = QLabel("Серия:")
        self.series_combo = QComboBox()
        self.series_combo.addItems(["Cup", "Xfinity", "Truck"])

        self.theme_button = QPushButton("🌓 Тема")
        self.theme_button.clicked.connect(self.theme_manager.toggle_theme)

        layout.addWidget(self.season_label)
        layout.addWidget(self.season_combo)
        layout.addWidget(self.series_label)
        layout.addWidget(self.series_combo)
        layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addWidget(self.theme_button)
