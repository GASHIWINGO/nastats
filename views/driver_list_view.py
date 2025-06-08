from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableView, QSizePolicy, QHeaderView, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from models.driver_table_model import DriverTableModel
import db_sync


class DriverListView(QWidget):
    driver_selected = Signal(int)

    def __init__(self, season: int, series: str, parent=None):
        super().__init__(parent)
        self.season = season
        self.series = series
        self._all_drivers = []

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.label = QLabel(f"Гонщики: {self.series} — {self.season}")
        self.label.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(self.label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Фильтр по имени гонщика...")
        self.search_box.textChanged.connect(self.apply_filter)
        self.layout.addWidget(self.search_box)

        self.table = QTableView()
        self.table.setObjectName("driversTable")
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.table)

        self.table.doubleClicked.connect(self.on_driver_double_clicked)

        self.load_data()

    def load_data(self):
        drivers, _, _ = db_sync.get_driver_standings(
            season=self.season,
            series_name=self.series,
            page=1,
            page_size=5000
        )
        self._all_drivers = drivers
        self.apply_filter()

    def apply_filter(self):
        query = self.search_box.text().lower()
        if not query:
            filtered_drivers = self._all_drivers
        else:
            filtered_drivers = [
                d for d in self._all_drivers
                if query in d.driver_name.lower()
            ]

        model = DriverTableModel(filtered_drivers)
        self.table.setModel(model)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 80)
        header.setStretchLastSection(False)

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.DescendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)

    def update_data(self, season: int, series: str):
        self.season = season
        self.series = series
        self.label.setText(f"Гонщики: {self.series} — {self.season}")
        self.load_data()

    def on_driver_double_clicked(self, index):
        if not index.isValid():
            return
        model = self.table.model()
        if not model:
            return
        driver_id = model.driver_id(index.row())
        self.driver_selected.emit(driver_id)