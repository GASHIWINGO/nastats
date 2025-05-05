from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGridLayout, QGroupBox, QScrollArea, QFrame, QComboBox, QRadioButton,
    QSpacerItem, QSizePolicy, QCompleter, QButtonGroup
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QThread, QObject, Signal
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

# Worker для фоновых задач БД
class DbWorker(QObject):
    """Выполняет запросы к БД в фоновом потоке."""
    # Сигнал с результатом: словарь со статистикой и результатами сезона
    result_ready = Signal(dict)
    # Сигнал ошибки
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self, entity_type, is_season_mode, id1, id2, season, series):
        """Запускает загрузку данных для сравнения."""
        print(f"DEBUG [DbWorker]: Starting task - Type: {entity_type}, Season Mode: {is_season_mode}, ID1: {id1}, ID2: {id2}, Season: {season}, Series: {series}")
        try:
            results = {
                'stats1': None,
                'stats2': None,
                'season_results1': None,
                'season_results2': None
            }
            series_id = None
            if is_season_mode:
                # Получаем series_id только один раз
                with db_sync.get_db_session() as session:
                    series_id = db_sync.get_series_id_by_name(session, series)
                if not series_id:
                    raise ValueError(f"Серия '{series}' не найдена в БД.")

            if entity_type == "driver":
                if is_season_mode:
                    results['stats1'] = db_sync.get_driver_season_details(id1, season, series)
                    results['stats2'] = db_sync.get_driver_season_details(id2, season, series)
                    results['season_results1'] = db_sync.get_driver_race_results_for_season(id1, season, series_id)
                    results['season_results2'] = db_sync.get_driver_race_results_for_season(id2, season, series_id)
                else:
                    results['stats1'] = db_sync.get_overall_driver_stats(id1)
                    results['stats2'] = db_sync.get_overall_driver_stats(id2)
            elif entity_type == "team":
                if is_season_mode:
                    results['stats1'] = db_sync.get_team_season_details(id1, season, series)
                    results['stats2'] = db_sync.get_team_season_details(id2, season, series)
                    results['season_results1'] = db_sync.get_team_race_results_for_season(id1, season, series_id)
                    results['season_results2'] = db_sync.get_team_race_results_for_season(id2, season, series_id)
                else:
                    results['stats1'] = db_sync.get_overall_team_stats(id1)
                    results['stats2'] = db_sync.get_overall_team_stats(id2)
            elif entity_type == "manufacturer":
                if is_season_mode:
                    # Получаем статистику ВСЕХ производителей за сезон
                    all_manu_stats = db_sync.get_manufacturer_season_stats(season, series)
                    # Находим нужных нам по ID
                    results['stats1'] = next((m for m in all_manu_stats if m.get('manufacturer_id') == id1), None)
                    results['stats2'] = next((m for m in all_manu_stats if m.get('manufacturer_id') == id2), None)
                    # Сезонных графиков для производителей пока нет
                else:
                    results['stats1'] = db_sync.get_overall_manufacturer_stats(id1)
                    results['stats2'] = db_sync.get_overall_manufacturer_stats(id2)

            print(f"DEBUG [DbWorker]: Task finished successfully. Emitting result_ready.")
            self.result_ready.emit(results)

        except Exception as e:
            error_msg = f"Ошибка при фоновой загрузке данных: {e}"
            print(f"ERROR [DbWorker]: {error_msg}")
            import traceback
            traceback.print_exc() # Выводим полный traceback в консоль для отладки
            self.error_occurred.emit(error_msg)

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
        self.db_thread = None # Для хранения потока
        self.db_worker = None # Для хранения worker'а
        self.grid1_labels = {} # Словарь для хранения меток первой сетки {key: (label_widget, value_widget)}
        self.grid2_labels = {} # Словарь для хранения меток второй сетки

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

    def _determine_stat_map(self):
        """Возвращает карту статистики в зависимости от текущего типа сущности."""
        if self.current_entity_type == "driver":
            return {
                "races": ("Гонки", True), "wins": ("Победы", True), "top5": ("Топ-5", True),
                "top10": ("Топ-10", True), "laps_led": ("Кругов в лидерах", True),
                "laps_completed": ("Завершено кругов", True), "avg_start": ("Средний старт", False),
                "avg_finish": ("Средний финиш", False), "points": ("Очки", True)
            }
        elif self.current_entity_type == "team":
            return {
                "entries": ("Участий", True), "wins": ("Победы", True), "top5": ("Топ-5", True),
                "top10": ("Топ-10", True), "laps_led": ("Кругов в лидерах", True),
                "laps_completed": ("Завершено кругов", True), "avg_start": ("Средний старт (команды)", False),
                "avg_finish": ("Средний финиш (команды)", False), "points": ("Очки (команды)", True)
            }
        elif self.current_entity_type == "manufacturer":
            return {
                "entries": ("Участий", True),
                "wins": ("Победы", True),
                "top5": ("Топ-5", True),
                "top10": ("Топ-10", True),
                "laps_led": ("Круги\nлидерства", True)
            }
        else:
            return {} # По умолчанию пусто

    def setup_results_ui(self):
        # 1. Создаем QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True) # Важно, чтобы внутренний виджет мог изменять размер
        self.scroll_area.setFrameShape(QFrame.NoFrame) # Убираем рамку

        # 2. Создаем виджет-контейнер, который будет ВНУТРИ QScrollArea
        self.results_container = QWidget()
        # 3. Создаем ГЛАВНЫЙ ВЕРТИКАЛЬНЫЙ layout для этого контейнера
        self.results_main_layout = QVBoxLayout(self.results_container)
        self.results_main_layout.setContentsMargins(5, 5, 5, 5) # Небольшие отступы внутри контейнера
        self.results_main_layout.setSpacing(20)
        # 4. Устанавливаем контейнер как виджет для QScrollArea
        self.scroll_area.setWidget(self.results_container)

        # --- Статистика ---
        # 5. Создаем ГОРИЗОНТАЛЬНЫЙ layout для размещения двух групп статистики
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(15)

        # 6. Создаем GroupBox'ы БЕЗ явного родителя
        self.driver1_stats_group = QGroupBox("Сущность 1")
        self.driver1_grid = QGridLayout(self.driver1_stats_group) # Grid является layout'ом для этой группы
        self.driver1_stats_group.setMinimumWidth(350)

        self.driver2_stats_group = QGroupBox("Сущность 2")
        self.driver2_grid = QGridLayout(self.driver2_stats_group) # Grid является layout'ом для этой группы
        self.driver2_stats_group.setMinimumWidth(350)

        # 7. Предсоздаем метки и добавляем их в grid'ы (как в прошлый раз)
        possible_keys_map = { # Определяем статически
            "races": ("Гонки", True), "wins": ("Победы", True), "top5": ("Топ-5", True),
            "top10": ("Топ-10", True), "laps_led": ("Кругов в лидерах", True),
            "laps_completed": ("Завершено кругов", True), "avg_start": ("Средний старт", False),
            "avg_finish": ("Средний финиш", False), "points": ("Очки", True),
            "entries": ("Участий", True)
        }
        self.grid1_labels.clear()
        self.grid2_labels.clear()
        row = 0
        for key, (label_text, _) in possible_keys_map.items():
            clean_label_text = label_text.replace("\n", " ").replace("(команды)", "").strip() + ":"
            # Метки для первой сетки
            label1_widget = QLabel(clean_label_text); label1_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter); label1_widget.setVisible(False)
            value1_widget = QLabel("-"); value1_widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); value1_widget.setTextInteractionFlags(Qt.TextSelectableByMouse); value1_widget.setVisible(False)
            self.driver1_grid.addWidget(label1_widget, row, 0); self.driver1_grid.addWidget(value1_widget, row, 1)
            self.grid1_labels[key] = (label1_widget, value1_widget)
            # Метки для второй сетки
            label2_widget = QLabel(clean_label_text); label2_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter); label2_widget.setVisible(False)
            value2_widget = QLabel("-"); value2_widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); value2_widget.setTextInteractionFlags(Qt.TextSelectableByMouse); value2_widget.setVisible(False)
            self.driver2_grid.addWidget(label2_widget, row, 0); self.driver2_grid.addWidget(value2_widget, row, 1)
            self.grid2_labels[key] = (label2_widget, value2_widget)
            row += 1

        # 8. Добавляем GroupBox'ы в горизонтальный stats_layout
        self.stats_layout.addWidget(self.driver1_stats_group)
        self.stats_layout.addWidget(self.driver2_stats_group)
        self.stats_layout.addStretch()

        # 9. Добавляем stats_layout (с группами внутри) в results_main_layout контейнера
        self.results_main_layout.addLayout(self.stats_layout)

        # --- Графики ---
        # 10. Создаем графики и добавляем их в results_main_layout контейнера
        self.career_chart_canvas = FigureCanvas(Figure(figsize=(8, 4)))
        self.career_chart_canvas.setVisible(False); self.career_chart_canvas.setMinimumHeight(250)
        self.results_main_layout.addWidget(self.career_chart_canvas)

        self.season_finish_canvas = FigureCanvas(Figure(figsize=(8, 4)))
        self.season_finish_canvas.setVisible(False); self.season_finish_canvas.setMinimumHeight(250)
        self.results_main_layout.addWidget(self.season_finish_canvas)

        self.season_points_canvas = FigureCanvas(Figure(figsize=(8, 4)))
        self.season_points_canvas.setVisible(False); self.season_points_canvas.setMinimumHeight(250)
        self.results_main_layout.addWidget(self.season_points_canvas)

        # 11. Наконец, добавляем QScrollArea (со всем содержимым) в ОСНОВНОЙ layout виджета CompareView
        self.layout.addWidget(self.scroll_area, stretch=1)

    def load_comparison_data(self):
        """Запускает загрузку данных сравнения в фоновом потоке."""
        # --- 1. Проверки и получение параметров (как раньше) ---
        self.clear_results()
        idx1 = self.entity1_combo.currentIndex()
        idx2 = self.entity2_combo.currentIndex()

        if idx1 < 0 or idx2 < 0:
            # Можно показать сообщение пользователю через QMessageBox
            print(f"Ошибка: Выберите обе(их) {self.current_entity_type}.")
            return

        model1: IdNameItemModel = self.entity1_combo.model()
        model2: IdNameItemModel = self.entity2_combo.model()
        id1 = model1.getId(idx1)
        id2 = model2.getId(idx2)

        if not id1 or not id2 or id1 == id2:
            print(f"Ошибка: Выберите две разные сущности ({self.current_entity_type}).")
            # Можно показать сообщение пользователю
            return

        is_season_mode = self.season_radio.isChecked()
        season = int(self.season_combo.currentText()) if is_season_mode else None
        series = self.series_combo.currentText() if is_season_mode else None
        self.is_season_mode_cache = is_season_mode # Кэшируем режим для отрисовки графиков

        # --- 2. Настройка и запуск фоновой задачи ---
        # Если предыдущий поток еще работает, нужно его остановить (или не запускать новый)
        # Простой вариант: просто не запускать новый, если кнопка неактивна
        if not self.compare_button.isEnabled():
            print("INFO: Загрузка данных уже выполняется.")
            return

        self.compare_button.setEnabled(False)
        self.compare_button.setText("Загрузка...") # Индикатор

        # Создаем поток и worker'а
        self.db_thread = QThread()
        self.db_worker = DbWorker() # Создаем экземпляр нашего worker'а
        self.db_worker.moveToThread(self.db_thread) # Перемещаем worker'а в поток

        # Подключаем сигналы worker'а к слотам CompareView
        self.db_worker.result_ready.connect(self._on_comparison_data_ready)
        self.db_worker.error_occurred.connect(self._on_db_error)

        # Подключаем сигналы потока для запуска и очистки
        # Запускаем run worker'а, когда поток стартует
        self.db_thread.started.connect(lambda: self.db_worker.run(
            self.current_entity_type, is_season_mode, id1, id2, season, series
        ))
        # Завершаем поток, когда worker закончил (успешно или с ошибкой)
        self.db_worker.result_ready.connect(self.db_thread.quit)
        self.db_worker.error_occurred.connect(self.db_thread.quit)
        # Удаляем worker'а и поток после завершения потока
        self.db_thread.finished.connect(self.db_worker.deleteLater)
        self.db_thread.finished.connect(self.db_thread.deleteLater)
        # Сбрасываем ссылки на поток и worker'а после удаления
        self.db_thread.finished.connect(self._reset_thread_worker)

        print("DEBUG: Запуск фонового потока для загрузки данных...")
        self.db_thread.start() # Запускаем поток

    def _on_comparison_data_ready(self, results_dict):
        """Слот для обработки результатов, полученных из фонового потока."""
        print("DEBUG: Получены результаты из фонового потока.")
        # Восстанавливаем состояние кнопки
        self.compare_button.setEnabled(True)
        self.compare_button.setText("Сравнить")

        # Обновляем кэши в основном потоке
        self.stats1_cache = results_dict.get('stats1')
        self.stats2_cache = results_dict.get('stats2')
        self.season_results1_cache = results_dict.get('season_results1')
        self.season_results2_cache = results_dict.get('season_results2')

        # Формируем контекстную строку (как раньше)
        context_str = ""
        if self.is_season_mode_cache:
            season = int(self.season_combo.currentText())
            series = self.series_combo.currentText()
            context_str = f"{series} {season}"
        else:
            context_str = "Карьера"

        # Обновляем UI (эти методы теперь работают с кэшами)
        self.display_comparison(self.stats1_cache, self.stats2_cache, context_str)
        self.draw_comparison_chart()
        print("DEBUG: UI обновлен результатами.")

    def _on_db_error(self, error_message):
        """Слот для обработки ошибок из фонового потока."""
        print(f"ERROR: Ошибка в фоновом потоке: {error_message}")
        # Восстанавливаем состояние кнопки
        self.compare_button.setEnabled(True)
        self.compare_button.setText("Сравнить")
        # Опционально: показать сообщение пользователю
        # QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось загрузить данные:\n{error_message}")
        # Очищаем результаты, если произошла ошибка
        self.clear_results()

    def _reset_thread_worker(self):
        """Сбрасывает ссылки на поток и worker после их удаления."""
        print("DEBUG: Очистка ссылок на поток и worker.")
        self.db_thread = None
        self.db_worker = None

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
        """Заполняет обе сетки (QGridLayout) статистикой, обновляя существующие QLabel."""
        # Отладочный вывод
        print("-" * 20)
        print(f"DEBUG [populate_grids] Updating grids. stats1: {bool(stats1)}, stats2: {bool(stats2)}")
        print("-" * 20)

        # Получаем актуальную карту для текущего типа сущности
        stat_map = self._determine_stat_map()
        if not stat_map:
            print("WARN [populate_grids] No stat map determined for current entity type.")
            # Скрываем все метки на всякий случай
            for key in self.grid1_labels:
                label1, value1 = self.grid1_labels[key]
                label2, value2 = self.grid2_labels[key]
                label1.setVisible(False)
                value1.setVisible(False)
                label2.setVisible(False)
                value2.setVisible(False)
            return

        # Стили
        default_style = "" # Обычный стиль по умолчанию (можно взять из темы, но пока пустой)
        highlight_color = QColor(Qt.darkGreen).lighter(150)
        highlight_style = f"font-weight: bold; color: {highlight_color.name()};"

        any_widget_shown = False
        # Проходим по всем возможным меткам, которые мы создали
        for key, (label1_widget, value1_widget) in self.grid1_labels.items():
            label2_widget, value2_widget = self.grid2_labels[key]

            # Проверяем, есть ли этот ключ в ТЕКУЩЕЙ карте статистики
            if key in stat_map:
                label_text, more_is_better = stat_map[key]
                # Корректируем текст основной метки, если нужно (например, для команд)
                clean_label_text = label_text.replace("\n", " ").replace("(команды)", "").strip() + ":"
                label1_widget.setText(clean_label_text)
                label2_widget.setText(clean_label_text)

                val1 = stats1.get(key) if stats1 else None
                val2 = stats2.get(key) if stats2 else None

                # Показываем строку, только если есть данные хотя бы у одного
                if val1 is not None or val2 is not None:
                    val1_str = self._format_value(val1)
                    val2_str = self._format_value(val2)
                    is_val1_better, is_val2_better = False, False
                    if val1 is not None and val2 is not None:
                        try:
                            num_val1, num_val2 = float(val1), float(val2)
                            if more_is_better: is_val1_better, is_val2_better = num_val1 > num_val2, num_val2 > num_val1
                            else: is_val1_better, is_val2_better = num_val1 < num_val2, num_val2 < num_val1
                        except (ValueError, TypeError): pass
                    elif val1 is not None: is_val1_better = True
                    elif val2 is not None: is_val2_better = True

                    # Обновляем значения и стили
                    value1_widget.setText(val1_str)
                    value1_widget.setStyleSheet(highlight_style if is_val1_better else default_style)
                    value2_widget.setText(val2_str)
                    value2_widget.setStyleSheet(highlight_style if is_val2_better else default_style)

                    # Показываем виджеты для этой строки
                    label1_widget.setVisible(True)
                    value1_widget.setVisible(True)
                    label2_widget.setVisible(True)
                    value2_widget.setVisible(True)
                    any_widget_shown = True
                    # print(f"DEBUG [populate_grids] Updated widgets for key '{key}'")
                else:
                    # Если данных нет у обоих, скрываем строку
                    label1_widget.setVisible(False)
                    value1_widget.setVisible(False)
                    label2_widget.setVisible(False)
                    value2_widget.setVisible(False)
                    # print(f"DEBUG [populate_grids] Hiding widgets for key '{key}' (both None)")
            else:
                # Если ключ неактуален для текущего типа сущности, скрываем
                label1_widget.setVisible(False)
                value1_widget.setVisible(False)
                label2_widget.setVisible(False)
                value2_widget.setVisible(False)
                # print(f"DEBUG [populate_grids] Hiding widgets for key '{key}' (not in current stat map)")


        # Обработка случая, если вообще не было данных для сравнения
        if not any_widget_shown:
            print("WARN [populate_grids] No comparison data found to display in grids.")
            # Можно добавить одну метку "Нет данных", если нужно
            # (но текущая логика просто скроет все строки)
        else:
            print(f"DEBUG [populate_grids] Finished updating grids.")

        # --- Активация layout'ов больше не нужна, т.к. структура не меняется ---
        # self.driver1_grid.activate() # Можно убрать
        # self.driver2_grid.activate() # Можно убрать

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
        print("DEBUG: Clearing results...")
        # --- Сброс сеток статистики ---
        self.driver1_stats_group.setTitle("Сущность 1") # Сброс заголовка
        self.driver2_stats_group.setTitle("Сущность 2") # Сброс заголовка

        # Сбрасываем текст, стиль и видимость для всех предсозданных меток
        default_style = ""
        for key in self.grid1_labels:
            label1, value1 = self.grid1_labels[key]
            label2, value2 = self.grid2_labels[key]

            value1.setText("-")
            value1.setStyleSheet(default_style)
            label1.setVisible(False) # Скрываем
            value1.setVisible(False)

            value2.setText("-")
            value2.setStyleSheet(default_style)
            label2.setVisible(False) # Скрываем
            value2.setVisible(False)
        # --- Конец сброса сеток ---

        # Очищаем и скрываем ВСЕ графики (как и раньше)
        for canvas in [self.career_chart_canvas, self.season_finish_canvas, self.season_points_canvas]:
            # Используем ax.cla() для оптимизации (это будет в следующем шаге, пока оставим fig.clear())
            # canvas.figure.gca().cla() # Очищаем оси
            canvas.figure.clear() # Пока оставляем так
            canvas.draw()
            canvas.setVisible(False)

        # Сбрасываем ВСЕ кэши (как и раньше)
        self.stats1_cache = None; self.stats2_cache = None
        self.season_results1_cache = None; self.season_results2_cache = None
        print("DEBUG: Results cleared.")

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
        rects2 = ax.bar(x + width/2, values2, width, label=name2, color='deeppink')
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
                ax.plot(race_nums2_valid, finishes2, marker='s', linestyle='--', label=f"{name2} Финиш", color='deeppink')
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
                ax.plot(race_nums2_valid, points2, marker='s', linestyle='--', label=f"{name2} Очки", color='deeppink')
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
        fig.subplots_adjust(bottom=0.20) # <--- Изменено на 0.20 и вызвано ПОСЛЕ tight_layout
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
                ax.plot(race_nums2_valid, avg_finishes2, marker='s', linestyle='--', label=f"{name2} Ср.Финиш", color='deeppink')
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
        rects2 = ax.bar(x + width/2, values2, width, label=name2, color='deeppink')

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

        fig = self.career_chart_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        rects1 = ax.bar(x - width/2, values1, width, label=name1)
        rects2 = ax.bar(x + width/2, values2, width, label=name2, color='deeppink')

        ax.set_ylabel('Значение')
        ax.set_title('Сравнение статистики производителей за карьеру')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        ax.bar_label(rects1, padding=3, fmt='%g')
        ax.bar_label(rects2, padding=3, fmt='%g')
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.15) # Даем место подписям (можно меньше, чем для сезонных)
        self.career_chart_canvas.draw()
        self.career_chart_canvas.setVisible(True)

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