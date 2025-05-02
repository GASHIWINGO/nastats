from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView, QSizePolicy
from PySide6.QtCore import Qt, Signal
from models.manufacturer_table_model import ManufacturerTableModel
import db_sync


class ManufacturerListView(QWidget):
    manufacturer_selected = Signal(int)

    def __init__(self, season: int, series: str, parent=None):
        super().__init__(parent)
        self.season = season
        self.series = series

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.label = QLabel(f"Производители: {series} — {season}")
        self.label.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(self.label)

        self.table = QTableView()
        self.table.setObjectName("manufacturersTable")
        self.table.setSortingEnabled(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.table, stretch=1)

        self.table.doubleClicked.connect(self._on_row_double_clicked)

        self.load_data()

    def load_data(self):
        manufacturers = db_sync.get_manufacturer_season_stats(
            season=self.season,
            series_name=self.series
        )
        model = ManufacturerTableModel(manufacturers)
        self.table.setModel(model)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Fixed)

        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Производитель
        self.table.setColumnWidth(1, 80)  # Победы
        self.table.setColumnWidth(2, 80)  # Топ-5
        self.table.setColumnWidth(3, 80)  # Топ-10
        self.table.setColumnWidth(4, 80)  # Участий

        self.table.sortByColumn(1, Qt.DescendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)

    def update_context(self, season: int, series: str):
        self.season = season
        self.series = series
        self.label.setText(f"Производители: {series} — {season}")
        self.load_data()

    def _on_row_double_clicked(self, index):
        row = index.row()
        manufacturer_id = self.table.model()._manufacturers[row].manufacturer_id
        self.manufacturer_selected.emit(manufacturer_id)
