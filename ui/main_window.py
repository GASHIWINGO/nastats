import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt

from ui.topbar import TopBar
from ui.sidebar import Sidebar
from views.race_list_view import RaceListView
from views.driver_list_view import DriverListView
from views.race_details_view import RaceDetailsView
from views.driver_details_view import DriverDetailsView


class MainWindow(QMainWindow):
    def __init__(self, theme_manager):
        super().__init__()
        self.setWindowTitle("NASCAR Stats")
        self.setMinimumSize(1200, 800)

        self.theme_manager = theme_manager
        self.current_view = None

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.topbar = TopBar(self.theme_manager)
        self.topbar.season_changed.connect(self._handle_topbar_change)
        self.topbar.series_changed.connect(self._handle_topbar_change)
        outer_layout.addWidget(self.topbar)

        self.content_layout = QHBoxLayout()

        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(180)
        self.sidebar.navigation_requested.connect(self.handle_navigation)
        self.content_layout.addWidget(self.sidebar)

        outer_layout.addLayout(self.content_layout)
        self.setCentralWidget(central_widget)

        self.handle_navigation("races")  # Стартовая страница — гонки

    def handle_navigation(self, page_key: str):
        if self.current_view:
            self.content_layout.removeWidget(self.current_view)
            self.current_view.deleteLater()
            self.current_view = None

        if page_key == "races":
            season = int(self.topbar.season_combo.currentText())
            series = self.topbar.series_combo.currentText()
            view = RaceListView(season, series)
            view.race_selected.connect(self.show_race_details)
        elif page_key == "drivers":
            season = int(self.topbar.season_combo.currentText())
            series = self.topbar.series_combo.currentText()
            view = DriverListView(season, series)
            view.driver_selected.connect(self.show_driver_details)
        else:
            view = QLabel(f"Страница: {page_key}")
            view.setAlignment(Qt.AlignCenter)
            view.setStyleSheet("font-size: 20px;")

        self.current_view = view
        self.content_layout.addWidget(self.current_view, stretch=1)

    def show_race_details(self, race_id: int):
        if self.current_view:
            self.content_layout.removeWidget(self.current_view)
            self.current_view.deleteLater()
            self.current_view = None

        view = RaceDetailsView(race_id)
        self.current_view = view
        self.content_layout.addWidget(view, stretch=1)

    def show_driver_details(self, driver_id: int):
        if self.current_view:
            self.content_layout.removeWidget(self.current_view)
            self.current_view.deleteLater()
            self.current_view = None

        season = int(self.topbar.season_combo.currentText())
        series = self.topbar.series_combo.currentText()
        view = DriverDetailsView(driver_id, season, series)
        self.current_view = view
        self.content_layout.addWidget(view, stretch=1)

    def _handle_topbar_change(self, *_):
        if isinstance(self.current_view, RaceListView):
            season = int(self.topbar.season_combo.currentText())
            series = self.topbar.series_combo.currentText()
            self.current_view.update_data(season, series)
        elif isinstance(self.current_view, DriverListView):
            season = int(self.topbar.season_combo.currentText())
            series = self.topbar.series_combo.currentText()
            self.current_view.update_data(season, series)
