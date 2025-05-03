from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGridLayout, QGroupBox, QScrollArea, QFrame, QComboBox, QRadioButton,
    QSpacerItem, QSizePolicy, QCompleter
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
        self._drivers_data = []
        self.stats1_cache = None
        self.stats2_cache = None
        self.is_season_mode_cache = False

        # --- Изменение здесь ---
        # Создаем layout отдельно
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)
        self.setLayout(self.layout) # Устанавливаем layout для виджета
        # --- Конец изменения ---

        self.load_initial_data()
        self.setup_selection_ui()
        self.setup_results_ui()

    def load_initial_data(self):
        """Загружает данные, необходимые для инициализации UI (список гонщиков)."""
        self._drivers_data = db_sync.get_all_drivers_list()

    def setup_selection_ui(self):
        # --- Верхняя часть: Выбор режима и контекста ---
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

        # --- Нижняя часть: Выбор гонщиков и кнопка ---
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(10)

        self.driver1_combo = self._create_driver_combo()
        self.driver2_combo = self._create_driver_combo()

        self.compare_button = QPushButton("Сравнить")
        self.compare_button.clicked.connect(self.load_comparison_data)

        selection_layout.addWidget(QLabel("Гонщик 1:"))
        selection_layout.addWidget(self.driver1_combo, 1) # Даем растяжение комбобоксам
        selection_layout.addSpacing(20)
        selection_layout.addWidget(QLabel("Гонщик 2:"))
        selection_layout.addWidget(self.driver2_combo, 1)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(self.compare_button)
        # Убираем addStretch(), чтобы кнопка была ближе

        self.layout.addLayout(selection_layout)

    def _create_driver_combo(self) -> QComboBox:
        """Создает и настраивает QComboBox для выбора гонщика."""
        combo = QComboBox()
        combo.setEditable(True)
        # Убираем стандартный валидатор, чтобы можно было вводить части имени
        combo.lineEdit().setValidator(None)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Позволяем растягиваться
        combo.setMinimumWidth(200) # Задаем минимальную ширину
        combo.setMaxVisibleItems(15) # Ограничиваем высоту выпадающего списка

        # Создаем модель с данными
        model = IdNameItemModel(self._drivers_data, self)
        combo.setModel(model)

        # Настраиваем completer для поиска
        completer = combo.completer()
        completer.setModel(model) # Используем ту же модель
        completer.setCompletionMode(QCompleter.PopupCompletion)
        # Фильтр по содержанию, без учета регистра
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)

        combo.setCurrentIndex(-1) # Сбрасываем выбор, чтобы плейсхолдер был виден
        combo.lineEdit().setPlaceholderText("Начните вводить имя...") # Добавляем плейсхолдер

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
        # Используем QScrollArea на случай большого количества статистики
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame) # Убираем рамку у ScrollArea

        self.results_container = QWidget() # Контейнер для размещения внутри ScrollArea
        self.results_layout = QHBoxLayout(self.results_container) # Горизонтальный layout для двух колонок
        self.results_layout.setSpacing(20)

        # Используем QVBoxLayout, чтобы разместить статистику и графики друг под другом
        self.results_main_layout = QVBoxLayout(self.results_container)
        self.results_main_layout.setSpacing(20)

        # Горизонтальный layout для колонок статистики
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(20)

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

        # --- Добавляем виджет для графика ---
        # Пока один график для сравнения основных показателей
        self.chart_canvas = FigureCanvas(Figure(figsize=(8, 4))) # Размер можно настроить
        self.chart_canvas.setVisible(False) # Скрываем по умолчанию
        # Уменьшаем минимальную высоту, чтобы он не растягивал окно слишком сильно
        self.chart_canvas.setMinimumHeight(200)
        self.results_main_layout.addWidget(self.chart_canvas)

        self.scroll_area.setWidget(self.results_container)
        self.layout.addWidget(self.scroll_area, stretch=1)

    def load_comparison_data(self):
        # --- Перемещаем очистку сюда ---
        self.clear_results() # Очищаем старые результаты ПЕРЕД загрузкой новых

        # Получаем ID из комбобоксов
        idx1 = self.driver1_combo.currentIndex()
        idx2 = self.driver2_combo.currentIndex()

        # print(f"DEBUG: Индексы комбобоксов: idx1={idx1}, idx2={idx2}") # Можно убрать

        if idx1 < 0 or idx2 < 0:
            print("Ошибка: Выберите обоих гонщиков.")
            # self.clear_results() # Уже вызвали выше
            return

        model1: IdNameItemModel = self.driver1_combo.model()
        model2: IdNameItemModel = self.driver2_combo.model()
        driver1_id = model1.getId(idx1)
        driver2_id = model2.getId(idx2)

        # print(f"DEBUG: Полученные ID: driver1_id={driver1_id}, driver2_id={driver2_id}") # Можно убрать

        if not driver1_id or not driver2_id:
             print("Ошибка: Не удалось получить ID гонщиков.")
             # self.clear_results() # Уже вызвали выше
             return

        if driver1_id == driver2_id:
            print("Ошибка: Выберите двух разных гонщиков.")
            # self.clear_results() # Уже вызвали выше
            return

        is_season_mode = self.season_radio.isChecked()
        season = int(self.season_combo.currentText()) if is_season_mode else None
        series = self.series_combo.currentText() if is_season_mode else None
        # print(f"DEBUG: Режим: {'Сезон' if is_season_mode else 'Карьера'}, Сезон: {season}, Серия: {series}") # Можно убрать

        # print("DEBUG: Загрузка данных из db_sync...") # Можно убрать
        if is_season_mode:
            self.stats1_cache = db_sync.get_driver_season_details(driver1_id, season, series)
            self.stats2_cache = db_sync.get_driver_season_details(driver2_id, season, series)
            context_str = f"{series} {season}"
        else:
            self.stats1_cache = db_sync.get_overall_driver_stats(driver1_id)
            self.stats2_cache = db_sync.get_overall_driver_stats(driver2_id)
            context_str = "Карьера"
        # print(f"DEBUG: Данные загружены. Stats1: {bool(self.stats1_cache)}, Stats2: {bool(self.stats2_cache)}") # Можно убрать
        self.is_season_mode_cache = is_season_mode

        # Отображаем статистику и графики
        # Теперь display_comparison не будет сбрасывать кэш перед draw_comparison_chart
        self.display_comparison(self.stats1_cache, self.stats2_cache, context_str)
        self.draw_comparison_chart()

    def display_comparison(self, stats1, stats2, context_str: str):
        # self.clear_results() # <--- Убираем вызов отсюда

        # Устанавливаем заголовки
        title1 = self._get_title(stats1, "Гонщик 1", context_str)
        title2 = self._get_title(stats2, "Гонщик 2", context_str)
        self.driver1_stats_group.setTitle(title1)
        self.driver2_stats_group.setTitle(title2)

        # Заполняем сетки статистики
        self._populate_comparison_grids(stats1, stats2)

    def _get_title(self, stats: dict | None, default_prefix: str, context_str: str) -> str:
        """Формирует заголовок для группы статистики."""
        if not stats:
            return f"{default_prefix} (не найден)"
        name = stats.get('driver_name', f"{default_prefix} ID {stats.get('driver_id', '?')}")
        return f"{name} — {context_str}"

    def _populate_comparison_grids(self, stats1: dict | None, stats2: dict | None):
        """Заполняет обе сетки (QGridLayout) статистикой, выделяя лучшие значения."""

        stat_map = {
            "races": ("Гонки", True), # True - больше = лучше
            "wins": ("Победы", True),
            "top5": ("Топ-5", True),
            "top10": ("Топ-10", True),
            "laps_led": ("Кругов в лидерах", True),
            "laps_completed": ("Завершено кругов", True),
            "avg_start": ("Средний старт", False), # False - меньше = лучше
            "avg_finish": ("Средний финиш", False), # False - меньше = лучше
            "points": ("Очки", True)
        }
        if stats1 and 'entries' in stats1 or stats2 and 'entries' in stats2: # Для команд/производителей
             stat_map['entries'] = ("Участий", True)

        # Цвета для выделения
        default_palette = self.palette() # Получаем стандартную палитру
        highlight_color = QColor(Qt.darkGreen).lighter(150) # Зеленоватый для лучшего
        default_text_color = default_palette.color(QPalette.Text)

        row = 0
        for key, (label_text, more_is_better) in stat_map.items():

            val1 = stats1.get(key) if stats1 else None
            val2 = stats2.get(key) if stats2 else None

            # Пропускаем строку, если данных нет у обоих
            if val1 is None and val2 is None:
                continue

            val1_str = self._format_value(val1)
            val2_str = self._format_value(val2)

            is_val1_better = False
            is_val2_better = False

            # Логика сравнения
            if val1 is not None and val2 is not None:
                try:
                    num_val1 = float(val1)
                    num_val2 = float(val2)
                    if more_is_better:
                        is_val1_better = num_val1 > num_val2
                        is_val2_better = num_val2 > num_val1
                    else: # Меньше - лучше (для средних позиций)
                        is_val1_better = num_val1 < num_val2
                        is_val2_better = num_val2 < num_val1
                except (ValueError, TypeError):
                    pass # Не сравниваем, если не числа
            elif val1 is not None: # Лучше, если у второго нет данных
                 is_val1_better = True
            elif val2 is not None: # Лучше, если у первого нет данных
                 is_val2_better = True

            # Добавляем метку (один раз, выровненную по центру между колонками)
            # Но проще добавить её в обе колонки
            label1 = QLabel(label_text + ":")
            label1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value1_label = QLabel(val1_str)
            value1_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value1_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            label2 = QLabel(label_text + ":")
            label2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value2_label = QLabel(val2_str)
            value2_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value2_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            # Применяем стиль к ЛУЧШЕМУ значению
            if is_val1_better:
                value1_label.setStyleSheet(f"font-weight: bold; color: {highlight_color.name()};")
            if is_val2_better:
                value2_label.setStyleSheet(f"font-weight: bold; color: {highlight_color.name()};")

            self.driver1_grid.addWidget(label1, row, 0)
            self.driver1_grid.addWidget(value1_label, row, 1)
            self.driver2_grid.addWidget(label2, row, 0)
            self.driver2_grid.addWidget(value2_label, row, 1)

            row += 1

        # Обработка случая, если вообще не было данных для сравнения
        if row == 0:
            no_data_label1 = QLabel("Нет данных\nдля сравнения.")
            no_data_label1.setAlignment(Qt.AlignCenter)
            no_data_label1.setStyleSheet("color: gray;")
            self.driver1_grid.addWidget(no_data_label1, 0, 0, 1, 2)

            no_data_label2 = QLabel("Нет данных\nдля сравнения.")
            no_data_label2.setAlignment(Qt.AlignCenter)
            no_data_label2.setStyleSheet("color: gray;")
            self.driver2_grid.addWidget(no_data_label2, 0, 0, 1, 2)

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

        # Очищаем график
        self.chart_canvas.figure.clear()
        self.chart_canvas.draw()
        self.chart_canvas.setVisible(False)

        # --- Сбрасываем кэш здесь ---
        self.stats1_cache = None
        self.stats2_cache = None
        # Сброс режима не обязателен, но можно оставить для консистентности
        # self.is_season_mode_cache = False

    def draw_comparison_chart(self):
        """Рисует график сравнения в зависимости от режима."""
        if self.is_season_mode_cache:
            # TODO: Реализовать графики для сезона (например, линии финишей/очков)
            self.chart_canvas.setVisible(False) # Пока скрываем для сезона
            print("Графики для сезона пока не реализованы.")
        else:
            # Рисуем бар-чарт для общей статистики
            self._draw_overall_bar_chart(self.stats1_cache, self.stats2_cache)

    def _draw_overall_bar_chart(self, stats1, stats2):
        """Рисует столбчатую диаграмму сравнения основных показателей карьеры."""
        # print(f"DEBUG: Попытка отрисовки бар-чарта. Stats1: {bool(stats1)}, Stats2: {bool(stats2)}") # Можно убрать
        if not stats1 or not stats2:
             # print("DEBUG: Скрытие графика, т.к. отсутствуют данные.") # Можно убрать
             self.chart_canvas.setVisible(False)
             self.chart_canvas.draw()
             return

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

        fig = self.chart_canvas.figure
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
        self.chart_canvas.draw()
        self.chart_canvas.setVisible(True)
        # print("DEBUG: График отрисован и показан.") # Можно убрать

        # except Exception as e:
        #     print(f"!!! Ошибка при отрисовке бар-чарта: {e}")
        #     import traceback
        #     traceback.print_exc()
        #     try:
        #          self.chart_canvas.setVisible(False)
        #          self.chart_canvas.draw()
        #     except Exception as hide_e:
        #          print(f"!!! Дополнительная ошибка при попытке скрыть canvas: {hide_e}")

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