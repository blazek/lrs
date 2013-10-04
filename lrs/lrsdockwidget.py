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

from PyQt4 import QtCore, QtGui
import qgiscombomanager as cm
from qgis.core import *

from ui_lrsdockwidget import Ui_LrsDockWidget

#class LrsDockWidget(QtGui.QDockWidget):
class LrsDockWidget( QtGui.QDockWidget, Ui_LrsDockWidget ):
    def __init__( self,parent, iface ):
        self.iface = iface
        #QtGui.QDockWidget.__init__( self, parent )
        super(LrsDockWidget, self).__init__(parent )
        
        # Set up the user interface from Designer.
        self.setupUi( self )
        
        # default item does not work because in qgiscombomanager is wrong index (+1) or findData() on user data instead text 
        # TODO make pull request from fixes

        self.genLineLayerCM = cm.VectorLayerCombo( self.genLineLayerCombo, 'lines', {'geomType':QGis.Line } )
        self.genLineRouteFieldCM = cm.FieldCombo( self.genLineRouteFieldCombo, self.genLineLayerCM, 'route' )
        self.genPointLayerCM = cm.VectorLayerCombo( self.genPointLayerCombo, 'points', {'geomType':QGis.Point } )
        self.genPointRouteFieldCM = cm.FieldCombo( self.genPointRouteFieldCombo, self.genPointLayerCM, 'route' )
        # TODO: allow integers, currently only one type supported by fieldType
        # in any case fieldType does not work, also wrong index (fixed in local copy) 
        self.genPointMeasureFieldCM = cm.FieldCombo( self.genPointMeasureFieldCombo, self.genPointLayerCM, 'km', { 'fieldType':QtCore.QVariant.Double } )

    def close(self):
      # Must delete combo managers to disconnect!
      del self.genLineLayerCM
      del self.genLineRouteFieldCM
      del self.genPointLayerCM
      del self.genPointRouteFieldCM
      del self.genPointMeasureFieldCM
      super(LrsDockWidget, self).close()
        
