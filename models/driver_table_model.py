from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class DriverTableModel(QAbstractTableModel):
    def __init__(self, drivers: list, parent=None):
        super().__init__(parent)
        self._drivers = drivers
        self._headers = ["Гонщик", "Очки", "Победы", "Участий"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._drivers)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        driver = self._drivers[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return driver.driver_name
            elif col == 1:
                return driver.total_points
            elif col == 2:
                return driver.total_wins
            elif col == 3:
                return driver.races_entered

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter  # ⬅️ всё выравниваем по центру

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder):
        if not self._drivers:
            return

        key_funcs = {
            0: lambda d: d.driver_name.lower(),
            1: lambda d: d.total_points or 0,
            2: lambda d: d.total_wins or 0,
            3: lambda d: d.races_entered or 0
        }

        key_func = key_funcs.get(column, lambda d: 0)
        reverse = order == Qt.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        self._drivers.sort(key=key_func, reverse=reverse)
        self.layoutChanged.emit()

    def driver_id(self, row: int) -> int:
        return self._drivers[row].driver_id
