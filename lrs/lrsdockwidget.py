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

        # debug
        if self.genLineLayerCM.getLayer():
            self.generateLrs() # only when reloading!

    def close(self):
        print "close"
        if self.lrs:
            self.lrs.disconnect()
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
        debug ( 'generateLrs')

        threshold = self.genThresholdSpin.value()
        self.lrs = Lrs ( self.genLineLayerCM.getLayer(), self.genLineRouteFieldCM.getFieldName(), self.genPointLayerCM.getLayer(), self.genPointRouteFieldCM.getFieldName(), self.genPointMeasureFieldCM.getFieldName(), crs = self.lrsCrs, threshold = threshold )
    
        self.errorZoomButton.setEnabled( False)
        self.errorModel = LrsErrorModel()
        self.errorModel.addErrors( self.lrs.getErrors() )

        self.sortErrorModel = QSortFilterProxyModel()
        self.sortErrorModel.setSourceModel( self.errorModel )
         
        self.errorView.setModel( self.sortErrorModel )
        self.errorView.resizeColumnsToContents ()
        self.errorView.selectionModel().selectionChanged.connect(self.errorSelectionChanged)
        
        self.resetErrorLayers()

    def errorSelectionChanged(self, selected, deselected ):
        self.errorZoomButton.setEnabled( False) 
        if self.errorHighlight:
            del self.errorHighlight
            self.errorHighlight = None

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

    def getSelectedError(self):
        sm = self.errorView.selectionModel()
        if not sm.hasSelection(): return None
        index = sm.selection().indexes()[0]
        index = self.sortErrorModel.mapToSource(index)
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
        attributes = [ 
            QgsField('type', QVariant.String),
            QgsField('route', QVariant.String),
            QgsField('measure', QVariant.String),
        ]

        if not self.errorLineLayer:
            self.errorLineLayer = QgsVectorLayer('linestring', 'LRS line errors', 'memory')
            self.errorLineLayer.startEditing()
            for attribute in attributes:
                self.errorLineLayer.addAttribute( attribute )
            self.errorLineLayer.commitChanges()
            self.resetErrorLineLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorLineLayer,] )

        if not self.errorPointLayer:
            self.errorPointLayer = QgsVectorLayer('point', 'LRS point errors', 'memory')
            self.errorPointLayer.startEditing()
            for attribute in attributes:
                self.errorPointLayer.addAttribute( attribute )
            self.errorPointLayer.commitChanges()
            self.resetErrorPointLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorPointLayer,] )
   
    # reset error layers content (features)
    def resetErrorLayers(self):
        self.resetErrorPointLayer()
        self.resetErrorLineLayer()

    def resetErrorPointLayer(self):
        if not self.errorPointLayer: return
        clearLayer( self.errorPointLayer )
        errors = self.lrs.getErrors()
        self.errorPointLayer.startEditing()
        fields = self.errorPointLayer.pendingFields()
        for error in errors:
            if error.geo.wkbType() != QGis.WKBPoint: continue
            feature = QgsFeature( fields )
            feature.setGeometry( error.geo )
            feature.setAttribute( 'type', error.typeLabel() )
            feature.setAttribute( 'route', '%s' % error.routeId )
            feature.setAttribute( 'measure', error.getMeasureString() )
            self.errorPointLayer.addFeatures( [ feature ] )
        self.errorPointLayer.commitChanges()            

    def resetErrorLineLayer(self):
        if not self.errorLineLayer: return
        clearLayer( self.errorLineLayer )
        errors = self.lrs.getErrors()
        self.errorLineLayer.startEditing()
        fields = self.errorLineLayer.pendingFields()
        for error in errors:
            if error.geo.wkbType() != QGis.WKBLineString: continue
            feature = QgsFeature( fields )
            feature.setGeometry( error.geo )
            feature.setAttribute( 'type', error.typeLabel() )
            feature.setAttribute( 'route', '%s' % error.routeId )
            feature.setAttribute( 'measure', error.getMeasureString() )
            self.errorLineLayer.addFeatures( [ feature ] )
        self.errorLineLayer.commitChanges()            

    def addQualityLayer(self):
        if not self.qualityLayer:
            attributes = [ 
                QgsField('route', QVariant.String),
                QgsField('m_from', QVariant.Double),
                QgsField('m_to', QVariant.Double),
                QgsField('l', QVariant.Double),
            ]
            self.qualityLayer = QgsVectorLayer('linestring', 'LRS quality', 'memory')
            self.qualityLayer.startEditing()
            for attribute in attributes:
                self.qualityLayer.addAttribute( attribute )
            self.qualityLayer.commitChanges()
            self.resetQualityLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.qualityLayer,] )

    def resetQualityLayer(self):
        if not self.qualityLayer: return
        clearLayer( self.qualityLayer )
        segments = self.lrs.getSegments()
        self.qualityLayer.startEditing()
        fields = self.qualityLayer.pendingFields()
        for segment in segments:
            feature = QgsFeature( fields )
            feature.setGeometry( segment.geo )
            feature.setAttribute( 'route', '%s' % segment.routeId )
            feature.setAttribute( 'm_from', segment.record.milestoneFrom )
            feature.setAttribute( 'm_to', segment.record.milestoneTo )
            feature.setAttribute( 'l', segment.geo.length() )
            self.qualityLayer.addFeatures( [ feature ] )
        self.qualityLayer.commitChanges()            
            
    def layersWillBeRemoved(self, layerIdList ):
        for id in layerIdList:
            if self.errorPointLayer and self.errorPointLayer.id() == id:
                self.errorPointLayer = None
            if self.errorLineLayer and self.errorLineLayer.id() == id:
                self.errorLineLayer = None
            if self.qualityLayer and self.qualityLayer.id() == id:
                self.qualityLayer = None
            
