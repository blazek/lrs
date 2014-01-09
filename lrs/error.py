# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsError
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
from qgis.gui import *

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
    DUPLICATE_REFERENCING = 11 # multiple route segments measures overlap
    PARALLEL = 12 # parallel line
    FORK_LINE = 13 # parts connected in fork

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
        DUPLICATE_REFERENCING: 'Duplicate referencing',
        PARALLEL: 'Parallel line',
        FORK_LINE: 'Fork line',
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
        if value == None:
            return ""
        elif isinstance(value,list):
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
            elif self.type == self.DUPLICATE_REFERENCING:
                m.update( '%s' % self.routeId )
                m.update( self.geo.asWkb() )
                m.update( self.getMeasureString() )
            elif self.type == self.PARALLEL:
                m.update( self.getOriginChecksum() )
            elif self.type == self.FORK_LINE:
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
    MESSAGE_COL = 3 # currently not used

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
        if not Qt or role != Qt.DisplayRole: return None
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
        return 3

    def data(self, index, role):
        if role != Qt.DisplayRole: return None

        error = self.getError(index)
        if not error: return

        col = index.column()
        value = ""
        if col == self.TYPE_COL:
            value = error.typeLabel()
        elif col == self.ROUTE_COL:
            value = "%s" % error.routeId
        elif col == self.MEASURE_COL:
            value = error.getMeasureString()
        elif col == self.MESSAGE_COL:
            value = error.message

        #return "row %s col %s" % ( index.row(), index.column() )
        return value
        
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
        #debug ( 'errorUpdates: %s' % errorUpdates ) 
        for checksum in errorUpdates['removedErrorChecksums']:
            idx = self.getErrorIndexForChecksum( checksum )
            #debug ( 'remove row %s' % idx )
            self.beginRemoveRows( QModelIndex(), idx, idx )
            del self.errors[idx]
            self.endRemoveRows()

        for error in errorUpdates['updatedErrors']:
            checksum = error.getChecksum() 
            idx = self.getErrorIndexForChecksum( checksum )
            #debug ( 'update row %s' % idx )
            self.errors[idx] = error
            topLeft = self.createIndex( idx, 0 )
            bottomRight = self.createIndex( idx, 3 )
            self.dataChanged.emit( topLeft, bottomRight )

        for error in errorUpdates['addedErrors']:
            #debug ( 'add row' )
            idx = len ( self.errors )
            self.beginInsertRows( QModelIndex(), idx, idx )
            self.errors.append ( error )
            self.endInsertRows()


class LrsFeature(QgsFeature):

    def __init__(self, fields ):
        super(LrsFeature, self).__init__(fields)

    def getAttributeMap(self):
        attributeMap = {}
        for i in range(len(self.fields())):
            name = self.fields()[i].name()
            attributeMap[i] = self.attribute( name )
        return attributeMap

class LrsErrorFields(QgsFields):

    def __init__(self):
        super(LrsErrorFields, self).__init__()

        fields = [
            QgsField('error', QVariant.String, "string"), # error type, avoid 'type' which could be keyword
            QgsField('route', QVariant.String, "string" ),
            QgsField('measure', QVariant.String, "string"),
        ]

        for field in fields:
            self.append(field)

LRS_ERROR_FIELDS = LrsErrorFields()

class LrsErrorFeature(LrsFeature):

    def __init__(self, error ):
        super(LrsErrorFeature, self).__init__( LRS_ERROR_FIELDS )
        error = error
        self.setGeometry( error.geo )
        self.checksum = error.getChecksum()

        values = {
            'error': error.typeLabel(),
            'route': '%s' % error.routeId,
            'measure': error.getMeasureString()
        }   
        for name, value in values.iteritems():
            self.setAttribute( name, value )
    
    def getChecksum(self):
        return self.checksum


class LrsQualityFields(QgsFields):

    def __init__(self):
        super(LrsQualityFields, self).__init__()

        fields = [
            QgsField('route', QVariant.String, "string"),
            QgsField('m_from', QVariant.Double, "double"),
            QgsField('m_to', QVariant.Double, "double"),
            QgsField('m_len', QVariant.Double, "double"),
            QgsField('len', QVariant.Double, "double"),
            QgsField('err_abs', QVariant.Double, "double"),
            QgsField('err_rel', QVariant.Double, "double"),
            QgsField('err_perc', QVariant.Double, "double"), # relative in percents
        ]
        for field in fields:
            self.append(field)

LRS_QUALITY_FIELDS = LrsQualityFields()

class LrsQualityFeature(LrsFeature):

    def __init__(self):
        super(LrsQualityFeature, self).__init__( LRS_QUALITY_FIELDS )
        self.checksum_ = None
    
    # full checksum, cannot be used to update existing feature because contains
    # geometry + all attributes
    def getChecksum(self):
        if not self.checksum_:
            m = md5.new( "%s" % self.geometry().asWkb() )
           
            for attribute in self.attributes():
                m.update( '%s' % attribute )
                 
            self.checksum_ = m.digest()
        return self.checksum_

# Highlight, zoom errors
class LrsErrorVisualizer(object):

    def __init__(self, mapCanvas ):
        self.errorHighlight = None
        self.mapCanvas = mapCanvas
        

    def __del__(self):
        if self.errorHighlight:
            del self.errorHighlight 

    def clearHighlight(self):
        if self.errorHighlight:
            del self.errorHighlight
            self.errorHighlight = None

    def highlight(self, error, crs):
        self.clearHighlight()
        if not error: return

        # QgsHighlight does reprojection from layer CRS
        layer = QgsVectorLayer( 'Point?crs=' + crsString( crs ), 'LRS error highlight', 'memory' )   
        self.errorHighlight = QgsHighlight( self.mapCanvas, error.geo, layer )
        # highlight point size is hardcoded in QgsHighlight
        self.errorHighlight.setWidth( 2 )
        self.errorHighlight.setColor( Qt.yellow )
        self.errorHighlight.show()

    def zoom(self, error, crs):
        if not error: return
        geo = error.geo
        mapRenderer = self.mapCanvas.mapRenderer()
        if mapRenderer.hasCrsTransformEnabled() and mapRenderer.destinationCrs() != crs:
            geo = QgsGeometry( error.geo )
            transform = QgsCoordinateTransform( crs, mapRenderer.destinationCrs() )
            geo.transform( transform )

        if geo.wkbType() == QGis.WKBPoint:
            p = geo.asPoint()
            bufferCrs = mapRenderer.destinationCrs() if mapRenderer.hasCrsTransformEnabled() else crs
            b = 2000 if not bufferCrs.geographicFlag() else 2000/100000  # buffer
            extent = QgsRectangle(p.x()-b, p.y()-b, p.x()+b, p.y()+b)
        else: #line
            extent = geo.boundingBox()
            extent.scale(2)
        self.mapCanvas.setExtent( extent )
        self.mapCanvas.refresh();

