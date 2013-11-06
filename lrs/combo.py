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
from PyQt4.QtCore import *
from PyQt4.QtGui import * 
from qgis.core import *

from utils import *

class LrsComboManager(QObject):

    def __init__(self, **kwargs ):
        super(LrsComboManager, self).__init__()
        self.settingsName = kwargs.get('settingsName')

class LrsLayerComboManager(LrsComboManager):
    layerChanged = pyqtSignal()

    def __init__(self, combo, **kwargs ):
        super(LrsLayerComboManager, self).__init__(**kwargs)
        self.combo = combo # QComboBox
        self.geometryType = kwargs.get('geometryType') # QGis.GeometryType

        self.proxy = QSortFilterProxyModel(self)
        self.model = QStandardItemModel(0, 1, self)
        self.proxy.setSourceModel(self.model)
        self.combo.setModel(self.proxy);
        self.combo.currentIndexChanged.connect(self.currentIndexChanged)

        self.canvasLayersChanged()

        QgsMapLayerRegistry.instance().layersAdded.connect(self.canvasLayersChanged)
        QgsMapLayerRegistry.instance().layersRemoved.connect(self.canvasLayersChanged)

    def currentIndexChanged(self):
        self.layerChanged.emit()

    def layerId(self):
        idx = self.combo.currentIndex()
        if idx != -1:
            return self.combo.itemData(idx, Qt.UserRole )
        return None

    def canvasLayersChanged(self):
        #debug ("canvasLayersChanged")
        if not QgsMapLayerRegistry: return
        layerIds = []
        for layerId, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            if layer.geometryType() != self.geometryType: continue
            layerIds.append(layerId)

        # delete removed layers
        for i in range( self.model.rowCount()-1, -1, -1):
            lid = self.model.item(i).data( Qt.UserRole )
            if not lid in layerIds:
                self.model.removeRows(i,1)

        # add new layers
        for layerId, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            if layer.geometryType() != self.geometryType: continue

            start = self.model.index(0,0, QModelIndex())
            indexes = self.model.match( start, Qt.UserRole, layerId, Qt.MatchFixedString )
            if len(indexes) == 0: # add new
                item = QStandardItem( layer.name() )
                item.setData( layerId, Qt.UserRole )
                self.model.appendRow( item )
            else: # update text
                index = indexes[0]
                item = self.model.item( index.row(), index.column())
                item.setText( layer.name() )

        self.proxy.sort(0)


class LrsFieldComboManager(LrsComboManager):

    def __init__(self, combo, layerComboManager, **kwargs ):
        super(LrsFieldComboManager, self).__init__(**kwargs)
        self.combo = combo # QComboBox
        self.types = kwargs.get('types', None) # QVariant.type
        self.layerComboManager = layerComboManager

        self.proxy = QSortFilterProxyModel(self)
        self.model = QStandardItemModel(0, 1, self)
        self.proxy.setSourceModel(self.model)
        self.combo.setModel(self.proxy);

        self.layerChanged()

        self.layerComboManager.layerChanged.connect(self.layerChanged)

    def layerChanged(self):
        debug ("layerChanged")
        if not QgsMapLayerRegistry: return

        layerId = self.layerComboManager.layerId()
        debug ("layerId = %s" % layerId)

        layer = QgsMapLayerRegistry.instance().mapLayer( layerId )
        if not layer:
            self.combo.clear()
            return            

        fieldsNames = []
        for idx, field in enumerate(layer.pendingFields()):
            if self.types and not field.type() in self.types: continue
            fieldsNames.append( field.name() )

        # delete removed
        for i in range( self.model.rowCount()-1, -1, -1):
            fieldName = self.model.item(i).data( Qt.UserRole )
            if not fieldName in fieldsNames:
                self.model.removeRows(i,1)
        
        # add new fields
        for idx, field in enumerate(layer.pendingFields()):
            #debug ("%s %s" % ( field.type(), self.types) )
            if self.types and not field.type() in self.types: continue
            fieldName = field.name()
            fieldLabel = layer.attributeDisplayName(idx)

            start = self.model.index(0,0, QModelIndex())
            indexes = self.model.match( start, Qt.UserRole, fieldName, Qt.MatchFixedString )
            if len(indexes) == 0: # add new
                item = QStandardItem( fieldLabel )
                item.setData( fieldName, Qt.UserRole )
                self.model.appendRow( item )
            else: # update text
                index = indexes[0]
                item = self.model.item( index.row(), index.column())
                item.setText( fieldLabel )
        
        self.proxy.sort(0)

