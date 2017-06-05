from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex


class LrsErrorModel(QAbstractTableModel):
    TYPE_COL = 0
    ROUTE_COL = 1
    MEASURE_COL = 2
    MESSAGE_COL = 3  # currently not used

    headerLabels = {
        TYPE_COL: 'Type',
        ROUTE_COL: 'Route',
        MEASURE_COL: 'Measure',
        MESSAGE_COL: 'Message',
    }

    def __init__(self):
        super(LrsErrorModel, self).__init__()
        self.errors = []

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if not Qt or role != Qt.DisplayRole: return None
        if orientation == Qt.Horizontal:
            if section in self.headerLabels:
                return self.headerLabels[section]
            else:
                return ""
        else:
            return "%s" % section

    def rowCount(self, index):
        return len(self.errors)

    def columnCount(self, index):
        return 3

    def data(self, index, role):
        if role != Qt.DisplayRole: return None

        error = self.getError(index)
        if not error: return

        col = index.column()
        value = ""
        if col == self.TYPE_COL:
            value = error.typeLabel()
        elif col == self.ROUTE_COL:
            value = "%s" % error.routeId
        elif col == self.MEASURE_COL:
            value = error.getMeasureString()
        elif col == self.MESSAGE_COL:
            value = error.message

        # return "row %s col %s" % ( index.row(), index.column() )
        return value

    def addErrors(self, errors):
        self.errors.extend(errors)

    def getError(self, index):
        if not index: return None
        row = index.row()
        if row < 0 or row >= len(self.errors): return None
        return self.errors[row]

    def getErrorIndexForChecksum(self, checksum):
        for i in range(len(self.errors)):
            if self.errors[i].getChecksum() == checksum:
                return i
        return None  # should not happen

    def rowsToBeRemoved(self, errorUpdates):
        rows = []
        for checksum in errorUpdates['removedErrorChecksums']:
            rows.append(self.getErrorIndexForChecksum(checksum))
        return rows

    def updateErrors(self, errorUpdates):
        # debug ( 'errorUpdates: %s' % errorUpdates )
        for checksum in errorUpdates['removedErrorChecksums']:
            idx = self.getErrorIndexForChecksum(checksum)
            # debug ( 'remove row %s' % idx )
            self.beginRemoveRows(QModelIndex(), idx, idx)
            del self.errors[idx]
            self.endRemoveRows()

        for error in errorUpdates['updatedErrors']:
            checksum = error.getChecksum()
            idx = self.getErrorIndexForChecksum(checksum)
            # debug ( 'update row %s' % idx )
            self.errors[idx] = error
            topLeft = self.createIndex(idx, 0)
            bottomRight = self.createIndex(idx, 3)
            self.dataChanged.emit(topLeft, bottomRight)

        for error in errorUpdates['addedErrors']:
            # debug ( 'add row' )
            idx = len(self.errors)
            self.beginInsertRows(QModelIndex(), idx, idx)
            self.errors.append(error)
            self.endInsertRows()