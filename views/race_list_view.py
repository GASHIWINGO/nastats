from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QLabel, QLineEdit, QSizePolicy, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from models.race_table_model import RaceTableModel
import db_sync


class RaceListView(QWidget):
    race_selected = Signal(int)

    def __init__(self, season: int, series: str, parent=None):
        super().__init__(parent)
        self.season = season
        self.series = series
        self._all_races = []

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.label = QLabel(f"Гонки: {series} — {season}")
        self.label.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(self.label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Фильтр по названию гонки...")
        self.search_box.textChanged.connect(self.apply_filter)
        self.layout.addWidget(self.search_box)

        self.table = QTableView()
        self.table.setObjectName("raceTable")  # 👈 для QSS
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.table)

        self.table.doubleClicked.connect(self.on_race_double_clicked)

        self.load_races()

    def load_races(self):
        races, _, _ = db_sync.get_races_for_season(
            season=self.season, series_name=self.series, page=1, page_size=100
        )
        self._all_races = races
        self.apply_filter()

    def apply_filter(self):
        query = self.search_box.text().lower()
        if not query:
            filtered = self._all_races
        else:
            filtered = [
                r for r in self._all_races
                if query in r.race_name.lower()
            ]

        model = RaceTableModel(filtered)
        self.table.setModel(model)

        header = self.table.horizontalHeader()
        self.table.setColumnWidth(0, 40)   # Номер гонки
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(2, 200)  # Трек
        self.table.setColumnWidth(3, 150)   # Длина (миль)
        self.table.setColumnWidth(4, 100)  # Покрытие
        header.setStretchLastSection(False)

        

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)

    def update_data(self, season: int, series: str):
        self.season = season
        self.series = series
        self.label.setText(f"Гонки: {series} — {season}")
        self.load_races()

    def on_race_double_clicked(self, index):
        if not index.isValid():
            return
        race_id = self.table.model()._races[index.row()].race_id
        self.race_selected.emit(race_id)
