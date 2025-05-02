from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView, QSizePolicy
from PySide6.QtCore import Qt, Signal
import db_sync
from models.team_table_model import TeamTableModel


class TeamListView(QWidget):
    team_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.season = None
        self.series = None
        self.teams = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.label = QLabel()
        self.label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.label)

        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table, stretch=1)

        self._configure_header()

    def _configure_header(self):
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Fixed)

        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Команда
        self.table.setColumnWidth(1, 80)   # Очки
        self.table.setColumnWidth(2, 80)   # Победы
        self.table.setColumnWidth(3, 80)   # Топ-5
        self.table.setColumnWidth(4, 80)   # Участий

    def update_context(self, season: int, series: str):
        self.season = season
        self.series = series
        self._load_data()

    def _load_data(self):
        self.teams, _, _ = db_sync.get_team_standings(
            self.season,
            self.series,
            page=1,
            page_size=5000  # ✅ все команды
        )
        self.label.setText(f"Команды: {self.series} — {self.season}")
        model = TeamTableModel(self.teams, self)
        self.table.setModel(model)
        self._configure_header()
        self.table.sortByColumn(1, Qt.DescendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)

    def _on_row_double_clicked(self, index):
        model: TeamTableModel = self.table.model()
        team_id = model.team_id(index.row())
        self.team_selected.emit(team_id)
