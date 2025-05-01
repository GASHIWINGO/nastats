from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import db_sync


class DriverDetailsView(QWidget):
    def __init__(self, driver_id: int, season: int, series: str, parent=None):
        super().__init__(parent)
        self.driver_id = driver_id
        self.season = season
        self.series = series

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(20)

        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.layout.addWidget(self.title_label)

        self.stats_group = QGroupBox("Статистика сезона")
        self.stats_layout = QGridLayout(self.stats_group)
        self.layout.addWidget(self.stats_group)

        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.canvas)

        self.load_data()

    def load_data(self):
        details = db_sync.get_driver_season_details(
            driver_id=self.driver_id,
            season=self.season,
            series_name=self.series
        )
        if not details:
            self.title_label.setText("Данные не найдены.")
            return

        self.title_label.setText(
            f"{details.get('driver_name')} — {self.series} {self.season}"
        )

        self._populate_stats(details)
        self._draw_finish_positions_chart()

    def _populate_stats(self, d):
        labels = [
            ("Гонки", d.get("races")),
            ("Победы", d.get("wins")),
            ("Топ-5", d.get("top5")),
            ("Топ-10", d.get("top10")),
            ("Кругов в лидерах", d.get("laps_led")),
            ("Завершено кругов", d.get("laps_completed")),
            ("Средняя стартовая позиция", d.get("avg_start")),
            ("Средняя финишная позиция", d.get("avg_finish")),
            ("Очки", d.get("points"))
        ]

        for i, (label_text, value) in enumerate(labels):
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setStyleSheet("font-weight: bold; font-size: 13px;")

            value_label = QLabel(str(value if value is not None else "-"))
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setStyleSheet("font-size: 13px;")

            self.stats_layout.addWidget(label, i // 3, (i % 3) * 2)
            self.stats_layout.addWidget(value_label, i // 3, (i % 3) * 2 + 1)

    def _draw_finish_positions_chart(self):
        series_id = db_sync.get_series_id_by_name(session=db_sync.sync_session_factory(), series_name=self.series)
        results = db_sync.get_driver_race_results_for_season(
            driver_id=self.driver_id,
            season=self.season,
            series_id=series_id
        )

        if not results:
            return

        race_nums = [r[0] for r in results]
        finish_positions = [r[2] for r in results]

        ax = self.canvas.figure.subplots()
        ax.clear()

        ax.plot(race_nums, finish_positions, marker='o', linestyle='-')
        ax.set_title("Финишные позиции по гонкам")
        ax.set_xlabel("Гонка")
        ax.set_ylabel("Позиция")
        ax.invert_yaxis()  # 1 — лучшая позиция
        ax.grid(True)

        self.canvas.draw()
