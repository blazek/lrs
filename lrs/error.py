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

    def __init__(self, type, geo, **kwargs ):
        self.type = type
        self.geo = QgsGeometry(geo) # store copy of QgsGeometry
        self.message = kwargs.get('message', '')
        self.routeId = kwargs.get('routeId', None)
        self.measure = kwargs.get('measure', None) # may be list !

    def typeLabel(self):
        if not self.typeLabels.has_key( self.type ):
            return "Unknown error"
        return self.typeLabels[ self.type ]

class LrsErrorModel( QAbstractTableModel ):
    
    TYPE_COL = 0
    ROUTE_COL = 1
    MEASURE_COL = 2
    MESSAGE_COL = 3

    headerLabels = {
        TYPE_COL: 'Type',
        ROUTE_COL: 'Route',
        MEASURE_COL: 'Measure',
        MESSAGE_COL: 'Message',
    }

    def __init__(self):
        super(LrsErrorModel, self).__init__()
        self.errors = []

    def headerData( self, section, orientation, role = Qt.DisplayRole ):
        if role != Qt.DisplayRole: return None
        if orientation == Qt.Horizontal:
            if self.headerLabels.has_key(section):
                return self.headerLabels[section]
            else:
                return ""
        else:
            return "%s" % section
    
    def rowCount(self, index):
        return len( self.errors )

    def columnCount(self, index):
        return 4

    def data(self, index, role):
        if role != Qt.DisplayRole: return None

        error = self.getError(index)
        if not error: return

        col = index.column()
        if col == self.TYPE_COL:
            return error.typeLabel()
        elif col == self.ROUTE_COL:
            return error.routeId
        elif col == self.MEASURE_COL:
            if isinstance(error.measure,list):
                errors = list ( error.measure )
                errors.sort()
                return " ".join( map(str,errors) )
            else:
                return error.measure
        elif col == self.MESSAGE_COL:
            return error.message

        #return "row %s col %s" % ( index.row(), index.column() )
        return ""
        
    def addErrors ( self, errors ):
        self.errors.extend ( errors )

    def getError (self, index):
        if not index: return None
        row = index.row()
        if row < 0 or row >= len(self.errors): return None
        return self.errors[row]

