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
from qgis.PyQt.QtWidgets import *


class LrsWidgetManager(QObject):
    def __init__(self, widget, **kwargs):
        super(LrsWidgetManager, self).__init__()
        self.widget = widget
        self.settingsName = kwargs.get('settingsName')
        self.defaultValue = kwargs.get('defaultValue')

    def defaultValue(self):
        return self.defaultValue

    def reset(self):
        if issubclass(self.widget.__class__, QDoubleSpinBox):
            self.widget.setValue(self.defaultValue)
        elif issubclass(self.widget.__class__, QLineEdit):
            self.widget.setText(self.defaultValue)
        elif issubclass(self.widget.__class__, QCheckBox):
            self.widget.setChecked(self.defaultValue)
        else:
            raise Exception("not supported widget")

    def writeToProject(self):
        project = QgsProject.instance()
        if issubclass(self.widget.__class__, QDoubleSpinBox):
            val = self.widget.value()
            project.writeEntryDouble(PROJECT_PLUGIN_NAME, self.settingsName, val)
        elif issubclass(self.widget.__class__, QLineEdit):
            val = self.widget.text()
            project.writeEntry(PROJECT_PLUGIN_NAME, self.settingsName, val)
        elif issubclass(self.widget.__class__, QCheckBox):
            val = self.widget.isChecked()
            project.writeEntry(PROJECT_PLUGIN_NAME, self.settingsName, val)
        else:
            raise Exception("not supported widget")

    def readFromProject(self):
        project = QgsProject.instance()

        if issubclass(self.widget.__class__, QDoubleSpinBox):
            val = project.readDoubleEntry(PROJECT_PLUGIN_NAME, self.settingsName, self.defaultValue)[0]
            self.widget.setValue(val)
        elif issubclass(self.widget.__class__, QLineEdit):
            val = project.readEntry(PROJECT_PLUGIN_NAME, self.settingsName, self.defaultValue)[0]
            self.widget.setText(val)
        elif issubclass(self.widget.__class__, QCheckBox):
            val = project.readBoolEntry(PROJECT_PLUGIN_NAME, self.settingsName, self.defaultValue)[0]
            self.widget.setChecked(val)
        else:
            raise Exception("not supported widget")
