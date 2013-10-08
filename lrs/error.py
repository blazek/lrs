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
#from PyQt4.QtGui import *
from qgis.core import *

from utils import *

# Class representing error in LRS 

class LrsError(object):

    # Error type enums
    DUPLICATE_LINE = 1
    DUPLICATE_POINT = 2
    FORK = 3 # more than 2 lines connected in one node
    ORPHAN = 4 # orphan point, no line with such routeId

    typeLabels = {
        DUPLICATE_LINE: "Duplicate line",
        DUPLICATE_POINT: "Duplicate point",
        FORK: "Fork",
        ORPHAN: 'Orphan point',
    }

    def __init__(self, type, geo, message = '' ):
        self.type = type
        self.geo = QgsGeometry(geo) # store copy of QgsGeometry
        self.message = message

    def typeLabel(self):
        if not self.typeLabels.has_key( self.type ):
            return "Unknown error"
        return self.typeLabels[ self.type ]

class LrsErrorModel( QAbstractTableModel ):
    
    def __init__(self):
        super(LrsErrorModel, self).__init__()
        self.errors = []

    def headerData( self, section, orientation, role = Qt.DisplayRole ):
        if role != Qt.DisplayRole: return None
        if orientation == Qt.Horizontal:
            if section == 0:
                return "Type"
            else:
                return "%s" % section
        else:
            return "%s" % section
    
    def rowCount(self, index):
        return len( self.errors )

    def columnCount(self, index):
        return 1

    def data(self, index, role):
        if role != Qt.DisplayRole: return None

        if index.column() == 0:
            return self.errors[index.row()].typeLabel()

        return "row %s col %s" % ( index.row(), index.column() )
        
    def addErrors ( self, errors ):
        self.errors.extend ( errors )

    def getError (self, index):
        if not index: return None
        row = index.row()
        if row < 0 or row >= len(self.errors): return None
        return self.errors[row]

