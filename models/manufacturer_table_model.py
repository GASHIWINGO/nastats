from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class ManufacturerTableModel(QAbstractTableModel):
    def __init__(self, manufacturers: list, parent=None):
        super().__init__(parent)
        self._manufacturers = manufacturers
        self._headers = ["Производитель", "Победы", "Топ-5", "Топ-10", "Участий"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._manufacturers)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        m = self._manufacturers[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return m.manufacturer_name
            elif col == 1: return m.wins
            elif col == 2: return m.top5
            elif col == 3: return m.top10
            elif col == 4: return m.entries

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder):
        if not self._manufacturers:
            return

        key_funcs = {
            0: lambda m: m.manufacturer_name.lower(),
            1: lambda m: m.wins or 0,
            2: lambda m: m.top5 or 0,
            3: lambda m: m.top10 or 0,
            4: lambda m: m.entries or 0
        }

        key_func = key_funcs.get(column, lambda m: 0)
        reverse = order == Qt.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        self._manufacturers.sort(key=key_func, reverse=reverse)
        self.layoutChanged.emit()
