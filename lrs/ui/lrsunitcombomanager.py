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