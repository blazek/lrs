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
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QStandardItem
from qgis._core import QgsProject

from ..lrs.utils import debug
from .lrscombomanagerbase import LrsComboManagerBase


class LrsFieldComboManager(LrsComboManagerBase):
    fieldNameChanged = pyqtSignal(str)
    fieldNameActivated = pyqtSignal(str)

    def __init__(self, comboOrList, layerComboManager, **kwargs):
        super(LrsFieldComboManager, self).__init__(comboOrList, **kwargs)
        self.types = kwargs.get('types', None)  # QVariant.type
        self.layerComboManager = layerComboManager
        # it is easier/safer to work with layer id instead of with the layer, because
        # it may be deleted in C++ and disconnect fails
        self.layerId = None  # current layer id

        self.connectCombos()
        self.layerComboManager.layerChanged.connect(self.layerChanged)

    def reload(self):
        self.layerChanged(self.layerComboManager.getLayer())

    def __del__(self):
        self.disconnectFromLayer()

    def getFieldName(self):
        idx = self.comboList[0].currentIndex()
        if idx != -1:
            return self.comboList[0].itemData(idx, Qt.UserRole)
        return None

    def disconnectFromLayer(self):
        layer = QgsProject.instance().mapLayer(self.layerId)
        if layer:
            layer.attributeAdded.disconnect(self.resetFields)
            layer.attributeDeleted.disconnect(self.resetFields)

    def layerChanged(self, layer):
        #debug("layerChanged settingsName = %s" % self.settingsName)
        if not QgsProject:
            return

        self.disconnectFromLayer()

        self.layerId = layer.id() if layer else None
        # debug ("layerId = %s" % layerId)

        self.resetFields()

        # layer = QgsProject.instance().mapLayer(self.layerId)
        if layer:
            layer.attributeAdded.connect(self.resetFields)
            layer.attributeDeleted.connect(self.resetFields)

    def resetFields(self):
        #debug("resetFields settingsName = %s" % self.settingsName)
        layer = QgsProject.instance().mapLayer(self.layerId)
        if not layer:
            for combo in self.comboList:
                combo.clear()
                return

        #debug("resetFields layer = %s" % layer.name())

        # Add none item
        if self.allowNone:
            item = self.findItemByData(None)
            if not item:
                item = QStandardItem("-----")
                item.setData(None, Qt.UserRole)
                self.model.appendRow(item)

        fieldsNames = []
        for idx, field in enumerate(layer.pendingFields()):
            if self.types and not field.type() in self.types: continue
            fieldsNames.append(field.name())

        # delete removed
        for i in range(self.model.rowCount() - 1, -1, -1):
            fieldName = self.model.item(i).data(Qt.UserRole)
            if self.allowNone and fieldName is None: continue
            if not fieldName in fieldsNames:
                self.model.removeRows(i, 1)

        # add new fields
        for idx, field in enumerate(layer.pendingFields()):
            #debug("resetFields %s %s %s" % (field.name(), field.type(), self.types))
            if self.types and not field.type() in self.types: continue
            fieldName = field.name()
            fieldLabel = layer.attributeDisplayName(idx)

            item = self.findItemByData(fieldName)
            if not item:  # add new
                item = QStandardItem(fieldLabel)
                item.setData(fieldName, Qt.UserRole)
                self.model.appendRow(item)
            else:  # update text
                item.setText(fieldLabel)

        self.proxy.sort(0)

    def currentIndexChanged(self, idx):
        #debug("LrsFieldComboManager currentIndexChanged idx = %s settingsName = %s" % (idx, self.settingsName))
        super(LrsFieldComboManager, self).currentIndexChanged(idx)
        self.fieldNameChanged.emit(self.getFieldName())

    def activated(self, idx):
        #self.debug("LrsFieldComboManager activated idx = %s value = %s" % (idx, self.getFieldName()))
        self.fieldNameActivated.emit(self.getFieldName())