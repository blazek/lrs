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
import md5

# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *

from utils import *

# Origin of geometry part used for error checksums, it allows to update errors when 
# geometry is changed, but error remains. 
# The identification by origin unfortunately fails if geometry part is deleted and thus
# geoPart numbers are changed. That is why there is also nGeoParts
class LrsOrigin(object):
    def __init__(self, geoType, fid, geoPart = -1, nGeoParts = -1 ):
        self.geoType = geoType # QGis.Point or QGis.Line
        self.fid = fid
        # geoPart and nGeoParts are -1 if the origin is full geometry, e.g. NO_ROUTE_ID
        self.geoPart = geoPart
        self.nGeoParts = nGeoParts # number of geometry parts in feature

    def getChecksum(self):
        s  = "%s-%s-%s-%s" % ( self.geoType, self.fid, self.geoPart, self.nGeoParts )
        m = md5.new( s )
        return m.digest()

# Class representing error in LRS 
class LrsError(object):

    # Error type enums
    DUPLICATE_LINE = 1
    DUPLICATE_POINT = 2
    FORK = 3 # more than 2 lines connected in one node
    ORPHAN = 4 # orphan point, no line with such routeId
    OUTSIDE_THRESHOLD = 5 # out of the threshold from line
    NOT_ENOUGH_MILESTONES = 6 # part has less than 2 milestones attached
    NO_ROUTE_ID = 7 # missing route id
    NO_MEASURE = 8 # missing point measure attribute value
    DIRECTION_GUESS = 9 # cannot guess part direction
    WRONG_MEASURE = 10 # milestones in wrong position

    typeLabels = {
        DUPLICATE_LINE: 'Duplicate line',
        DUPLICATE_POINT: 'Duplicate point',
        FORK: 'Fork',
        ORPHAN: 'Orphan point',
        OUTSIDE_THRESHOLD: 'Out of threshold',
        NOT_ENOUGH_MILESTONES: 'Not enough points',
        NO_ROUTE_ID: 'Missing route id',
        NO_MEASURE: 'Missing measure',
        DIRECTION_GUESS: 'Cannot guess direction',
        WRONG_MEASURE: 'Wrong measure',
    }

    def __init__(self, type, geo, **kwargs ):
        self.type = type
        self.geo = QgsGeometry(geo) # store copy of QgsGeometry
        self.message = kwargs.get('message', '')
        self.routeId = kwargs.get('routeId', None)
        self.measure = kwargs.get('measure', None) # may be list !
        #self.lineFid = kwargs.get('lineFid', None)
        #self.pointFid = kwargs.get('pointFid', None) # may be list !
        # multigeometry part
        #self.geoPart = kwargs.get('geoPart', None) # may be list !
        self.origins = kwargs.get('origins', []) # list of LrsOrigin

        # checksum cache
        self.originChecksum_ = None
        self.checksum_ = None
        #self.fullChecksum_ = None

    def typeLabel(self):
        if not self.typeLabels.has_key( self.type ):
            return "Unknown error"
        return self.typeLabels[ self.type ]

    # get string of simple value or list
    def getValueString(self, value ):
        if isinstance(value,list):
            vals = list ( value )
            vals.sort()
            return " ".join( map(str,vals) )
        else:
            return str( value )

    def getMeasureString(self):
        return self.getValueString ( self.measure )

    #def getPointFidString(self):
    #    return self.getValueString ( self.pointFid )

    #def getGeoPartString(self):
    #    return self.getValueString ( self.geoPart )

    def getOriginChecksum(self):
        if not self.originChecksum_:
            checksums = []
            for origin in self.origins:
                checksums.append( origin.getChecksum() )

            checksums.sort()

            m = md5.new()
            for checksum in checksums:
                m.update( checksum )
            self.originChecksum_ = m.digest()

        return self.originChecksum_

    # base checksum, mostly using origin, maybe used to update errors, 
    # calculation depends on error type
    def getChecksum(self):
        if not self.checksum_: 
            m = md5.new( "%s" % self.type )
            
            if self.type == self.DUPLICATE_LINE:
                m.update( self.geo.asWkb() )
            elif self.type == self.DUPLICATE_POINT:
                m.update( self.geo.asWkb() )
            elif self.type == self.FORK:
                m.update( '%s' % self.routeId )
                m.update( self.geo.asWkb() )
            elif self.type == self.ORPHAN:
                m.update( self.getOriginChecksum() )
            elif self.type == self.OUTSIDE_THRESHOLD:
                m.update( self.getOriginChecksum() )
            elif self.type == self.NOT_ENOUGH_MILESTONES:
                m.update( '%s' % self.routeId )
                m.update( self.getOriginChecksum() )
            elif self.type == self.NO_ROUTE_ID:
                m.update( self.getOriginChecksum() )
            elif self.type == self.NO_MEASURE:
                m.update( self.getOriginChecksum() )
            elif self.type == self.DIRECTION_GUESS:
                m.update( self.getOriginChecksum() )
            elif self.type == self.WRONG_MEASURE:
                m.update( self.getOriginChecksum() )
                 
            self.checksum_ = m.digest()
        return self.checksum_

    # full checksum
    #def getFullChecksum(self):
        #if not self.fullChecksum_: 
            #s  = "%s-%s-%s-%s-%s" % ( self.type, self.geo.asWkb(), self.routeId, self.getMeasureString(), self.getOriginChecksum() )
            #m = md5.new( s )
            #self.fullChecksum_ = m.digest()
        #return self.fullChecksum_

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
            return error.getMeasureString()
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

    def getErrorIndexForChecksum( self, checksum ):
        for i in range( len(self.errors) ):
            if self.errors[i].getChecksum() == checksum:
                return i
        return None # should not happen
        
    def rowsToBeRemoved(self, errorUpdates):
        rows = []
        for checksum in errorUpdates['removedErrorChecksums']:
            rows.append ( self.getErrorIndexForChecksum( checksum ) )
        return rows

    def updateErrors(self, errorUpdates):
        debug ( 'errorUpdates: %s' % errorUpdates ) 
        for checksum in errorUpdates['removedErrorChecksums']:
            idx = self.getErrorIndexForChecksum( checksum )
            debug ( 'remove row %s' % idx )
            self.beginRemoveRows( QModelIndex(), idx, idx )
            del self.errors[idx]
            self.endRemoveRows()
                

