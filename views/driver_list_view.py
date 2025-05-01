from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableView, QSizePolicy, QHeaderView
)
from PySide6.QtCore import Qt
from models.driver_table_model import DriverTableModel
import db_sync
from PySide6.QtCore import Qt, Signal


class DriverListView(QWidget):
    driver_selected = Signal(int)

    def __init__(self, season: int, series: str, parent=None):
        super().__init__(parent)
        self.season = season
        self.series = series

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.label = QLabel(f"Гонщики: {series} — {season}")
        self.label.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(self.label)

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
            page_size=5000  # ⚠️ большое значение для загрузки всех
        )
        model = DriverTableModel(drivers)
        self.table.setModel(model)

        header = self.table.horizontalHeader()
        self.table.setColumnWidth(0, 70)   # Позиция
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(2, 80)   # Очки
        self.table.setColumnWidth(3, 80)   # Победы
        self.table.setColumnWidth(4, 70)   # Гонок
        header.setStretchLastSection(False)

        

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.DescendingOrder)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)

    def update_data(self, season: int, series: str):
        self.season = season
        self.series = series
        self.label.setText(f"Гонщики: {series} — {season}")
        self.load_data()

    def on_driver_double_clicked(self, index):
        if not index.isValid():
            return
        model = self.table.model()
        driver_id = model.driver_id(index.row())
        self.driver_selected.emit(driver_id)

