# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsPlugin
                                 A QGIS plugin
 Linear reference system builder and editor
                              -------------------
        begin                : 2013-10-02
        copyright            : (C) 2013 by Radim Blažek
        email                : radim.blazek@gmail.com

 Partialy based on qgiscombomanager by Denis Rouzaud.

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
from ..lrs.utils import *
from qgis.PyQt.QtGui import *


# combo is QComboBox or list of QComboBox
class LrsComboManagerBase(QObject):
    def __init__(self, comboOrList, **kwargs):
        super(LrsComboManagerBase, self).__init__()

        if isinstance(comboOrList, list):
            self.comboList = comboOrList
        else:
            self.comboList = [comboOrList]  # QComboBox list
        self.settingsName = kwargs.get('settingsName')
        self.allowNone = kwargs.get('allowNone', False)  # allow select none
        self.sort = kwargs.get('sort', True)  # sort values
        # debug ( "sort = %s" % self.sort )
        self.defaultValue = kwargs.get('defaultValue', None)

        self.model = QStandardItemModel(0, 1, self)

        if self.sort:
            self.proxy = QSortFilterProxyModel(self)
            self.proxy.setSourceModel(self.model)
        else:
            self.proxy = None

        for combo in self.comboList:
            if self.proxy:
                combo.setModel(self.proxy);
            else:
                combo.setModel(self.model)

        # options is dict with of [value,label] pairs
        self.setOptions(kwargs.get('options', []))

    def debug(self, message):
        debug("CM(%s): %s" % (self.settingsName, message))

    def connectCurrentIndexChanged(self):
        # https://qgis.org/api/classQgsMapLayerComboBox.html#a7b6a9f46e655c0c48392e33089bbc992
        for combo in self.comboList:
            combo.currentIndexChanged.connect(self.currentIndexChanged)

    def currentIndexChanged(self, idx):
        # reset other combos
        self.debug("LrsComboManager currentIndexChanged")
        #debug("currentIndexChanged sender = %s" % self.sender())
        for combo in self.comboList:
            if combo == self.sender():
                continue
            combo.setCurrentIndex(idx)

    # To be implemented in subclasses, load layers from project, fields from layer, ...
    def reload(self):
        pass

    def clear(self):
        self.options = []
        self.model.clear()

    def setOptions(self, options):
        self.options = options
        self.model.clear()
        if options:
            for opt in options:
                item = QStandardItem(opt[1])
                item.setData(opt[0], Qt.UserRole)
                self.model.appendRow(item)

    def value(self):
        idx = self.comboList[0].currentIndex()
        if idx != -1:
            return self.comboList[0].itemData(idx, Qt.UserRole)
        return None

    def writeToProject(self):
        idx = self.comboList[0].currentIndex()
        val = self.comboList[0].itemData(idx, Qt.UserRole)
        QgsProject.instance().writeEntry(PROJECT_PLUGIN_NAME, self.settingsName, val)

    def readFromProject(self):
        val = QgsProject.instance().readEntry(PROJECT_PLUGIN_NAME, self.settingsName)[0]
        if val == '':
            val = None  # to set correctly none

        for combo in self.comboList:
            idx = combo.findData(val, Qt.UserRole)
            # debug( "readFromProject settingsName = %s val = %s idx = %s" % ( self.settingsName, val, idx) )
            if idx == -1:
                idx = combo.findData(self.defaultValue, Qt.UserRole)
            combo.setCurrentIndex(idx)

    # reset to index -1
    def reset(self):
        for combo in self.comboList:
            if self.defaultValue is not None:
                idx = combo.findData(self.defaultValue, Qt.UserRole)
                # debug( "defaultValue = %s idx = %s" % ( self.defaultValue, idx ) )
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(-1)

    def findItemByData(self, data):
        # QStandardItemModel.match() is not suitable, with Qt.MatchExactly it seems to comare objects
        # (must be reference to the same object?) and with Qt.MatchFixedString it works like with Qt.MatchContains
        # so we do our loop
        for i in range(self.model.rowCount() - 1, -1, -1):
            itemData = self.model.item(i).data(Qt.UserRole)
            if itemData == data:
                return self.model.item(i)
        return None
