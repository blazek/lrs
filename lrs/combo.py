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
from qgis.PyQt.QtGui import *

from .utils import *

# combo is QComboBox or list of QComboBox
class LrsComboManager(QObject):
    def __init__(self, comboOrList, **kwargs):
        super(LrsComboManager, self).__init__()

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

        # https://qgis.org/api/classQgsMapLayerComboBox.html#a7b6a9f46e655c0c48392e33089bbc992
        for combo in self.comboList:
            combo.currentIndexChanged.connect(self.currentIndexChanged)

        # options is dict with of [value,label] pairs
        self.setOptions(kwargs.get('options', []))

    def currentIndexChanged(self, idx):
        # reset other combos
        #debug("currentIndexChanged sender = %s" % self.sender())
        for combo in self.comboList:
            if combo == self.sender():
                continue
            combo.setCurrentIndex(idx)

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
        # (must be treference to the same object?) and with Qt.MatchFixedString it works like with Qt.MatchContains
        # so we do our loop
        for i in range(self.model.rowCount() - 1, -1, -1):
            itemData = self.model.item(i).data(Qt.UserRole)
            if itemData == data:
                return self.model.item(i)
        return None


class LrsLayerComboManager(LrsComboManager):
    layerChanged = pyqtSignal()

    def __init__(self, comboOrList, **kwargs):
        super(LrsLayerComboManager, self).__init__(comboOrList, **kwargs)
        self.geometryType = kwargs.get('geometryType', None)  # QgsWkbTypes.GeometryType
        self.geometryHasM = kwargs.get('geometryHasM', False)  # has measure

        # https://qgis.org/api/classQgsMapLayerComboBox.html#af4d245f67261e82719290ca028224b3c
        self.canvasLayersChanged()

        QgsProject.instance().layersAdded.connect(self.canvasLayersChanged)
        QgsProject.instance().layersRemoved.connect(self.canvasLayersChanged)
        # nameChanged is emitted by layer, see canvasLayersChanged


    def __del__(self):
        if not QgsProject:
            return
        QgsProject.instance().layersAdded.disconnect(self.canvasLayersChanged)
        QgsProject.instance().layersRemoved.disconnect(self.canvasLayersChanged)


    def currentIndexChanged(self, idx):
        super(LrsLayerComboManager, self).currentIndexChanged(idx)
        self.layerChanged.emit()

    def layerId(self):
        idx = self.comboList[0].currentIndex()
        if idx != -1:
            return self.comboList[0].itemData(idx, Qt.UserRole)
        return None

    def getLayer(self):
        if not QgsProject:
            return
        lId = self.layerId()
        return QgsProject.instance().mapLayer(lId)

    def canvasLayersChanged(self):
        # debug ("canvasLayersChanged")
        if not QgsProject:
            return
        # layers = []
        # for layer in QgsProject.instance().mapLayers().values():
        #     print(layer)
        #     if layer.type() != QgsMapLayer.VectorLayer:
        #         continue
        #     if self.geometryType is not None and layer.geometryType() != self.geometryType:
        #         continue
        #     if self.geometryHasM and not QgsWkbTypes.hasM(layer.wkbType()):
        #         continue
        #     layers.append(layer)

        # delete removed layers
        for i in range(self.model.rowCount() - 1, -1, -1):
            lid = self.model.item(i).data(Qt.UserRole)
            if not lid in QgsProject.instance().mapLayers().keys():
                self.model.removeRows(i, 1)

        # add new layers
        for layer in QgsProject.instance().mapLayers().values():
            print(layer)
            if layer.type() != QgsMapLayer.VectorLayer:
                continue
            if self.geometryType is not None and layer.geometryType() != self.geometryType:
                continue
            if self.geometryHasM and not QgsWkbTypes.hasM(layer.wkbType()):
                continue

            start = self.model.index(0, 0, QModelIndex())
            indexes = self.model.match(start, Qt.UserRole, layer.id(), Qt.MatchFixedString)
            if len(indexes) == 0:  # add new
                item = QStandardItem(layer.name())
                item.setData(layer.id(), Qt.UserRole)
                self.model.appendRow(item)
                layer.nameChanged.connect(self.canvasLayersChanged)
            else:  # update text
                index = indexes[0]
                item = self.model.item(index.row(), index.column())
                item.setText(layer.name())

        self.proxy.sort(0)


class LrsFieldComboManager(LrsComboManager):
    def __init__(self, comboOrList, layerComboManager, **kwargs):
        super(LrsFieldComboManager, self).__init__(comboOrList, **kwargs)
        self.types = kwargs.get('types', None)  # QVariant.type
        self.layerComboManager = layerComboManager
        self.layerId = None  # current layer id

        self.layerChanged()

        self.layerComboManager.layerChanged.connect(self.layerChanged)

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

    def layerChanged(self):
        debug("layerChanged settingsName = %s" % self.settingsName )
        if not QgsProject:
            return

        self.disconnectFromLayer()

        self.layerId = self.layerComboManager.layerId()
        # debug ("layerId = %s" % layerId)

        self.resetFields()

        layer = QgsProject.instance().mapLayer(self.layerId)
        if layer:
            layer.attributeAdded.connect(self.resetFields)
            layer.attributeDeleted.connect(self.resetFields)

    def resetFields(self):
        layer = QgsProject.instance().mapLayer(self.layerId)
        if not layer:
            for combo in self.comboList:
                combo.clear()
                return

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
            # debug ("%s %s %s" % ( field.name(), field.type(), self.types) )
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


class LrsUnitComboManager(LrsComboManager):
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
