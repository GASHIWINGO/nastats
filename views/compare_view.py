from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGridLayout, QGroupBox, QScrollArea, QFrame, QComboBox, QRadioButton,
    QSpacerItem, QSizePolicy, QCompleter
)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
import db_sync

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
        self._drivers_data = [] # Кэш списка гонщиков

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)

        self.load_initial_data() # Загружаем список гонщиков
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

        self.driver1_stats_group = QGroupBox("Гонщик 1")
        self.driver1_grid = QGridLayout(self.driver1_stats_group)
        self.driver1_stats_group.setMinimumWidth(350) # Задаем мин. ширину для групп

        self.driver2_stats_group = QGroupBox("Гонщик 2")
        self.driver2_grid = QGridLayout(self.driver2_stats_group)
        self.driver2_stats_group.setMinimumWidth(350)

        self.results_layout.addWidget(self.driver1_stats_group)
        self.results_layout.addWidget(self.driver2_stats_group)
        self.results_layout.addStretch() # Добавляем растяжение в конце

        self.scroll_area.setWidget(self.results_container)
        self.layout.addWidget(self.scroll_area, stretch=1) # ScrollArea занимает оставшееся место


    def load_comparison_data(self):
        # Получаем ID из комбобоксов
        idx1 = self.driver1_combo.currentIndex()
        idx2 = self.driver2_combo.currentIndex()

        if idx1 < 0 or idx2 < 0:
            # TODO: Показать сообщение об ошибке пользователю
            print("Ошибка: Выберите обоих гонщиков.")
            self.clear_results()
            return

        # Используем модель для получения ID
        model1: IdNameItemModel = self.driver1_combo.model()
        model2: IdNameItemModel = self.driver2_combo.model()

        driver1_id = model1.getId(idx1)
        driver2_id = model2.getId(idx2)

        if not driver1_id or not driver2_id:
             # TODO: Показать сообщение об ошибке пользователю
             print("Ошибка: Не удалось получить ID гонщиков.")
             self.clear_results()
             return

        if driver1_id == driver2_id:
            # TODO: Показать сообщение об ошибке пользователю
            print("Ошибка: Выберите двух разных гонщиков.")
            self.clear_results()
            return

        # Определяем режим и контекст
        is_season_mode = self.season_radio.isChecked()
        season = int(self.season_combo.currentText()) if is_season_mode else None
        series = self.series_combo.currentText() if is_season_mode else None

        # Загружаем данные в зависимости от режима
        if is_season_mode:
            stats1 = db_sync.get_driver_season_details(driver1_id, season, series)
            stats2 = db_sync.get_driver_season_details(driver2_id, season, series)
            context_str = f"{series} {season}"
        else:
            stats1 = db_sync.get_overall_driver_stats(driver1_id)
            stats2 = db_sync.get_overall_driver_stats(driver2_id)
            context_str = "Карьера"

        self.display_comparison(stats1, stats2, context_str)

    def display_comparison(self, stats1, stats2, context_str: str):
        self.clear_results() # Очищаем предыдущие результаты

        title1 = "Гонщик 1 (не найден)"
        if stats1:
            # Используем имя из статистики, оно должно там быть
            name1 = stats1.get('driver_name', f"Гонщик ID {stats1.get('driver_id', '?')}")
            title1 = f"{name1} — {context_str}"
            self._populate_grid(self.driver1_grid, stats1)
        self.driver1_stats_group.setTitle(title1)

        title2 = "Гонщик 2 (не найден)"
        if stats2:
            name2 = stats2.get('driver_name', f"Гонщик ID {stats2.get('driver_id', '?')}")
            title2 = f"{name2} — {context_str}"
            self._populate_grid(self.driver2_grid, stats2)
        self.driver2_stats_group.setTitle(title2)

    def _populate_grid(self, grid_layout: QGridLayout, stats: dict):
        """Заполняет QGridLayout статистикой."""
        if not stats or stats.get("races", 0) == 0 and stats.get("entries", 0) == 0: # Проверяем наличие данных
            label = QLabel("Данные не найдены\nдля выбранного контекста.")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: gray;")
            grid_layout.addWidget(label, 0, 0, 1, 2) # Span across 2 columns
            return

        # Статистика для отображения (ключ словаря -> отображаемый текст)
        stat_map = {
            "races": "Гонки",
            "wins": "Победы",
            "top5": "Топ-5",
            "top10": "Топ-10",
            "laps_led": "Кругов в лидерах",
            "laps_completed": "Завершено кругов",
            "avg_start": "Средний старт",
            "avg_finish": "Средний финиш",
            "points": "Очки" # Убрали уточнение, т.к. контекст в заголовке
        }
        # Добавляем 'entries' для команд/производителей, если они есть
        if 'entries' in stats:
            stat_map['entries'] = "Участий"
            # Можно переупорядочить словарь, если нужно

        row = 0
        for key, label_text in stat_map.items():
            # Пропускаем ключ, если его нет в словаре статистики
            if key not in stats: continue

            value = stats.get(key)
            # Форматируем значение
            if isinstance(value, float):
                value_str = f"{value:.1f}" # Округляем float до 1 знака
            elif value is not None:
                value_str = str(value)
            else:
                value_str = "-" # Отображаем прочерк для None

            label = QLabel(label_text + ":")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # label.setStyleSheet("font-weight: bold;")

            value_label = QLabel(value_str)
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse) # Позволяем копировать значение

            grid_layout.addWidget(label, row, 0)
            grid_layout.addWidget(value_label, row, 1)
            row += 1

    def clear_results(self):
        """Очищает область отображения результатов."""
        self.driver1_stats_group.setTitle("Гонщик 1")
        self.driver2_stats_group.setTitle("Гонщик 2")
        # Удаляем виджеты из GridLayout
        for grid in [self.driver1_grid, self.driver2_grid]:
            while grid.count():
                child = grid.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

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