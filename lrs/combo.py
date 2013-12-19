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

    def __init__(self, combo, **kwargs ):
        super(LrsComboManager, self).__init__()
        self.combo = combo # QComboBox
        self.settingsName = kwargs.get('settingsName')
        self.allowNone = kwargs.get('allowNone', False) # allow select none
        self.sort = kwargs.get('sort', True) # sort values
        #debug ( "sort = %s" % self.sort ) 
        self.defaultValue = kwargs.get('defaultValue', None)

        self.model = QStandardItemModel(0, 1, self)

        if self.sort:
            self.proxy = QSortFilterProxyModel(self)
            self.proxy.setSourceModel(self.model)
            self.combo.setModel(self.proxy);
        else:
            self.proxy = None
            self.combo.setModel(self.model)

        # options is dict with of [value,label] pairs
        self.setOptions( kwargs.get('options', []) )

    def setOptions(self, options):
        self.options = options
        self.model.clear()
        if options:
            for opt in options:
                item = QStandardItem( opt[1] )
                item.setData( opt[0], Qt.UserRole )
                self.model.appendRow( item )

    def value(self):
        idx = self.combo.currentIndex()
        if idx != -1:
            return self.combo.itemData(idx, Qt.UserRole )
        return None

    def writeToProject(self):
        idx = self.combo.currentIndex()
        val = self.combo.itemData(idx, Qt.UserRole )
        QgsProject.instance().writeEntry(PROJECT_PLUGIN_NAME, self.settingsName, val )

    def readFromProject(self):
        val = QgsProject.instance().readEntry(PROJECT_PLUGIN_NAME, self.settingsName )[0]
        if val == '': val = None # to set correctly none

        idx = self.combo.findData(val, Qt.UserRole)
        #debug( "readFromProject settingsName = %s val = %s idx = %s" % ( self.settingsName, val, idx) )
        if idx == -1:
            idx = self.combo.findData( self.defaultValue, Qt.UserRole)
        
        self.combo.setCurrentIndex(idx)

    # reset to index -1
    def reset(self):
        if self.defaultValue is not None:
            idx = self.combo.findData( self.defaultValue, Qt.UserRole )
            #debug( "defaultValue = %s idx = %s" % ( self.defaultValue, idx ) )
            self.combo.setCurrentIndex( idx )
        else:
            self.combo.setCurrentIndex(-1)

    def findItemByData(self, data, flags = Qt.MatchFixedString ):
        start = self.model.index(0,0, QModelIndex())
        indexes = self.model.match( start, Qt.UserRole, data, flags )
        if len(indexes) == 0: return None
        index = indexes[0]
        return self.model.item( index.row(), index.column())

class LrsLayerComboManager(LrsComboManager):
    layerChanged = pyqtSignal()

    def __init__(self, combo, **kwargs ):
        super(LrsLayerComboManager, self).__init__(combo,**kwargs)
        self.geometryType = kwargs.get('geometryType', None) # QGis.GeometryType

        self.combo.currentIndexChanged.connect(self.currentIndexChanged)

        self.canvasLayersChanged()

        QgsMapLayerRegistry.instance().layersAdded.connect(self.canvasLayersChanged)
        QgsMapLayerRegistry.instance().layersRemoved.connect(self.canvasLayersChanged)
    def __del__(self):
        if not QgsMapLayerRegistry: return
        QgsMapLayerRegistry.instance().layersAdded.disconnect(self.canvasLayersChanged)
        QgsMapLayerRegistry.instance().layersRemoved.disconnect(self.canvasLayersChanged)

    def currentIndexChanged(self):
        self.layerChanged.emit()

    def layerId(self):
        idx = self.combo.currentIndex()
        if idx != -1:
            return self.combo.itemData(idx, Qt.UserRole )
        return None

    def getLayer(self):
        if not QgsMapLayerRegistry: return
        lId = self.layerId()
        return QgsMapLayerRegistry.instance().mapLayer( lId )

    def canvasLayersChanged(self):
        #debug ("canvasLayersChanged")
        if not QgsMapLayerRegistry: return
        layerIds = []
        for layerId, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            if layer.type() != QgsMapLayer.VectorLayer: continue
            if self.geometryType is not None and layer.geometryType() != self.geometryType: continue
            layerIds.append(layerId)

        # delete removed layers
        for i in range( self.model.rowCount()-1, -1, -1):
            lid = self.model.item(i).data( Qt.UserRole )
            if not lid in layerIds:
                self.model.removeRows(i,1)

        # add new layers
        for layerId, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            if layer.type() != QgsMapLayer.VectorLayer: continue
            if self.geometryType is not None and layer.geometryType() != self.geometryType: continue

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
        super(LrsFieldComboManager, self).__init__(combo, **kwargs)
        self.types = kwargs.get('types', None) # QVariant.type
        self.layerComboManager = layerComboManager


        self.layerChanged()

        self.layerComboManager.layerChanged.connect(self.layerChanged)

    def getFieldName(self):
        idx = self.combo.currentIndex()
        if idx != -1:
            return self.combo.itemData(idx, Qt.UserRole )
        return None


    def layerChanged(self):
        #debug ("layerChanged settingsName = %s" % self.settingsName )
        if not QgsMapLayerRegistry: return

        layerId = self.layerComboManager.layerId()
        #debug ("layerId = %s" % layerId)

        layer = QgsMapLayerRegistry.instance().mapLayer( layerId )
        if not layer:
            self.combo.clear()
            return            

        # Add none item
        if self.allowNone:
            item = self.findItemByData(None)
            if not item:
                item = QStandardItem( "-----" )
                item.setData( None, Qt.UserRole )
                self.model.appendRow( item )

        fieldsNames = []
        for idx, field in enumerate(layer.pendingFields()):
            if self.types and not field.type() in self.types: continue
            fieldsNames.append( field.name() )

        # delete removed
        for i in range( self.model.rowCount()-1, -1, -1):
            fieldName = self.model.item(i).data( Qt.UserRole )
            if self.allowNone and fieldName is None: continue
            if not fieldName in fieldsNames:
                self.model.removeRows(i,1)
        
        # add new fields
        for idx, field in enumerate(layer.pendingFields()):
            #debug ("%s %s" % ( field.type(), self.types) )
            if self.types and not field.type() in self.types: continue
            fieldName = field.name()
            fieldLabel = layer.attributeDisplayName(idx)

            item = self.findItemByData(fieldName)
            if not item: # add new
                item = QStandardItem( fieldLabel )
                item.setData( fieldName, Qt.UserRole )
                self.model.appendRow( item )
            else: # update text
                item.setText( fieldLabel )
        
        self.proxy.sort(0)

class LrsUnitComboManager(LrsComboManager):

    def __init__(self, combo, **kwargs ):
        kwargs['sort'] = False
        super(LrsUnitComboManager, self).__init__(combo,**kwargs)

        for unit in [ LrsUnits.METER, LrsUnits.KILOMETER, LrsUnits.FEET, LrsUnits.MILE]:
            item = QStandardItem( LrsUnits.unitName( unit ) )
            item.setData( unit, Qt.UserRole )
            self.model.appendRow( item )

        self.reset()

    def unit(self):
        idx = self.combo.currentIndex()
        if idx != -1:
            return self.combo.itemData(idx, Qt.UserRole )
        return LrsUnits.UNKNOWN

    def writeToProject(self):
        name = LrsUnits.unitName( self.unit() )
        QgsProject.instance().writeEntry(PROJECT_PLUGIN_NAME, self.settingsName, name )

    def readFromProject(self):
        name = QgsProject.instance().readEntry(PROJECT_PLUGIN_NAME, self.settingsName )[0]

        unit = LrsUnits.unitFromName( name )
        idx = self.combo.findData( unit, Qt.UserRole)
        #debug( "readFromProject settingsName = %s name = %s idx = %s" % ( self.settingsName, name, idx) )
        if idx != -1:
            self.combo.setCurrentIndex(idx)
        else:
            self.reset()
