from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class RaceResultsModel(QAbstractTableModel):
    def __init__(self, results: list, parent=None):
        super().__init__(parent)
        self.results = results
        self.headers = [
            "Поз.", "Старт", "№", "Гонщик", "Команда",
            "Произв.", "Круги", "Вёл", "Статус"
        ]

    def rowCount(self, parent=QModelIndex()):
        return len(self.results)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        result = self.results[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            return [
                result.finish_position,
                result.start_position,
                result.car_number,
                result.driver_name,
                result.team_name,
                result.manufacturer_name,
                result.laps_completed,
                result.laps_led,
                result.status,
            ][col]

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter if col in (0, 1, 2, 6, 7) else Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.ToolTipRole and col in (3, 4, 5):
            return self.data(index, Qt.DisplayRole)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder):
        if not self.results:
            return

        key_funcs = {
            0: lambda r: r.finish_position or 9999,
            1: lambda r: r.start_position or 9999,
            2: lambda r: r.car_number or "",
            3: lambda r: r.driver_name or "",
            4: lambda r: r.team_name or "",
            5: lambda r: r.manufacturer_name or "",
            6: lambda r: r.laps_completed or 0,
            7: lambda r: r.laps_led or 0,
            8: lambda r: r.status or ""
        }

        key_func = key_funcs.get(column, lambda r: "")
        reverse = order == Qt.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        self.results.sort(key=key_func, reverse=reverse)
        self.layoutChanged.emit()
