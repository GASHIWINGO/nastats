from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGridLayout, QGroupBox, QScrollArea, QFrame, QComboBox, QRadioButton,
    QSpacerItem, QSizePolicy, QCompleter, QButtonGroup
)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QPalette
import db_sync
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np # Для расположения столбцов на графике

# Модель для QComboBox с возможностью хранения ID
class IdNameItemModel(QStandardItemModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        if data:
            for item_id, item_name in data:
                item = QStandardItem(item_name)
                item.setData(item_id, Qt.UserRole) # Сохраняем ID в UserRole
                self.appendRow(item)

    def getId(self, index):
        # Проверяем валидность индекса перед доступом к данным
        if index >= 0 and index < self.rowCount():
             item = self.item(index)
             if item:
                 return item.data(Qt.UserRole)
        return None # Возвращаем None, если индекс невалиден или элемента нет

class CompareView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Кэши данных
        self._drivers_data = []
        self._teams_data = []
        self._manufacturers_data = []
        self.stats1_cache = None
        self.stats2_cache = None
        self.season_results1_cache = None
        self.season_results2_cache = None
        # Кэши выбранного типа/режима
        self.current_entity_type = "driver"
        self.is_season_mode_cache = False

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)
        self.setLayout(self.layout)

        self.load_initial_data()
        self.setup_selection_ui()
        self.setup_results_ui()
        self._update_combos_for_entity_type()

    def load_initial_data(self):
        """Загружает данные, необходимые для инициализации UI."""
        self._drivers_data = db_sync.get_all_drivers_list()
        self._teams_data = db_sync.get_all_teams_list()
        self._manufacturers_data = db_sync.get_all_manufacturers_list()

    def setup_selection_ui(self):
        # --- Группа выбора типа сущности ---
        entity_type_layout = QHBoxLayout()
        self.entity_type_label = QLabel("Тип:")
        self.driver_radio = QRadioButton("Гонщики")
        self.team_radio = QRadioButton("Команды")
        self.manu_radio = QRadioButton("Производители")
        self.driver_radio.setChecked(True)

        self.entity_type_group = QButtonGroup(self)
        self.entity_type_group.addButton(self.driver_radio)
        self.entity_type_group.addButton(self.team_radio)
        self.entity_type_group.addButton(self.manu_radio)

        entity_type_layout.addWidget(self.entity_type_label)
        entity_type_layout.addWidget(self.driver_radio)
        entity_type_layout.addWidget(self.team_radio)
        entity_type_layout.addWidget(self.manu_radio)
        entity_type_layout.addStretch()
        self.layout.addLayout(entity_type_layout)

        # Подключаем сигнал смены типа сущности
        self.driver_radio.toggled.connect(lambda checked: self._on_entity_type_changed("driver", checked))
        self.team_radio.toggled.connect(lambda checked: self._on_entity_type_changed("team", checked))
        self.manu_radio.toggled.connect(lambda checked: self._on_entity_type_changed("manufacturer", checked))

        # --- Верхняя часть: Выбор режима и контекста (как и раньше) ---
        context_layout = QHBoxLayout()
        context_layout.setSpacing(10)

        self.mode_label = QLabel("Режим:")
        self.career_radio = QRadioButton("Карьера")
        self.season_radio = QRadioButton("Сезон")
        self.career_radio.setChecked(True) # По умолчанию - карьера

        # Определяем последний сезон и список сезонов
        latest_season = db_sync.get_latest_season() or 2025
        season_list = [str(y) for y in range(latest_season, 1948, -1)]

        self.season_label = QLabel("Сезон:")
        self.season_combo = QComboBox()
        self.season_combo.addItems(season_list)
        # Устанавливаем текущий сезон, если он есть в списке
        if str(latest_season) in season_list:
            self.season_combo.setCurrentText(str(latest_season))

        self.series_label = QLabel("Серия:")
        self.series_combo = QComboBox()
        self.series_combo.addItems(["Cup", "Xfinity", "Truck"])

        # Управляем видимостью выбора сезона/серии
        self.season_label.setVisible(False)
        self.season_combo.setVisible(False)
        self.series_label.setVisible(False)
        self.series_combo.setVisible(False)

        # Подключаем сигнал от ОДНОЙ кнопки (или обеих к одному слоту)
        self.career_radio.toggled.connect(self._toggle_context_widgets)
        # self.season_radio.toggled.connect(self._toggle_context_widgets) # Не обязательно дублировать

        context_layout.addWidget(self.mode_label)
        context_layout.addWidget(self.career_radio)
        context_layout.addWidget(self.season_radio)
        context_layout.addSpacing(20)
        context_layout.addWidget(self.season_label)
        context_layout.addWidget(self.season_combo)
        context_layout.addWidget(self.series_label)
        context_layout.addWidget(self.series_combo)
        context_layout.addStretch()

        self.layout.addLayout(context_layout)

        # --- Нижняя часть: Выбор сущностей и кнопка ---
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(10)

        self.entity1_label = QLabel("Гонщик 1:") # Текст будет меняться
        self.entity1_combo = self._create_dynamic_combo() # Используем новый метод
        self.entity2_label = QLabel("Гонщик 2:") # Текст будет меняться
        self.entity2_combo = self._create_dynamic_combo()

        self.compare_button = QPushButton("Сравнить")
        self.compare_button.clicked.connect(self.load_comparison_data)

        selection_layout.addWidget(self.entity1_label)
        selection_layout.addWidget(self.entity1_combo, 1)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(self.entity2_label)
        selection_layout.addWidget(self.entity2_combo, 1)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(self.compare_button)
        self.layout.addLayout(selection_layout)

    def _on_entity_type_changed(self, type_key, checked):
        """Обработчик смены типа сущности."""
        if checked: # Реагируем только на выбор новой кнопки
            print(f"DEBUG: Entity type changed to: {type_key}")
            self.current_entity_type = type_key
            self._update_combos_for_entity_type()
            self.clear_results() # Очищаем результаты при смене типа

    def _update_combos_for_entity_type(self):
        """Обновляет модели и метки комбобоксов в соответствии с выбранным типом сущности."""
        label_text = "Сущность" # Значение по умолчанию
        if self.current_entity_type == "driver":
            data = self._drivers_data
            label_text = "Гонщик"
        elif self.current_entity_type == "team":
            data = self._teams_data
            label_text = "Команда"
        elif self.current_entity_type == "manufacturer": # <-- Обработка нового типа
            data = self._manufacturers_data
            label_text = "Произв-ль" # Сокращенно для метки
        else:
            data = []

        self.entity1_label.setText(f"{label_text} 1:")
        self.entity2_label.setText(f"{label_text} 2:")

        # Обновляем модель для каждого комбобокса
        for combo in [self.entity1_combo, self.entity2_combo]:
            model = IdNameItemModel(data, self)
            combo.setModel(model)
            combo.completer().setModel(model)
            combo.setCurrentIndex(-1)
            # Плейсхолдер тоже меняется
            combo.lineEdit().setPlaceholderText(f"Начните вводить {label_text.lower()}...")

    def _create_dynamic_combo(self) -> QComboBox:
        """Создает QComboBox без начальной модели (модель будет установлена позже)."""
        combo = QComboBox()
        combo.setEditable(True)
        combo.lineEdit().setValidator(None)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setMinimumWidth(200)
        combo.setMaxVisibleItems(15)

        # Настраиваем completer без модели (модель будет установлена позже)
        completer = QCompleter(self) # Создаем completer без модели
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(completer) # Устанавливаем completer для combo

        return combo

    def _toggle_context_widgets(self, checked):
        """Показывает/скрывает виджеты выбора сезона/серии."""
        # Срабатывает при изменении состояния career_radio
        # Если career_radio выбрана (checked=True), то режим сезона выключен
        is_season_mode = not checked
        self.season_label.setVisible(is_season_mode)
        self.season_combo.setVisible(is_season_mode)
        self.series_label.setVisible(is_season_mode)
        self.series_combo.setVisible(is_season_mode)

    def setup_results_ui(self):
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.results_container = QWidget()
        self.results_main_layout = QVBoxLayout(self.results_container)
        self.results_main_layout.setSpacing(20)

        # --- Статистика (как и раньше) ---
        self.stats_layout = QHBoxLayout()
        self.driver1_stats_group = QGroupBox("Гонщик 1")
        self.driver1_grid = QGridLayout(self.driver1_stats_group)
        self.driver1_stats_group.setMinimumWidth(350)

        self.driver2_stats_group = QGroupBox("Гонщик 2")
        self.driver2_grid = QGridLayout(self.driver2_stats_group)
        self.driver2_stats_group.setMinimumWidth(350)

        self.stats_layout.addWidget(self.driver1_stats_group)
        self.stats_layout.addWidget(self.driver2_stats_group)
        self.stats_layout.addStretch()

        # Добавляем layout статистики в основной вертикальный layout
        self.results_main_layout.addLayout(self.stats_layout)

        # --- Графики ---
        # Убираем аргумент parent
        self.career_chart_canvas = FigureCanvas(Figure(figsize=(8, 4))) # <-- Убран parent
        self.career_chart_canvas.setVisible(False)
        self.career_chart_canvas.setMinimumHeight(250)
        self.results_main_layout.addWidget(self.career_chart_canvas)

        # Убираем аргумент parent
        self.season_finish_canvas = FigureCanvas(Figure(figsize=(8, 4))) # <-- Убран parent
        self.season_finish_canvas.setVisible(False)
        self.season_finish_canvas.setMinimumHeight(250)
        self.results_main_layout.addWidget(self.season_finish_canvas)

        # Убираем аргумент parent
        self.season_points_canvas = FigureCanvas(Figure(figsize=(8, 4))) # <-- Убран parent
        self.season_points_canvas.setVisible(False)
        self.season_points_canvas.setMinimumHeight(250)
        self.results_main_layout.addWidget(self.season_points_canvas)

        self.scroll_area.setWidget(self.results_container)
        self.layout.addWidget(self.scroll_area, stretch=1)

    def load_comparison_data(self):
        self.clear_results()
        idx1 = self.entity1_combo.currentIndex()
        idx2 = self.entity2_combo.currentIndex()

        if idx1 < 0 or idx2 < 0:
            print(f"Ошибка: Выберите обе(их) {self.current_entity_type}.")
            return

        model1: IdNameItemModel = self.entity1_combo.model()
        model2: IdNameItemModel = self.entity2_combo.model()
        id1 = model1.getId(idx1)
        id2 = model2.getId(idx2)

        if not id1 or not id2 or id1 == id2:
            print(f"Ошибка: Выберите две разные сущности ({self.current_entity_type}).")
            return

        is_season_mode = self.season_radio.isChecked()
        season = int(self.season_combo.currentText()) if is_season_mode else None
        series = self.series_combo.currentText() if is_season_mode else None
        self.is_season_mode_cache = is_season_mode
        series_id = None
        context_str = ""
        # Сбрасываем кэши перед загрузкой
        self.stats1_cache = None
        self.stats2_cache = None
        self.season_results1_cache = None
        self.season_results2_cache = None

        # --- Выбираем функции загрузки данных в зависимости от типа сущности ---
        if self.current_entity_type == "driver":
            if is_season_mode:
                with db_sync.get_db_session() as session: series_id = db_sync.get_series_id_by_name(session, series)
                if not series_id: print(f"Ошибка: Серия '{series}' не найдена."); return
                self.stats1_cache = db_sync.get_driver_season_details(id1, season, series)
                self.stats2_cache = db_sync.get_driver_season_details(id2, season, series)
                self.season_results1_cache = db_sync.get_driver_race_results_for_season(id1, season, series_id)
                self.season_results2_cache = db_sync.get_driver_race_results_for_season(id2, season, series_id)
                context_str = f"{series} {season}"
            else:
                self.stats1_cache = db_sync.get_overall_driver_stats(id1)
                self.stats2_cache = db_sync.get_overall_driver_stats(id2)
                context_str = "Карьера"
        elif self.current_entity_type == "team":
            if is_season_mode:
                with db_sync.get_db_session() as session: series_id = db_sync.get_series_id_by_name(session, series)
                if not series_id: print(f"Ошибка: Серия '{series}' не найдена."); return
                self.stats1_cache = db_sync.get_team_season_details(id1, season, series)
                self.stats2_cache = db_sync.get_team_season_details(id2, season, series)
                # --- Загружаем данные для сезонных графиков команд ---
                self.season_results1_cache = db_sync.get_team_race_results_for_season(id1, season, series_id)
                self.season_results2_cache = db_sync.get_team_race_results_for_season(id2, season, series_id)
                context_str = f"{series} {season}"
            else:
                self.stats1_cache = db_sync.get_overall_team_stats(id1)
                self.stats2_cache = db_sync.get_overall_team_stats(id2)
                context_str = "Карьера"
        elif self.current_entity_type == "manufacturer":
            if is_season_mode:
                # Получаем статистику ВСЕХ производителей за сезон
                all_manu_stats = db_sync.get_manufacturer_season_stats(season, series)
                # Находим нужных нам по ID
                self.stats1_cache = next((m for m in all_manu_stats if m.get('manufacturer_id') == id1), None)
                self.stats2_cache = next((m for m in all_manu_stats if m.get('manufacturer_id') == id2), None)
                # Сезонных графиков для производителей пока нет
                self.season_results1_cache = None
                self.season_results2_cache = None
                context_str = f"{series} {season}"
            else:
                self.stats1_cache = db_sync.get_overall_manufacturer_stats(id1)
                self.stats2_cache = db_sync.get_overall_manufacturer_stats(id2)
                context_str = "Карьера"

        self.display_comparison(self.stats1_cache, self.stats2_cache, context_str)
        self.draw_comparison_chart()

    def display_comparison(self, stats1, stats2, context_str: str):
        # --- Очистка теперь в load_comparison_data ---
        title1 = self._get_title(stats1, f"{self.current_entity_type.capitalize()} 1", context_str)
        title2 = self._get_title(stats2, f"{self.current_entity_type.capitalize()} 2", context_str)
        # --- Используем правильные группы ---
        self.driver1_stats_group.setTitle(title1) # Оставляем старые имена переменных для групп/сеток
        self.driver2_stats_group.setTitle(title2)
        self._populate_comparison_grids(stats1, stats2) # Эта функция адаптируется

        # Явное отображение групп
        if stats1 or stats2:
             self.driver1_stats_group.setVisible(True)
             self.driver2_stats_group.setVisible(True)
        else:
             self.driver1_stats_group.setVisible(False)
             self.driver2_stats_group.setVisible(False)

        # Обновление UI
        self.driver1_stats_group.update()
        self.driver2_stats_group.update()
        self.results_container.adjustSize()
        self.results_container.update()

    def _get_title(self, stats: dict | None, default_prefix: str, context_str: str) -> str:
        """Формирует заголовок для группы статистики."""
        if not stats:
            return f"{default_prefix} (не найден)"
        # Определяем ключ для имени в зависимости от типа
        name_key = f"{self.current_entity_type}_name" # driver_name, team_name, ...
        id_key = f"{self.current_entity_type}_id"
        name = stats.get(name_key, f"{default_prefix} ID {stats.get(id_key, '?')}")
        return f"{name} — {context_str}"

    def _populate_comparison_grids(self, stats1: dict | None, stats2: dict | None):
        """Заполняет обе сетки (QGridLayout) статистикой, выделяя лучшие значения."""
        # Отладочный вывод полученных данных
        print("-" * 20)
        print(f"DEBUG [populate_grids] stats1: {stats1}")
        print(f"DEBUG [populate_grids] stats2: {stats2}")
        print("-" * 20)

        # --- Явная очистка сеток перед заполнением (на всякий случай) ---
        for grid in [self.driver1_grid, self.driver2_grid]:
             while grid.count():
                 child = grid.takeAt(0)
                 if child.widget():
                     child.widget().deleteLater()
        # --- Конец явной очистки ---

        stat_map = {}
        if self.current_entity_type == "driver":
            stat_map = {
                "races": ("Гонки", True), "wins": ("Победы", True), "top5": ("Топ-5", True),
                "top10": ("Топ-10", True), "laps_led": ("Кругов в лидерах", True),
                "laps_completed": ("Завершено кругов", True), "avg_start": ("Средний старт", False),
                "avg_finish": ("Средний финиш", False), "points": ("Очки", True)
            }
        elif self.current_entity_type == "team":
             stat_map = {
                "entries": ("Участий", True), "wins": ("Победы", True), "top5": ("Топ-5", True),
                "top10": ("Топ-10", True), "laps_led": ("Кругов в лидерах", True),
                "laps_completed": ("Завершено кругов", True), "avg_start": ("Средний старт (команды)", False),
                "avg_finish": ("Средний финиш (команды)", False), "points": ("Очки (команды)", True)
            }
        elif self.current_entity_type == "manufacturer":
            stat_map = {
                "entries": ("Участий", True),
                "wins": ("Победы", True),
                "top5": ("Топ-5", True),
                "top10": ("Топ-10", True),
                "laps_led": ("Круги\nлидерства", True)
            }

        default_palette = self.palette()
        highlight_color = QColor(Qt.darkGreen).lighter(150)

        row = 0
        any_widget_added = False # Флаг для проверки, добавили ли хоть что-то
        for key, (label_text, more_is_better) in stat_map.items():
            val1 = stats1.get(key) if stats1 else None
            val2 = stats2.get(key) if stats2 else None

            # Пропускаем строку, если данных нет у обоих
            if val1 is None and val2 is None:
                # print(f"DEBUG [populate_grids] Skipping key '{key}' (both None)") # Можно раскомментировать для детальной отладки
                continue

            val1_str = self._format_value(val1)
            val2_str = self._format_value(val2)
            is_val1_better = False
            is_val2_better = False
            if val1 is not None and val2 is not None:
                try:
                    num_val1 = float(val1); num_val2 = float(val2)
                    if more_is_better: is_val1_better, is_val2_better = num_val1 > num_val2, num_val2 > num_val1
                    else: is_val1_better, is_val2_better = num_val1 < num_val2, num_val2 < num_val1
                except (ValueError, TypeError): pass
            elif val1 is not None: is_val1_better = True
            elif val2 is not None: is_val2_better = True

            # Создаем виджеты
            label1 = QLabel(label_text + ":"); label1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value1_label = QLabel(val1_str); value1_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); value1_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label2 = QLabel(label_text + ":"); label2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value2_label = QLabel(val2_str); value2_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); value2_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            # Применяем стиль
            if is_val1_better: value1_label.setStyleSheet(f"font-weight: bold; color: {highlight_color.name()};")
            if is_val2_better: value2_label.setStyleSheet(f"font-weight: bold; color: {highlight_color.name()};")

            # Добавляем виджеты
            self.driver1_grid.addWidget(label1, row, 0)
            self.driver1_grid.addWidget(value1_label, row, 1)
            self.driver2_grid.addWidget(label2, row, 0)
            self.driver2_grid.addWidget(value2_label, row, 1)
            any_widget_added = True # Устанавливаем флаг
            # print(f"DEBUG [populate_grids] Added widgets for key '{key}' at row {row}") # Можно раскомментировать

            row += 1

        # Обработка случая, если вообще не было данных для сравнения
        if not any_widget_added: # Проверяем флаг
            print("WARN [populate_grids] No comparison data found to display in grids.")
            no_data_label1 = QLabel("Нет данных\nдля сравнения."); no_data_label1.setAlignment(Qt.AlignCenter); no_data_label1.setStyleSheet("color: gray;")
            self.driver1_grid.addWidget(no_data_label1, 0, 0, 1, 2)
            no_data_label2 = QLabel("Нет данных\nдля сравнения."); no_data_label2.setAlignment(Qt.AlignCenter); no_data_label2.setStyleSheet("color: gray;")
            self.driver2_grid.addWidget(no_data_label2, 0, 0, 1, 2)
        else:
             print(f"DEBUG [populate_grids] Finished loop. Total rows added: {row}")

        # --- Добавляем активацию layout'ов ---
        print("DEBUG [populate_grids] Activating grids...")
        self.driver1_grid.activate()
        self.driver2_grid.activate()
        # --- Конец добавления ---

    def _format_value(self, value):
        """Форматирует значение для отображения."""
        if isinstance(value, float):
            return f"{value:.1f}"
        elif value is not None:
            return str(value)
        else:
            return "-"

    def clear_results(self):
        """Очищает область отображения результатов статистики и графиков."""
        # Очистка сеток статистики
        self.driver1_stats_group.setTitle("Гонщик 1")
        self.driver2_stats_group.setTitle("Гонщик 2")
        for grid in [self.driver1_grid, self.driver2_grid]:
            while grid.count():
                child = grid.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Очищаем и скрываем ВСЕ графики
        for canvas in [self.career_chart_canvas, self.season_finish_canvas, self.season_points_canvas]:
            canvas.figure.clear()
            canvas.draw()
            canvas.setVisible(False)

        # Сбрасываем ВСЕ кэши
        self.stats1_cache = None; self.stats2_cache = None
        self.season_results1_cache = None; self.season_results2_cache = None
        # Режим и тип сбрасывать не нужно, они управляются UI

    def draw_comparison_chart(self):
        """Рисует график(и) сравнения в зависимости от режима и типа сущности."""
        self.career_chart_canvas.setVisible(False)
        self.season_finish_canvas.setVisible(False)
        self.season_points_canvas.setVisible(False)

        if self.is_season_mode_cache:
            if self.current_entity_type == "driver":
                self._draw_season_finish_chart(self.stats1_cache, self.stats2_cache, self.season_results1_cache, self.season_results2_cache)
                self._draw_season_points_chart(self.stats1_cache, self.stats2_cache, self.season_results1_cache, self.season_results2_cache)
            elif self.current_entity_type == "team":
                 self._draw_season_team_avg_finish_chart(self.stats1_cache, self.stats2_cache, self.season_results1_cache, self.season_results2_cache)
            elif self.current_entity_type == "manufacturer":
                self._draw_overall_manufacturer_bar_chart(self.stats1_cache, self.stats2_cache)
        else: # Режим карьеры
            if self.current_entity_type == "driver":
                self._draw_overall_bar_chart(self.stats1_cache, self.stats2_cache)
            elif self.current_entity_type == "team":
                 self._draw_overall_team_bar_chart(self.stats1_cache, self.stats2_cache)
            elif self.current_entity_type == "manufacturer":
                self._draw_overall_manufacturer_bar_chart(self.stats1_cache, self.stats2_cache)

        # Перерисовываем все canvas
        self.career_chart_canvas.draw()
        self.season_finish_canvas.draw()
        self.season_points_canvas.draw()

    def _draw_overall_bar_chart(self, stats1, stats2):
        """Рисует столбчатую диаграмму сравнения карьеры ГОНЩИКОВ."""
        if not stats1 or not stats2:
             return # Данных нет, график остается скрытым

        # --- Убираем блок try...except, т.к. причина найдена ---
        # try:
        labels_map = {
            'wins': 'Победы', 'top5': 'Топ-5', 'top10': 'Топ-10',
            'laps_led': 'Круги\nлидерства', 'races': 'Гонки'
        }
        stat_keys = list(labels_map.keys())
        labels = [labels_map[k] for k in stat_keys]

        values1 = [stats1.get(key, 0) for key in stat_keys]
        values2 = [stats2.get(key, 0) for key in stat_keys]
        # print(f"DEBUG: Значения для графика 1: {values1}") # Можно убрать
        # print(f"DEBUG: Значения для графика 2: {values2}") # Можно убрать

        name1 = stats1.get('driver_name', 'Гонщик 1')
        name2 = stats2.get('driver_name', 'Гонщик 2')

        x = np.arange(len(labels))
        width = 0.35

        fig = self.career_chart_canvas.figure
        # print("DEBUG: Очистка фигуры...") # Можно убрать
        fig.clear()
        ax = fig.add_subplot(111)
        # print("DEBUG: Фигура очищена, subplot добавлен.") # Можно убрать

        # print("DEBUG: Отрисовка столбцов...") # Можно убрать
        rects1 = ax.bar(x - width/2, values1, width, label=name1)
        rects2 = ax.bar(x + width/2, values2, width, label=name2)
        # print("DEBUG: Столбцы отрисованы.") # Можно убрать

        ax.set_ylabel('Значение')
        ax.set_title('Сравнение статистики за карьеру')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        # print("DEBUG: Настроены оси и легенда.") # Можно убрать

        # print("DEBUG: Добавление меток столбцов...") # Можно убрать
        ax.bar_label(rects1, padding=3, fmt='%g')
        ax.bar_label(rects2, padding=3, fmt='%g')
        # print("DEBUG: Метки столбцов добавлены.") # Можно убрать

        # print("DEBUG: Применение tight_layout...") # Можно убрать
        fig.tight_layout()
        # print("DEBUG: tight_layout применен.") # Можно убрать

        # print("DEBUG: Отрисовка canvas и установка видимости...") # Можно убрать
        self.career_chart_canvas.draw()
        self.career_chart_canvas.setVisible(True)
        # print("DEBUG: График отрисован и показан.") # Можно убрать

        # except Exception as e:
        #     print(f"!!! Ошибка при отрисовке бар-чарта: {e}")
        #     import traceback
        #     traceback.print_exc()
        #     try:
        #          self.career_chart_canvas.setVisible(False)
        #          self.career_chart_canvas.draw()
        #     except Exception as hide_e:
        #          print(f"!!! Дополнительная ошибка при попытке скрыть canvas: {hide_e}")

    def _draw_season_finish_chart(self, stats1, stats2, results1, results2):
        """Рисует линейный график сравнения финишей ГОНЩИКОВ за сезон."""
        if not results1 and not results2: # Если нет данных ни у одного
            return # График останется скрытым

        fig = self.season_finish_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        name1 = stats1.get('driver_name', 'Гонщик 1') if stats1 else 'Гонщик 1'
        name2 = stats2.get('driver_name', 'Гонщик 2') if stats2 else 'Гонщик 2'

        all_race_nums = set() # Собираем все номера гонок для оси X

        if results1:
            race_nums1 = [r[0] for r in results1]
            finishes1 = [r[2] for r in results1 if r[2] is not None] # Учитываем только фактические финиши
            # Корректируем race_nums1, если были пропуски финишей
            race_nums1_valid = [r[0] for r in results1 if r[2] is not None]
            if finishes1: # Рисуем, только если есть что рисовать
                ax.plot(race_nums1_valid, finishes1, marker='o', linestyle='-', label=f"{name1} Финиш")
                all_race_nums.update(race_nums1_valid)

        if results2:
            race_nums2 = [r[0] for r in results2]
            finishes2 = [r[2] for r in results2 if r[2] is not None]
            race_nums2_valid = [r[0] for r in results2 if r[2] is not None]
            if finishes2:
                ax.plot(race_nums2_valid, finishes2, marker='s', linestyle='--', label=f"{name2} Финиш")
                all_race_nums.update(race_nums2_valid)

        if not all_race_nums: # Если никто не финишировал ни разу
             ax.text(0.5, 0.5, "Нет данных о финишах", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
        else:
            ax.set_xlabel("Номер гонки в сезоне")
            ax.set_ylabel("Финишная позиция")
            ax.set_title("Сравнение финишных позиций по гонкам")
            ax.invert_yaxis() # Меньше позиция = выше на графике
            ax.legend()
            ax.grid(True, axis='y', linestyle=':') # Сетка по оси Y
            # Устанавливаем целые числа на оси X, если гонок немного
            if len(all_race_nums) > 0:
                 max_race = max(all_race_nums)
                 if max_race <= 40: # Примерный порог
                     ax.set_xticks(sorted(list(all_race_nums)))

        # --- Сначала вызываем tight_layout ---
        fig.tight_layout()
        # --- Затем увеличиваем нижний отступ ЕЩЕ БОЛЬШЕ ---
        fig.subplots_adjust(bottom=0.25) # <--- Изменено на 0.25 и вызвано ПОСЛЕ tight_layout
        # --- Конец изменения ---

        self.season_finish_canvas.draw() # Перерисовываем после изменений
        self.season_finish_canvas.setVisible(True)

    def _draw_season_points_chart(self, stats1, stats2, results1, results2):
        """Рисует линейный график сравнения очков ГОНЩИКОВ по гонкам за сезон."""
        if not results1 and not results2:
            return

        fig = self.season_points_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        name1 = stats1.get('driver_name', 'Гонщик 1') if stats1 else 'Гонщик 1'
        name2 = stats2.get('driver_name', 'Гонщик 2') if stats2 else 'Гонщик 2'

        all_race_nums = set()

        if results1:
            # Используем 4-й элемент (индекс 3) - очки
            race_nums1 = [r[0] for r in results1]
            points1 = [r[3] for r in results1 if r[3] is not None]
            race_nums1_valid = [r[0] for r in results1 if r[3] is not None]
            if points1:
                ax.plot(race_nums1_valid, points1, marker='o', linestyle='-', label=f"{name1} Очки")
                all_race_nums.update(race_nums1_valid)

        if results2:
            race_nums2 = [r[0] for r in results2]
            points2 = [r[3] for r in results2 if r[3] is not None]
            race_nums2_valid = [r[0] for r in results2 if r[3] is not None]
            if points2:
                ax.plot(race_nums2_valid, points2, marker='s', linestyle='--', label=f"{name2} Очки")
                all_race_nums.update(race_nums2_valid)

        if not all_race_nums:
             ax.text(0.5, 0.5, "Нет данных об очках", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
        else:
            ax.set_xlabel("Номер гонки в сезоне")
            ax.set_ylabel("Набранные очки")
            ax.set_title("Сравнение набранных очков по гонкам")
            ax.legend()
            ax.grid(True, axis='y', linestyle=':')
            if len(all_race_nums) > 0:
                 max_race = max(all_race_nums)
                 if max_race <= 40:
                     ax.set_xticks(sorted(list(all_race_nums)))

        # --- Сначала вызываем tight_layout ---
        fig.tight_layout()
        # --- Затем увеличиваем нижний отступ ЕЩЕ БОЛЬШЕ ---
        fig.subplots_adjust(bottom=0.25) # <--- Изменено на 0.25 и вызвано ПОСЛЕ tight_layout
        # --- Конец изменения ---

        self.season_points_canvas.draw() # Перерисовываем после изменений
        self.season_points_canvas.setVisible(True)

    def _draw_season_team_avg_finish_chart(self, stats1, stats2, results1, results2):
        """Рисует график средних финишных позиций КОМАНД по гонкам за сезон."""
        if not results1 and not results2:
            return # График season_finish_canvas останется скрытым

        fig = self.season_finish_canvas.figure # Используем canvas финишей
        fig.clear()
        ax = fig.add_subplot(111)

        name1 = stats1.get('team_name', 'Команда 1') if stats1 else 'Команда 1'
        name2 = stats2.get('team_name', 'Команда 2') if stats2 else 'Команда 2'

        all_race_nums = set()

        # results для команд: (race_num, avg_start, avg_finish)
        if results1:
            race_nums1 = [r[0] for r in results1]
            avg_finishes1 = [r[2] for r in results1 if r[2] is not None]
            race_nums1_valid = [r[0] for r in results1 if r[2] is not None]
            if avg_finishes1:
                ax.plot(race_nums1_valid, avg_finishes1, marker='o', linestyle='-', label=f"{name1} Ср.Финиш")
                all_race_nums.update(race_nums1_valid)

        if results2:
            race_nums2 = [r[0] for r in results2]
            avg_finishes2 = [r[2] for r in results2 if r[2] is not None]
            race_nums2_valid = [r[0] for r in results2 if r[2] is not None]
            if avg_finishes2:
                ax.plot(race_nums2_valid, avg_finishes2, marker='s', linestyle='--', label=f"{name2} Ср.Финиш")
                all_race_nums.update(race_nums2_valid)

        if not all_race_nums:
             ax.text(0.5, 0.5, "Нет данных о средних финишах", ...)
        else:
            ax.set_xlabel("Номер гонки в сезоне")
            ax.set_ylabel("Средняя финишная позиция") # Меняем подпись Y
            ax.set_title("Сравнение средних финишных позиций команд") # Меняем заголовок
            ax.invert_yaxis()
            ax.legend()
            ax.grid(True, axis='y', linestyle=':')
            if len(all_race_nums) > 0:
                 max_race = max(all_race_nums)
                 if max_race <= 40: ax.set_xticks(sorted(list(all_race_nums)))

        fig.subplots_adjust(bottom=0.20) # Отступ для подписи
        fig.tight_layout()
        self.season_finish_canvas.setVisible(True) # Показываем этот график

    def _draw_overall_team_bar_chart(self, stats1, stats2):
        """Рисует столбчатую диаграмму сравнения карьеры КОМАНД."""
        if not stats1 or not stats2:
            return # График останется скрытым (career_chart_canvas)

        # Ключи для статистики команд
        labels_map = {
            'wins': 'Победы', 'top5': 'Топ-5', 'top10': 'Топ-10',
            'laps_led': 'Круги\nлидерства', 'entries': 'Участий'
        }
        stat_keys = list(labels_map.keys())
        labels = [labels_map[k] for k in stat_keys]

        values1 = [stats1.get(key, 0) for key in stat_keys]
        values2 = [stats2.get(key, 0) for key in stat_keys]

        name1 = stats1.get('team_name', 'Команда 1') if stats1 else 'Команда 1'
        name2 = stats2.get('team_name', 'Команда 2') if stats2 else 'Команда 2'

        x = np.arange(len(labels))
        width = 0.35

        fig = self.career_chart_canvas.figure # Используем тот же canvas
        fig.clear()
        ax = fig.add_subplot(111)

        rects1 = ax.bar(x - width/2, values1, width, label=name1)
        rects2 = ax.bar(x + width/2, values2, width, label=name2)

        ax.set_ylabel('Значение')
        ax.set_title('Сравнение статистики команд за карьеру') # Меняем заголовок
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        ax.bar_label(rects1, padding=3, fmt='%g')
        ax.bar_label(rects2, padding=3, fmt='%g')
        fig.tight_layout()
        self.career_chart_canvas.setVisible(True) # Показываем график

    def _draw_overall_manufacturer_bar_chart(self, stats1, stats2):
        """Рисует столбчатую диаграмму сравнения карьеры ПРОИЗВОДИТЕЛЕЙ."""
        if not stats1 or not stats2:
            return # График career_chart_canvas останется скрытым

        # Ключи для статистики производителей
        labels_map = {
            'wins': 'Победы', 'top5': 'Топ-5', 'top10': 'Топ-10',
            'laps_led': 'Круги\nлидерства', 'entries': 'Участий'
        }
        # Убедимся, что порядок ключей соответствует карте
        stat_keys = ['entries', 'wins', 'top5', 'top10', 'laps_led']
        labels = [labels_map[k] for k in stat_keys]

        values1 = [stats1.get(key, 0) for key in stat_keys]
        values2 = [stats2.get(key, 0) for key in stat_keys]

        name1 = stats1.get('manufacturer_name', 'Произв. 1') # Используем manufacturer_name
        name2 = stats2.get('manufacturer_name', 'Произв. 2')

        x = np.arange(len(labels))
        width = 0.35

        fig = self.career_chart_canvas.figure # Используем тот же canvas
        fig.clear()
        ax = fig.add_subplot(111)

        rects1 = ax.bar(x - width/2, values1, width, label=name1)
        rects2 = ax.bar(x + width/2, values2, width, label=name2)

        ax.set_ylabel('Значение')
        ax.set_title('Сравнение статистики производителей за карьеру') # Меняем заголовок
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        ax.bar_label(rects1, padding=3, fmt='%g')
        ax.bar_label(rects2, padding=3, fmt='%g')
        fig.tight_layout() # Вызываем перед subplots_adjust
        fig.subplots_adjust(bottom=0.15) # Даем место подписям (можно меньше, чем для сезонных)
        self.career_chart_canvas.draw() # Перерисовываем
        self.career_chart_canvas.setVisible(True) # Показываем график

    # Метод для обновления данных, если контекст изменится (пока не используется)
    # def update_context(self, season: int, series: str):
    #     # Может быть полезно для синхронизации с TopBar
    #     if self.season_radio.isChecked():
    #          self.season_combo.setCurrentText(str(season))
    #          self.series_combo.setCurrentText(series)
    #          # Может быть, стоит очистить выбор гонщиков или результаты?
    #          # self.driver1_combo.setCurrentIndex(-1)
    #          # self.driver2_combo.setCurrentIndex(-1)
    #          # self.clear_results()
    #     pass 