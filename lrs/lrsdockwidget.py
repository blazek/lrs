# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsDockWidget
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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
import qgiscombomanager as cm
from qgis.core import *
from qgis.gui import *

from ui_lrsdockwidget import Ui_LrsDockWidget
from utils import *
from error import *
from lrs import Lrs

#class LrsDockWidget(QDockWidget):
class LrsDockWidget( QDockWidget, Ui_LrsDockWidget ):
    def __init__( self,parent, iface ):
        self.iface = iface
        self.lrsCrs = None
        if self.iface.mapCanvas().mapRenderer().hasCrsTransformEnabled():
            self.lrsCrs = self.iface.mapCanvas().mapRenderer().destinationCrs()
        self.lrs = None # Lrs object
        self.errorHighlight = None 
        self.errorPointLayer = None
        self.errorLineLayer = None
        self.qualityLayer = None
 
        super(LrsDockWidget, self).__init__(parent )
        
        # Set up the user interface from Designer.
        self.setupUi( self )
        

        ##### getTab 
        # initLayer, initField, fieldType did not work, fixed and created pull request
        # https://github.com/3nids/qgiscombomanager/pull/1

        self.genLineLayerCM = cm.VectorLayerCombo( self.genLineLayerCombo, 'lines', {'geomType':QGis.Line } )
        self.genLineRouteFieldCM = cm.FieldCombo( self.genLineRouteFieldCombo, self.genLineLayerCM, 'route' )
        self.genPointLayerCM = cm.VectorLayerCombo( self.genPointLayerCombo, 'points', {'geomType':QGis.Point } )
        self.genPointRouteFieldCM = cm.FieldCombo( self.genPointRouteFieldCombo, self.genPointLayerCM, 'route' )
        # TODO: allow integers, currently only one type supported by fieldType
        #self.genPointMeasureFieldCM = cm.FieldCombo( self.genPointMeasureFieldCombo, self.genPointLayerCM, 'km', { 'fieldType':QVariant.Double } )
        self.genPointMeasureFieldCM = cm.FieldCombo( self.genPointMeasureFieldCombo, self.genPointLayerCM, 'km' )

        self.genButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.generateLrs)

        ##### errorTab
        self.errorModel = None
        self.errorView.horizontalHeader().setStretchLastSection ( True )
        self.errorZoomButton.setEnabled( False) 
        self.errorZoomButton.setIcon( QgsApplication.getThemeIcon( '/mActionZoomIn.svg' ) )
        self.errorZoomButton.setText('Zoom')
        self.errorZoomButton.clicked.connect( self.errorZoom )

        ##### error / quality layers
        self.addErrorLayersButton.clicked.connect( self.addErrorLayers )
        self.addQualityLayerButton.clicked.connect( self.addQualityLayer )

        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.layersWillBeRemoved)
        
        QgsProject.instance().readProject.connect( self.projectRead )

        # read project if plugin was reloaded
        self.projectRead()

        # debug
        if self.genLineLayerCM.getLayer():
            self.generateLrs() # only when reloading!

    def projectRead(self):
        #debug("projectRead")
        ##### set error layers if stored in project
        project = QgsProject.instance()
        if not project: return

        registry = QgsMapLayerRegistry.instance()

        errorLineLayerId = project.readEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId" )[0]
        if errorLineLayerId: 
            self.errorLineLayer = registry.mapLayer( errorLineLayerId )

        errorPointLayerId = project.readEntry( PROJECT_PLUGIN_NAME, "errorPointLayerId" )[0]
        if errorPointLayerId: 
            self.errorPointLayer = registry.mapLayer( errorPointLayerId )

        qualityLayerId = project.readEntry( PROJECT_PLUGIN_NAME, "qualityLayerId" )[0]
        if qualityLayerId: 
            self.qualityLayer = registry.mapLayer( qualityLayerId )


    def close(self):
        print "close"
        if self.lrs:
            self.lrs.disconnect()
        QgsMapLayerRegistry.instance().layersWillBeRemoved.disconnect(self.layersWillBeRemoved)
        # Must delete combo managers to disconnect!
        del self.genLineLayerCM
        del self.genLineRouteFieldCM
        del self.genPointLayerCM
        del self.genPointRouteFieldCM
        del self.genPointMeasureFieldCM
        if self.errorHighlight:
            del self.errorHighlight
        super(LrsDockWidget, self).close()

    def generateLrs(self):
        #debug ( 'generateLrs')

        self.clearHighlight()

        threshold = self.genThresholdSpin.value()
        self.lrs = Lrs ( self.genLineLayerCM.getLayer(), self.genLineRouteFieldCM.getFieldName(), self.genPointLayerCM.getLayer(), self.genPointRouteFieldCM.getFieldName(), self.genPointMeasureFieldCM.getFieldName(), crs = self.lrsCrs, threshold = threshold )
    
        self.errorZoomButton.setEnabled( False)
        self.errorModel = LrsErrorModel()
        self.errorModel.addErrors( self.lrs.getErrors() )

        self.sortErrorModel = QSortFilterProxyModel()
        self.sortErrorModel.setSourceModel( self.errorModel )
         
        self.errorView.setModel( self.sortErrorModel )
        self.errorView.resizeColumnsToContents ()
        self.errorView.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Attention, if selectionMode is QTableView.SingleSelection, selection is not
        # cleared if deleted row was selected (at least one row is always selected)
        self.errorView.setSelectionMode(QTableView.SingleSelection)
        self.errorView.selectionModel().selectionChanged.connect(self.errorSelectionChanged)
        
        self.lrs.updateErrors.connect ( self.updateErrors )
        
        self.resetErrorLayers()
        self.resetQualityLayer()

        if self.errorPointLayer or self.errorLineLayer or self.qualityLayer:
            self.iface.mapCanvas().refresh()
        

    def updateErrors( self, errorUpdates):
        debug ( "updateErrors" )
        # because SingleSelection does not allow to deselect row, we have to clear selection manually
        index = self.getSelectedErrorIndex()
        if index:
            rows = self.errorModel.rowsToBeRemoved( errorUpdates )
            selected = index.row()
            if selected in rows:
                self.errorView.selectionModel().clear()
        self.errorModel.updateErrors( errorUpdates )
        self.resetErrorLayers()
        self.resetQualityLayer()

    def clearHighlight(self):
        self.errorZoomButton.setEnabled( False) 
        if self.errorHighlight:
            del self.errorHighlight
            self.errorHighlight = None

    def errorSelectionChanged(self, selected, deselected ):
        self.clearHighlight()

        error = self.getSelectedError()
        if not error: return

        print 'error %s' % error.typeLabel()
        # we have geo in current canvas CRS but QgsHighlight does reprojection
        # from layer CRS so we have to use fake layer
        layer = QgsVectorLayer( 'Point?crs=' + self.iface.mapCanvas().mapRenderer().destinationCrs().authid() )
        
        print error.geo
        print error.geo.exportToWkt()
        self.errorHighlight = QgsHighlight( self.iface.mapCanvas(), error.geo, layer )
        # highlight point size is hardcoded in QgsHighlight
        self.errorHighlight.setWidth( 2 )
        self.errorHighlight.setColor( Qt.red )
        self.errorHighlight.show()

        self.errorZoomButton.setEnabled(True) 

    def getSelectedErrorIndex(self):
        sm = self.errorView.selectionModel()
        if not sm.hasSelection(): return None
        index = sm.selection().indexes()[0]
        index = self.sortErrorModel.mapToSource(index)
        return index

    def getSelectedError(self):
        index = self.getSelectedErrorIndex()
        if not index: return None
        return self.errorModel.getError(index)

    def errorZoom(self):
        error = self.getSelectedError()
        if not error: return
        
        geo = error.geo
        if geo.wkbType() == QGis.WKBPoint:
            p = geo.asPoint()
            b = 2000 # buffer
            extent = QgsRectangle(p.x()-b, p.y()-b, p.x()+b, p.y()+b)
        else: #line
            extent = geo.boundingBox()
            extent.scale(2)
        self.iface.mapCanvas().setExtent( extent )
        self.iface.mapCanvas().refresh();

    # add new error layers to map
    def addErrorLayers(self):
        # changes done to vector layer attributes are not store correctly in project file
        # http://hub.qgis.org/issues/8997 -> recreate temporary provider first to construct uri

        attributes = [ 
            QgsField('error', QVariant.String, "string"), # error type, avoid 'type' which could be keyword
            QgsField('route', QVariant.String, "string" ),
            QgsField('measure', QVariant.String, "string"),
        ]

        project = QgsProject.instance()

        if not self.errorLineLayer:
            provider = QgsProviderRegistry.instance().provider( 'memory', 'LineString' )
            provider.addAttributes( attributes )
            uri = provider.dataSourceUri()
            #debug ( "uri = " + uri )
            self.errorLineLayer = QgsVectorLayer( uri, 'LRS line errors', 'memory')
            self.resetErrorLineLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorLineLayer,] )
            project.writeEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId", self.errorLineLayer.id() )

        if not self.errorPointLayer:
            provider = QgsProviderRegistry.instance().provider( 'memory', 'Point' )
            provider.addAttributes( attributes )
            uri = provider.dataSourceUri()
            self.errorPointLayer = QgsVectorLayer( uri, 'LRS point errors', 'memory')
            self.resetErrorPointLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorPointLayer,] )
            project.writeEntry( PROJECT_PLUGIN_NAME, "errorPointLayerId", self.errorPointLayer.id() )
   
    # reset error layers content (features)
    def resetErrorLayers(self):
        #debug ( "resetErrorLayers" )
        self.resetErrorPointLayer()
        self.resetErrorLineLayer()

    def resetErrorPointLayer(self):
        #debug ( "resetErrorPointLayer %s" % self.errorPointLayer )
        if not self.errorPointLayer: return
        clearLayer( self.errorPointLayer )
        errors = self.lrs.getErrors()
        #self.errorPointLayer.startEditing()
        fields = self.errorPointLayer.pendingFields()
        features = []
        for error in errors:
            if error.geo.wkbType() != QGis.WKBPoint: continue
            feature = QgsFeature( fields )
            feature.setGeometry( error.geo )
            feature.setAttribute( 'error', error.typeLabel() )
            feature.setAttribute( 'route', '%s' % error.routeId )
            feature.setAttribute( 'measure', error.getMeasureString() )
            #self.errorPointLayer.addFeatures( [ feature ] )
            features.append( feature )
        self.errorPointLayer.dataProvider().addFeatures( features )
        #self.errorPointLayer.commitChanges()            

    def resetErrorLineLayer(self):
        if not self.errorLineLayer: return
        clearLayer( self.errorLineLayer )
        errors = self.lrs.getErrors()
        #self.errorLineLayer.startEditing()
        fields = self.errorLineLayer.pendingFields()
        features = []
        for error in errors:
            if error.geo.wkbType() != QGis.WKBLineString: continue
            feature = QgsFeature( fields )
            feature.setGeometry( error.geo )
            feature.setAttribute( 'error', error.typeLabel() )
            feature.setAttribute( 'route', '%s' % error.routeId )
            feature.setAttribute( 'measure', error.getMeasureString() )
            #self.errorLineLayer.addFeatures( [ feature ] )
            features.append( feature )
        #self.errorLineLayer.commitChanges()            
        self.errorLineLayer.dataProvider().addFeatures( features )

    def addQualityLayer(self):
        if not self.qualityLayer:
            attributes = [ 
                QgsField('route', QVariant.String, "string"),
                QgsField('m_from', QVariant.Double, "double"),
                QgsField('m_to', QVariant.Double, "double"),
                QgsField('l', QVariant.Double, "double"),
            ]
            provider = QgsProviderRegistry.instance().provider( 'memory', 'LineString' )
            provider.addAttributes( attributes )
            uri = provider.dataSourceUri()
            self.qualityLayer = QgsVectorLayer( uri, 'LRS quality', 'memory')
            self.resetQualityLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.qualityLayer,] )
            project = QgsProject.instance()
            project.writeEntry( PROJECT_PLUGIN_NAME, "qualityLayerId", self.qualityLayer.id() )

    def resetQualityLayer(self):
        debug ( "resetQualityLayer %s" % self.qualityLayer )
        if not self.qualityLayer: return
        clearLayer( self.qualityLayer )
        segments = self.lrs.getSegments()
        #self.qualityLayer.startEditing()
        fields = self.qualityLayer.pendingFields()
        features = []
        for segment in segments:
            feature = QgsFeature( fields )
            feature.setGeometry( segment.geo )
            feature.setAttribute( 'route', '%s' % segment.routeId )
            feature.setAttribute( 'm_from', segment.record.milestoneFrom )
            feature.setAttribute( 'm_to', segment.record.milestoneTo )
            feature.setAttribute( 'l', segment.geo.length() )
            self.qualityLayer.addFeatures( [ feature ] )
            features.append( feature )
        #self.qualityLayer.commitChanges()            
        self.qualityLayer.dataProvider().addFeatures( features )
            
    def layersWillBeRemoved(self, layerIdList ):
        project = QgsProject.instance()
        for id in layerIdList:
            if self.errorPointLayer and self.errorPointLayer.id() == id:
                self.errorPointLayer = None
                project.removeEntry( PROJECT_PLUGIN_NAME, "errorPointLayerId" )
            if self.errorLineLayer and self.errorLineLayer.id() == id:
                self.errorLineLayer = None
                project.removeEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId" )
            if self.qualityLayer and self.qualityLayer.id() == id:
                self.qualityLayer = None
                project.removeEntry( PROJECT_PLUGIN_NAME, "qualityLayerId" )
            
