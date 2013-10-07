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
        self.genPointMeasureFieldCM = cm.FieldCombo( self.genPointMeasureFieldCombo, self.genPointLayerCM, 'km', { 'fieldType':QVariant.Double } )

        self.genButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.generateLrs)

        ##### errorTab
        self.errorModel = None

        # debug
        self.generateLrs()

    def close(self):
        # Must delete combo managers to disconnect!
        del self.genLineLayerCM
        del self.genLineRouteFieldCM
        del self.genPointLayerCM
        del self.genPointRouteFieldCM
        del self.genPointMeasureFieldCM
        super(LrsDockWidget, self).close()

    def generateLrs(self):
        debug ( 'generateLrs')
        self.lrs = Lrs ( self.genLineLayerCM.getLayer(), self.genLineRouteFieldCM.getFieldName(), self.genPointLayerCM.getLayer(), self.genPointRouteFieldCM.getFieldName(), self.genPointMeasureFieldCM.getFieldName(), crs = self.lrsCrs, threshold = 10.0 )
    
        self.errorModel = LrsErrorModel()

        self.errorModel.addErrors( self.lrs.getErrors() )

        self.sortErrorModel = QSortFilterProxyModel()
        self.sortErrorModel.setSourceModel( self.errorModel )
        self.errorView.setModel( self.sortErrorModel )
 
