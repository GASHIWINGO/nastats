from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QSizePolicy, QHeaderView
from PySide6.QtCore import Qt
from models.race_results_model import RaceResultsModel
import db_sync


class RaceDetailsView(QWidget):
    def __init__(self, race_id: int, parent=None):
        super().__init__(parent)
        self.race_id = race_id

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.title_label = QLabel("Гонка")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.layout.addWidget(self.title_label)

        self.results_table = QTableView()
        self.results_table.setObjectName("resultsTable")
        self.results_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.results_table.setSizeAdjustPolicy(QTableView.AdjustToContents)
        self.layout.addWidget(self.results_table)

        self.load_data()

    def load_data(self):
        details, results = db_sync.get_race_details_and_results(self.race_id)
        if not details:
            self.title_label.setText("Ошибка загрузки гонки.")
            return

        self.title_label.setText(
            f"{details.race_name} ({details.series_name} {details.season}) — {details.track_name}"
        )

        model = RaceResultsModel(results)
        self.results_table.setModel(model)

        header = self.results_table.horizontalHeader()
        self.results_table.setColumnWidth(0, 60)   # Поз.
        self.results_table.setColumnWidth(1, 80)   # Старт
        self.results_table.setColumnWidth(2, 50)   # №
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.results_table.setColumnWidth(5, 100)  # Производитель
        self.results_table.setColumnWidth(6, 70)   # Круги
        self.results_table.setColumnWidth(7, 50)   # Вёл
        self.results_table.setColumnWidth(8, 100)  # Статус
        header.setStretchLastSection(False)

        


        self.results_table.setSortingEnabled(True)
        self.results_table.sortByColumn(0, Qt.AscendingOrder)

        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableView.SelectRows)
