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
        self.errorLayer = None
        self.qualityLayer = None
        self.addErrorLayersButton.clicked.connect( self.addErrorLayers )

        # debug
        if self.genLineLayerCM.getLayer():
            self.generateLrs() # only when reloading!

    def close(self):
        print "close"
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
        self.errorPointLayer = QgsVectorLayer('point', 'LRS point errors', 'memory')
        self.errorLineLayer = QgsVectorLayer('linestring', 'LRS line errors', 'memory')
        self.errorPointLayer.startEditing()
        self.errorLineLayer.startEditing()
        for attribute in attributes:
            self.errorPointLayer.addAttribute( attribute )
            self.errorLineLayer.addAttribute( attribute )
        self.errorPointLayer.commitChanges()
        self.errorLineLayer.commitChanges()

        self.resetErrorLayers()
        QgsMapLayerRegistry.instance().addMapLayers( [self.errorLineLayer,self.errorPointLayer,] )
   
    # reset error layers content (features)
    def resetErrorLayers(self):
        if not self.errorPointLayer and not self.errorLineLayer: return

        errors = self.lrs.getErrors()

        if self.errorPointLayer:
            clearLayer( self.errorPointLayer )
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

        if self.errorLineLayer:
            clearLayer( self.errorLineLayer )
            self.errorLineLayer.startEditing()
        
            fields = self.errorPointLayer.pendingFields()
            for error in errors:
                if error.geo.wkbType() != QGis.WKBLineString: continue
                feature = QgsFeature( fields )
                feature.setGeometry( error.geo )
                feature.setAttribute( 'type', error.typeLabel() )
                feature.setAttribute( 'route', '%s' % error.routeId )
                feature.setAttribute( 'measure', error.getMeasureString() )
                self.errorLineLayer.addFeatures( [ feature ] )

            self.errorLineLayer.commitChanges()            
            
        
            
