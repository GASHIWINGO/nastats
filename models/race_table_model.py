from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class RaceTableModel(QAbstractTableModel):
    def __init__(self, races: list, parent=None):
        super().__init__(parent)
        self._races = races
        self._headers = ["#", "Название гонки", "Трек", "Длина (миль)", "Покрытие"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._races)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        race = self._races[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return race.race_num_in_season
            elif col == 1:
                return race.race_name
            elif col == 2:
                return race.track_name
            elif col == 3:
                return f"{race.track_length:.1f}" if race.track_length else "-"
            elif col == 4:
                return race.track_surface or "-"

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter if col in (0, 3) else Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.ToolTipRole and col in (1, 2):
            return race.race_name if col == 1 else race.track_name

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder):
        if not self._races:
            return

        key_funcs = {
            0: lambda r: r.race_num_in_season,
            1: lambda r: r.race_name.lower(),
            2: lambda r: r.track_name.lower(),
            3: lambda r: r.track_length or 0,
            4: lambda r: r.track_surface or ""
        }

        key_func = key_funcs.get(column, lambda r: "")
        reverse = order == Qt.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        self._races.sort(key=key_func, reverse=reverse)
        self.layoutChanged.emit()
