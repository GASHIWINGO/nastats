from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox,
    QSizePolicy, QTabWidget
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

        # --- Вкладки графиков ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # 1. Финишные позиции
        self.finish_tab = QWidget()
        self.finish_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self._add_chart_tab(self.finish_tab, self.finish_canvas, "Финишные позиции")

        # 2. Очки по гонкам
        self.points_tab = QWidget()
        self.points_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self._add_chart_tab(self.points_tab, self.points_canvas, "Очки по гонкам")

        # 3. Распределение финишей
        self.pie_tab = QWidget()
        self.pie_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self._add_chart_tab(self.pie_tab, self.pie_canvas, "Распределение финишей")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.load_data()

    def _add_chart_tab(self, container, canvas, label):
        layout = QVBoxLayout(container)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(canvas)
        self.tabs.addTab(container, label)

    def load_data(self):
        self.details = db_sync.get_driver_season_details(
            driver_id=self.driver_id,
            season=self.season,
            series_name=self.series
        )
        if not self.details:
            self.title_label.setText("Данные не найдены.")
            return

        self.title_label.setText(
            f"{self.details.get('driver_name')} — {self.series} {self.season}"
        )

        self._populate_stats(self.details)
        self._on_tab_changed(0)  # отрисовать первый график

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

    def _on_tab_changed(self, index):
        if index == 0:
            self._draw_finish_positions_chart()
        elif index == 1:
            self._draw_points_chart()
        elif index == 2:
            self._draw_finish_distribution_pie()

    def _draw_finish_positions_chart(self):
        session = db_sync.sync_session_factory()
        series_id = db_sync.get_series_id_by_name(session=session, series_name=self.series)
        results = db_sync.get_driver_race_results_for_season(
            driver_id=self.driver_id,
            season=self.season,
            series_id=series_id
        )

        session.close()

        if not results:
            return

        race_nums = [r[0] for r in results]
        finish_positions = [r[2] for r in results]

        ax = self.finish_canvas.figure.subplots()
        ax.clear()

        ax.plot(race_nums, finish_positions, marker='o', linestyle='-')
        ax.set_title("Финишные позиции по гонкам")
        ax.set_xlabel("Гонка")
        ax.set_ylabel("Позиция")
        ax.invert_yaxis()
        ax.grid(True)

        self.finish_canvas.draw()

    def _draw_points_chart(self):
        session = db_sync.sync_session_factory()
        series_id = db_sync.get_series_id_by_name(session=session, series_name=self.series)
        session.close()

        if not series_id:
            return

        try:
            with db_sync.get_db_session() as session:
                stmt = db_sync.select(
                    db_sync.races_table.c.race_num_in_season,
                    db_sync.race_entries_table.c.points
                ).join_from(
                    db_sync.race_entries_table, db_sync.races_table,
                    db_sync.race_entries_table.c.race_id == db_sync.races_table.c.race_id
                ).where(
                    (db_sync.race_entries_table.c.driver_id == self.driver_id) &
                    (db_sync.races_table.c.season == self.season) &
                    (db_sync.races_table.c.series_id == series_id)
                ).order_by(db_sync.races_table.c.race_num_in_season)

                results = session.execute(stmt).fetchall()

        except Exception as e:
            print(f"Ошибка получения очков: {e}")
            results = []

        if not results:
            return

        race_nums = [r[0] for r in results]
        points = [r[1] for r in results]

        ax = self.points_canvas.figure.subplots()
        ax.clear()

        ax.plot(race_nums, points, marker='s', linestyle='-', color='green')
        ax.set_title("Очки по гонкам")
        ax.set_xlabel("Гонка")
        ax.set_ylabel("Очки")
        ax.grid(True)

        self.points_canvas.draw()

    def _draw_finish_distribution_pie(self):
        if not self.details or self.details.get('races', 0) == 0:
            return

        wins = self.details.get("wins", 0)
        top5 = self.details.get("top5", 0) - wins
        top10 = self.details.get("top10", 0) - wins - top5
        others = self.details.get("races", 0) - wins - top5 - top10

        raw_data = [
            ("Победы", wins),
            ("Топ-5", top5),
            ("Топ-10", top10),
            ("Остальные", others)
        ]

        # ❗ Удаляем нулевые значения
        filtered_data = [(label, value) for label, value in raw_data if value > 0]

        if not filtered_data:
            ax = self.pie_canvas.figure.subplots()
            ax.clear()
            ax.text(0.5, 0.5, "Нет данных для отображения", ha='center', va='center')
            ax.set_title("Распределение финишных позиций")
            self.pie_canvas.draw()
            return

        labels, values = zip(*filtered_data)

        ax = self.pie_canvas.figure.subplots()
        ax.clear()

        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140)
        ax.set_title("Распределение финишных позиций")

        self.pie_canvas.draw()
