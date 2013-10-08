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
        #QtGui.QDockWidget.__init__( self, parent )
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
        self.lrs = Lrs ( self.genLineLayerCM.getLayer(), self.genLineRouteFieldCM.getFieldName(), self.genPointLayerCM.getLayer(), self.genPointRouteFieldCM.getFieldName(), self.genPointMeasureFieldCM.getFieldName(), crs = self.lrsCrs, threshold = 10.0 )
    
        self.errorModel = LrsErrorModel()

        self.errorModel.addErrors( self.lrs.getErrors() )

        self.sortErrorModel = QSortFilterProxyModel()
        self.sortErrorModel.setSourceModel( self.errorModel )
         
        self.errorView.setModel( self.sortErrorModel )
        self.errorView.resizeColumnsToContents ()
        self.errorView.selectionModel().selectionChanged.connect(self.errorSelectionChanged)

    def errorSelectionChanged(self, selected, deselected ):
        self.errorZoomButton.setEnabled( False) 
        if self.errorHighlight:
            del self.errorHighlight
            self.errorHighlight = None

        #if len( selected.indexes() ) == 0: return
        #index = selected.indexes()[0]
        #index = self.sortErrorModel.mapToSource( index)
        #error = self.errorModel.getError(indexndex)
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
