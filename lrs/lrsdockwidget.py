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
class LrsDockWidget(QtGui.QDockWidget,Ui_LrsDockWidget):
    def __init__(self,parent,iface):
        self.iface = iface
        QtGui.QDockWidget.__init__(self,parent)
        
        # Set up the user interface from Designer.
        #self.ui = Ui_LrsDockWidget()
        #self.ui.setupUi(self)
        self.setupUi(self)

        self.genLinesLayerComboManager = cm.VectorLayerCombo(self.genLineLayerCombo, '', {'geomType':QGis.Line } )
        
