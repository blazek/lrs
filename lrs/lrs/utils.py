# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LRS Plugin utilities
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
import math
import sys

from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QMessageBox

from qgis.PyQt.QtCore import *
from qgis.core import *

from qgis.core import Qgis
from qgis.core import QgsWkbTypes

# name of plugin in project file
PROJECT_PLUGIN_NAME = "lrs"

# input layers selection
ALL_FEATURES = "all"
SELECTED_FEATURES = "selected"

QVARIANT_NUMBER_TYPE_LIST = [QVariant.Int, QVariant.UInt, QVariant.LongLong, QVariant.ULongLong, QVariant.Double]

class LrsUnits():
    METER = 0
    KILOMETER = 1
    FEET = 2
    MILE = 3
    UNKNOWN = 4

    names = {METER: 'meter', KILOMETER: 'kilometer', FEET: 'feet', MILE: 'mile'}

    @staticmethod
    def unitName(unit):
        return LrsUnits.names.get(unit, 'unknown')

    @staticmethod
    def unitFromName(name):
        for u, n in LrsUnits.names.items():
            if n == name:
                return u
        return LrsUnits.UNKNOWN


# print debug message
def debug(msg):
    print("LRSDEBUG: %s" % msg)
    # sys.stdout.flush()  # gives error on Windows if Python console is not open
    QgsMessageLog.logMessage(msg, 'LRS Plugin', Qgis.Info)


# compare 2 doubles
def doubleNear(d1, d2):
    return abs(d1 - d2) < 1e-10


# covert route id to lower case string
# expected types are str, int, double, None
# TODO: float
def normalizeRouteId(route):
    if route is None: return None
    if type(route) != str:
        if type(route) == float:  # could be integer, try round
            if int(route) == route:
                route = int(route)
        route = str(route)
    return route.lower()


# print measure with decent number of decimal places (meters), 
# this is used in events error messages
def formatMeasure(measure, measureUnit):
    if measureUnit == LrsUnits.METER:
        return "%d" % measure
    elif measureUnit == LrsUnits.KILOMETER:
        return "%.3f" % measure
    elif measureUnit == LrsUnits.FEET:
        return "%d" % measure
    elif measureUnit == LrsUnits.MILE:
        return "%.3f" % measure

    return "%s" % measure


# test if two QgsPolyline are identical including reverse order
# return False - not identical
#        True - identical
def polylinesIdentical(polyline1, polyline2):
    if polyline1 == polyline2:
        return True

    tmp = []
    tmp.extend(polyline2)
    tmp.reverse()
    return polyline1 == tmp


# return hash of QgsPointXY (may be used as key in dictionary)
def pointHash(point):
    return "%s-%s" % (point.x().__hash__(), point.y().__hash__())


def convertDistanceUnits(distance, qgisUnit, lrsUnit):
    if qgisUnit == QgsUnitTypes.DistanceMeters:
        if lrsUnit == LrsUnits.METER:
            return distance
        elif lrsUnit == LrsUnits.KILOMETER:
            return distance / 1000.
        elif lrsUnit == LrsUnits.FEET:
            return distance * 3.2808399
        elif lrsUnit == LrsUnits.MILE:
            return distance / 1609.344
    elif qgisUnit == QgsUnitTypes.DistanceFeet:
        if lrsUnit == LrsUnits.METER:
            return distance / 3.2808399
        elif lrsUnit == LrsUnits.KILOMETER:
            return distance / 3280.8399
        elif lrsUnit == LrsUnits.FEET:
            return distance
        elif lrsUnit == LrsUnits.MILE:
            return distance / 5280

    raise Exception("Conversion from QGIS unit %s to Lrs unit %s not supported" % (qgisUnit, lrsUnit))


def pointsDistance(p1, p2):
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    return math.sqrt(dx * dx + dy * dy)


def segmentLength(polyline, segment):
    p1 = polyline[segment]
    p2 = polyline[segment + 1]
    return pointsDistance(p1, p2)


# calculate distance along line to pnt
def measureAlongPolyline(polyline, segment, pnt):
    measure = 0.0
    for i in range(segment):
        measure += segmentLength(polyline, i)

    measure += pointsDistance(polyline[segment], pnt)
    return measure


# delete all features from layer
# def clearLayer( layer ):
# if not layer: return

# iterator = layer.getFeatures()
# ids = []
# for feature in layer.getFeatures():
# ids.append( feature.id() )

# layer.dataProvider().deleteFeatures( ids )

# compute offset pt
def offsetPt(point1, point2, offset=0.0):
    dx = math.fabs(point2.x() - point1.x())
    dy = math.fabs(point2.y() - point1.y())
    a = math.atan(math.fabs(dy) / math.fabs(dx))
    #a = math.atan2(dy, dx) - math.pi/2
    offset = offset or 0.0
    dxo = offset * math.fabs(math.sin(a))
    dyo = offset * math.fabs(math.cos(a))
    #debug("dx = %s dy = %s !" % (dx, dy))
    #debug("dxo = %s dyo = %s !" % (dxo, dyo))
    if point2.x() >= point1.x() and point2.y() >= point1.y(): # Quadrant 1
        x = point2.x() + dxo
        y = point2.y() - dyo
    elif point2.x() < point1.x() and point2.y() >= point1.y(): # Quadrant 2
        x = point2.x() + dxo
        y = point2.y() + dyo
    elif point2.x() < point1.x() and point2.y() < point1.y(): # Quadrant 3
        x = point2.x() - dxo
        y = point2.y() + dyo
    elif point2.x() >= point1.x() and point2.y() < point1.y(): # Quadrant 4
        x = point2.x() - dxo
        y = point2.y() - dyo
    return QgsPointXY(x, y)

# place point on line in distance from point 1 with offset o
def pointXYOnLine(point1, point2, distance, o=0.0):
    #debug("pointOnLine distance = %s" % distance)
    dx = point2.x() - point1.x()
    dy = point2.y() - point1.y()
    # this gives exception if point1 and point2 have the same coordinate, but duplicate coordinates 
    # clean up was added in LrsRoute.buildParts so that it should no more happen
    k = distance / math.sqrt(dx * dx + dy * dy)
    #debug("pointOnLine k = %s" % k)

    x = point1.x() + k * dx
    y = point1.y() + k * dy

    # Calcul du décalage
    if o != 0.0:
        pt = offsetPt(point1, QgsPointXY(x, y), o)
    else:
        pt = QgsPointXY(x, y)

    #return QgsPointXY(x, y)
    return pt

# place point on line in distance from point 1
def pointXYOnLine_sav(point1, point2, distance):
    #debug("pointOnLine distance = %s" % distance)
    dx = point2.x() - point1.x()
    dy = point2.y() - point1.y()
    # this gives exception if point1 and point2 have the same coordinate, but duplicate coordinates 
    # clean up was added in LrsRoute.buildParts so that it should no more happen
    k = distance / math.sqrt(dx * dx + dy * dy)
    #debug("pointOnLine k = %s" % k)
    x = point1.x() + k * dx
    y = point1.y() + k * dy
    return QgsPointXY(x, y)


# returns new QgsPointXY on polyline in distance along polyline
def polylineXYPointXY(polyline, distance):
    # debug( "polylinePoint distance = %s" % distance )
    # geo = QgsGeometry.fromPolyline( polyline )
    # length = geo.length()

    length = 0
    for i in range(len(polyline) - 1):
        p1 = polyline[i]
        p2 = polyline[i + 1]
        l = pointsDistance(p1, p2)

        if length <= distance <= length + l:
            d = distance - length
            return pointXYOnLine(p1, p2, d)
        length += l
    # debug ( 'point in distance %s not found on line length = %s' % ( distance, length ) )
    return None


# returns new polyline 'from - to' measured along original polyline
def polylineXYSegmentXY(polylineXY, frm, to, oStart=0.0, oEnd=0.0):
    # debug('offset %s' % oStart)
    geo = QgsGeometry.fromPolylineXY(polylineXY)
    length = geo.length()

    poly = []  # section
    length = 0
    for i in range(len(polylineXY) - 1):
        p1 = polylineXY[i]
        p2 = polylineXY[i + 1]
        l = pointsDistance(p1, p2)

        if len(poly) == 0 and frm <= length + l:
            d = frm - length
            p = pointXYOnLine(p1, p2, d, oStart)
            poly.append(p)

        if len(poly) > 0:
            if to < length + l:
                d = to - length
                p = pointXYOnLine(p1, p2, d, oEnd)
                poly.append(p)
                break
            else:
                poly.append(p2)

        length += l

    return poly


def getLayerFeature(layer, fid):
    if not layer: return None

    request = QgsFeatureRequest().setFilterFid(fid)

    # StopIteration is raised if fid does not exist
    feature = QgsFeature()
    layer.getFeatures(request).nextFeature(feature)
    del request

    return feature


# QgsCoordinateReferenceSystem.createFromString() does not accept value from authid()
# if it is type 'USER:'
def crsString(crs):
    crs_string = crs.authid()
    if not crs_string.lower().startswith('epsg'):
        crs_string = 'internal:%s' % crs.srsid()
    return crs_string


def isProjectCrsEnabled():
    return QgsProject().instance().crs().isValid()


def getProjectCrs():
    return QgsProject().instance().crs()


# Because memory provider (QGIS 2.4) fails to parse PostGIS type names (like int8, float, float8 ...)
# and negative length and precision we overwrite type names according to types and reset length and precision
def fixFields(fieldsList):
    for field in fieldsList:
        #debug("fixFields %s %s %s" % (field.name(), field.typeName(), QVariant.typeToName(field.type())))
        if field.type() == QVariant.String:
            field.setTypeName('string')
        elif field.type() == QVariant.UInt:
            field.setTypeName('int')
        elif field.type() == QVariant.Int:
            field.setTypeName('int')
        elif field.type() == QVariant.LongLong:
            field.setTypeName('int8')
        elif field.type() == QVariant.ULongLong:
            field.setTypeName('int8')
        elif field.type() == QVariant.Double:
            field.setTypeName('double')

        if field.length() < 0:
            field.setLength(0)

        if field.precision() < 0:
            field.setPrecision(0)

        #debug("fixFields %s" % (field.typeName()))


# Check if all attributes were parsed correctly, memory provider may fail to parse attribute
# types and adds names including types in such case
def checkFields(inputLayer, outputLayer):
    missingFields = []
    for field in inputLayer.fields():
        if outputLayer.fields().indexFromName(field.name()) < 0:
            missingFields.append(field.name())

    if missingFields:
        QMessageBox.information(None, 'Information',
                                'Could not copy field %s. The type is not probably supported by memory provider, try to change field type.' % " ".join(
                                    missingFields))

