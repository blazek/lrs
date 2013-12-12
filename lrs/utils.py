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
import sys, math
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *

# name of plugin in project file
PROJECT_PLUGIN_NAME = "lrs"

class LrsUnits():
    METER = 0
    KILOMETER = 1
    FEET = 2
    MILE = 3
    UNKNOWN = 4

    names = { METER: 'meter', KILOMETER: 'kilometer', FEET: 'feet', MILE: 'mile' }

    @staticmethod
    def unitName(unit):
        return LrsUnits.names.get(unit, 'unknown')

    @staticmethod
    def unitFromName(name):
        for u,n in LrsUnits.names.iteritems():
            if n == name:
                return u
        return LrsUnits.UNKNOWN

# print debug message
def debug(msg):
    print "LRSDEBUG: %s" % msg
    sys.stdout.flush()

# compare 2 doubles
def doubleNear( d1, d2 ):
    return abs(d1-d2) < 1e-10

# covert route id to lower case string
# expected types are str, int, None
def normalizeRouteId( route ):
    if route is None: return None
    if type(route) != str:
        route = str(route)
    return route.lower()
    
# print measure with decent number of decimal places (meters), 
# this is used in events error messages
#def printMeasure(measure,crs,mapUnitsPerMeasureUnit):
#   return measure 

# test if two QgsPolyline are identical including reverse order
# return False - not identical
#        True - identical
def polylinesIdentical( polyline1, polyline2 ):
    if polyline1 == polyline2: 
        return True
    
    tmp = []
    tmp.extend(polyline2)
    tmp.reverse()
    return polyline1 == tmp

# return hash of QgsPoint (may be used as key in dictionary)
def pointHash( point ):
    return "%s-%s" % ( point.x().__hash__(), point.y().__hash__() )


def convertDistanceUnits( distance, qgisUnit, lrsUnit ):
    if qgisUnit == QGis.Meters:
        if lrsUnit == LrsUnits.METER:
            return distance
        elif lrsUnit == LrsUnits.KILOMETER:
            return distance / 1000.
        elif lrsUnit == LrsUnits.FEET:
            return distance * 3.2808399
        elif lrsUnit == LrsUnits.MILE:
            return distance / 1609.344
    elif qgisUnit == QGis.Feet:
        if lrsUnit == LrsUnits.METER:
            return distance / 3.2808399
        elif lrsUnit == LrsUnits.KILOMETER:
            return distance / 3280.8399
        elif lrsUnit == LrsUnits.FEET:
            return distance
        elif lrsUnit == LrsUnits.MILE:
            return distance / 5280

    raise Exception( "Conversion from QGIS unit %s to Lrs unit %s not supported" % ( qgisUnit, lrsUnit ) )

def pointsDistance( p1, p2 ):
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    return math.sqrt( dx*dx + dy*dy)

def segmentLength( polyline, segment ):
    p1 = polyline[segment]
    p2 = polyline[segment+1]
    return pointsDistance( p1, p2 )

# calculate distance along line to pnt
def measureAlongPolyline( polyline, segment, pnt):
    measure = 0.0
    for i in range(segment):
        measure += segmentLength( polyline, i )
    
    measure += pointsDistance( polyline[segment], pnt )
    return measure


# delete all features from layer
#def clearLayer( layer ):
    #if not layer: return

    #iterator = layer.getFeatures()
    #ids = []
    #for feature in layer.getFeatures():
        #ids.append( feature.id() )

    #layer.dataProvider().deleteFeatures( ids )

# place point on line in distance from point 1
def pointOnLine( point1, point2, distance ):
    dx = point2.x() - point1.x()
    dy = point2.y() - point1.y()
    k = distance / math.sqrt(dx*dx+dy*dy)
    x = point1.x() + k * dx
    y = point1.y() + k * dy
    return QgsPoint( x, y )

# returns new QgsPoint on polyline in distance along original polyline
def polylinePoint( polyline, distance ):
    #geo = QgsGeometry.fromPolyline( polyline )
    #length = geo.length()

    length = 0
    for i in range(len(polyline)-1):
        p1 = polyline[i]
        p2 = polyline[i+1]
        l = pointsDistance( p1, p2 )

        if distance >= length and distance <= length + l:
            d = distance - length
            return pointOnLine ( p1, p2, d )
        length += l
    #debug ( 'point in distance %s not found on line length = %s' % ( distance, length ) )
    return None

# returns new polyline 'from - to' measured along original polyline
def polylineSegment( polyline, frm, to ):
    geo = QgsGeometry.fromPolyline( polyline )
    length = geo.length()

    poly = [] # section
    length = 0
    for i in range(len(polyline)-1):
        p1 = polyline[i]
        p2 = polyline[i+1]
        l = pointsDistance( p1, p2 )

        if len(poly) == 0 and frm <= length + l:
            d = frm - length
            p = pointOnLine ( p1, p2, d )
            poly.append( p )

        if len(poly) > 0:
            if to < length + l:
                d = to - length
                p = pointOnLine ( p1, p2, d )
                poly.append( p )
                break
            else:
                poly.append( p2 )

        length += l

    return poly

def getLayerFeature( layer, fid ):
    if not layer: return None

    request = QgsFeatureRequest().setFilterFid(fid)

    # StopIteration is raised if fid does not exist
    feature = layer.getFeatures(request).next()
    del request

    return feature
   
# QgsCoordinateReferenceSystem.createFromString() does not accept value from authid()
# if it is type 'USER:'
def crsString ( crs ):
    string = crs.authid()
    if not string.lower().startswith('epsg'):
        string = 'internal:%s' % crs.srsid()
    return string
