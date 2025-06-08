from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView, QSizePolicy, QLineEdit
from PySide6.QtCore import Qt, Signal
import db_sync
from models.team_table_model import TeamTableModel


class TeamListView(QWidget):
    team_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.season = None
        self.series = None
        self._all_teams = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.label = QLabel()
        self.label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Фильтр по названию команды...")
        self.search_box.textChanged.connect(self.apply_filter)
        layout.addWidget(self.search_box)

        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table, stretch=1)

    def _configure_table(self):
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Fixed)

        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.DescendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)

    def update_context(self, season: int, series: str):
        self.season = season
        self.series = series
        self._load_data()

    def _load_data(self):
        teams, _, _ = db_sync.get_team_standings(
            self.season,
            self.series,
            page=1,
            page_size=5000
        )
        self._all_teams = teams
        self.label.setText(f"Команды: {self.series} — {self.season}")
        self.apply_filter()

    def apply_filter(self):
        query = self.search_box.text().lower()
        if not query:
            filtered_teams = self._all_teams
        else:
            filtered_teams = [
                t for t in self._all_teams
                if query in t.team_name.lower()
            ]

        model = TeamTableModel(filtered_teams, self)
        self.table.setModel(model)
        self._configure_table()

    def _on_row_double_clicked(self, index):
        if not index.isValid():
            return
        model: TeamTableModel = self.table.model()
        if not model:
            return
        team_id = model.team_id(index.row())
        self.team_selected.emit(team_id)