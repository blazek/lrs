# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsPlugin
                                 A QGIS plugin
 Linear reference system builder and editor
                              -------------------
        begin                : 2017-5-29
        copyright            : (C) 2017 by Radim Blažek
        email                : radim.blazek@gmail.com
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
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem
from qgis._core import QgsProject

from ..lrs.utils import LrsUnits, PROJECT_PLUGIN_NAME
from .lrscombomanagerbase import LrsComboManagerBase


class LrsUnitComboManager(LrsComboManagerBase):
    def __init__(self, comboOrList, **kwargs):
        kwargs['sort'] = False
        super(LrsUnitComboManager, self).__init__(comboOrList, **kwargs)

        for unit in [LrsUnits.METER, LrsUnits.KILOMETER, LrsUnits.FEET, LrsUnits.MILE]:
            item = QStandardItem(LrsUnits.unitName(unit))
            item.setData(unit, Qt.UserRole)
            self.model.appendRow(item)

        self.reset()

    def unit(self):
        idx = self.comboList[0].currentIndex()
        if idx != -1:
            return self.comboList[0].itemData(idx, Qt.UserRole)
        return LrsUnits.UNKNOWN

    def writeToProject(self):
        name = LrsUnits.unitName(self.unit())
        QgsProject.instance().writeEntry(PROJECT_PLUGIN_NAME, self.settingsName, name)

    def readFromProject(self):
        name = QgsProject.instance().readEntry(PROJECT_PLUGIN_NAME, self.settingsName)[0]

        unit = LrsUnits.unitFromName(name)
        idx = self.comboList[0].findData(unit, Qt.UserRole)
        # debug( "readFromProject settingsName = %s name = %s idx = %s" % ( self.settingsName, name, idx) )
        if idx != -1:
            for combo in self.comboList:
                combo.setCurrentIndex(idx)
        else:
            self.reset()