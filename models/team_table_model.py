from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class TeamTableModel(QAbstractTableModel):
    def __init__(self, teams: list, parent=None):
        super().__init__(parent)
        self._teams = teams
        self._headers = ["Поз.", "Команда", "Очки", "Победы", "Топ-5", "Участий"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._teams)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        team = self._teams[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return index.row() + 1
            elif col == 1: return team.team_name
            elif col == 2: return team.total_points
            elif col == 3: return team.total_wins
            elif col == 4: return team.total_top5
            elif col == 5: return team.total_entries

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter if col != 1 else Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder):
        if not self._teams:
            return

        key_funcs = {
            1: lambda t: t.team_name.lower(),
            2: lambda t: t.total_points or 0,
            3: lambda t: t.total_wins or 0,
            4: lambda t: t.total_top5 or 0,
            5: lambda t: t.total_entries or 0
        }

        key_func = key_funcs.get(column, lambda t: 0)
        reverse = order == Qt.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        self._teams.sort(key=key_func, reverse=reverse)
        self.layoutChanged.emit()

    def team_id(self, row: int) -> int:
        return self._teams[row].team_id
