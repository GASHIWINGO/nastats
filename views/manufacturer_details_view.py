from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox, QPushButton, QTabWidget
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import db_sync


class ManufacturerDetailsView(QWidget):
    def __init__(self, manufacturer_id: int, season: int, series: str, parent=None):
        super().__init__(parent)
        self.manufacturer_id = manufacturer_id
        self.season = season
        self.series = series
        self.overall_mode = False

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)

        self.title = QLabel()
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.layout.addWidget(self.title)

        self.toggle_button = QPushButton("Статистика за всё время")
        self.toggle_button.clicked.connect(self._toggle_mode)
        self.layout.addWidget(self.toggle_button)

        self.stats_group = QGroupBox("Статистика")
        self.stats_layout = QGridLayout(self.stats_group)
        self.layout.addWidget(self.stats_group)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self._rebuild_tabs()
        self.load_data()

    def _toggle_mode(self):
        self.overall_mode = not self.overall_mode
        self.toggle_button.setText("Статистика сезона" if self.overall_mode else "Статистика за всё время")
        self.stats_group.setTitle("Статистика за всё время" if self.overall_mode else "Статистика")
        self._rebuild_tabs()
        self.load_data()

    def _rebuild_tabs(self):
        self.tabs.clear()
        self.pie_tab = QWidget()
        self.pie_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout = QVBoxLayout(self.pie_tab)
        layout.addWidget(self.pie_canvas)
        self.tabs.addTab(self.pie_tab, "Распределение финишей")
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def load_data(self):
        if self.overall_mode:
            self.details = db_sync.get_overall_manufacturer_stats(self.manufacturer_id)
        else:
            stats = db_sync.get_manufacturer_season_stats(self.season, self.series)
            self.details = next((d for d in stats if d.manufacturer_id == self.manufacturer_id), None)

        if not self.details:
            self.title.setText("Данные не найдены.")
            return

        name = self.details.get("manufacturer_name", f"ID {self.manufacturer_id}")
        self.title.setText(f"{name} — {'ВСЯ КАРЬЕРА' if self.overall_mode else f'{self.series} {self.season}'}")
        self._populate_stats(self.details)
        self._draw_pie_chart()

    def _populate_stats(self, d):
        for i in reversed(range(self.stats_layout.count())):
            widget = self.stats_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        labels = [
            ("Участий", d.get("entries", 0)),
            ("Победы", d.get("wins", 0)),
            ("Топ-5", d.get("top5", 0)),
            ("Топ-10", d.get("top10", 0)),
            ("Кругов в лидерах", d.get("laps_led", 0)),
        ]

        for i, (text, value) in enumerate(labels):
            label = QLabel(text)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setStyleSheet("font-weight: bold; font-size: 13px;")

            val = QLabel(str(value if value is not None else "-"))
            val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            val.setStyleSheet("font-size: 13px;")

            self.stats_layout.addWidget(label, i // 2, (i % 2) * 2)
            self.stats_layout.addWidget(val, i // 2, (i % 2) * 2 + 1)

    def _on_tab_changed(self, index):
        self._draw_pie_chart()

    def _draw_pie_chart(self):
        if not self.details or self.details.get('entries', 0) == 0:
            return

        wins = self.details.get("wins", 0)
        top5 = self.details.get("top5", 0) - wins
        top10 = self.details.get("top10", 0) - wins - top5
        others = self.details.get("entries", 0) - wins - top5 - top10

        data = [("Победы", wins), ("Топ-5", top5), ("Топ-10", top10), ("Остальные", others)]
        filtered = [(label, v) for label, v in data if v > 0]

        self.pie_canvas.figure.clear()
        ax = self.pie_canvas.figure.add_subplot(111)

        if filtered:
            labels, values = zip(*filtered)
            ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140)
            ax.set_title("Распределение финишных позиций")
        else:
            ax.text(0.5, 0.5, "Нет данных для отображения", ha='center', va='center')

        self.pie_canvas.draw()
