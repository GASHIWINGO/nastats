from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class DriverTableModel(QAbstractTableModel):
    def __init__(self, drivers: list, parent=None):
        super().__init__(parent)
        self._drivers = drivers
        self._headers = ["Поз.", "Гонщик", "Очки", "Победы", "Гонок"]

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
                return index.row() + 1
            elif col == 1:
                return driver.driver_name
            elif col == 2:
                return driver.total_points
            elif col == 3:
                return driver.total_wins
            elif col == 4:
                return driver.races_entered

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter if col in (0, 2, 3, 4) else Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def driver_id(self, row: int) -> int:
        return self._drivers[row].driver_id
