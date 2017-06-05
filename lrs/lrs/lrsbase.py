# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsPlugin
                                 A QGIS plugin
 Linear reference system builder and editor
                              -------------------
        begin                : 2017-5-29
        copyright            : (C) 2017 by Radim Blažek
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

from .error.lrserror import *


# Base class for Lrs and LrsLayer
class LrsBase(QObject):
    def __init__(self, **kwargs):
        super(LrsBase, self).__init__()
        self.lineLayer = None
        self.crs = None
        # dictionary of LrsRoute, key is normalized route id
        self.routes = {}  # LrsRoutBase subclasses
        # self.mapUnitsPerMeasureUnit = kwargs.get('mapUnitsPerMeasureUnit',1000.0)
        self.measureUnit = kwargs.get('measureUnit', LrsUnits.UNKNOWN)
        # LrsLayer has LrsUnits.UNKNOWN, there is no such info available
        #if self.measureUnit == LrsUnits.UNKNOWN:
        #    raise Exception("measureUnit not set")

        self.partSpatialIndex = None
        self.partSpatialIndexRoutePart = None

    # get route by id if exists otherwise returns None
    # routeId does not have to be normalized
    def getRouteIfExists(self, routeId):
        normalId = normalizeRouteId(routeId)
        if not normalId in self.routes:
            return None
        return self.routes[normalId]

    # get list of available measures ( (from, to),.. )
    def getRouteMeasureRanges(self, routeId):
        routeId = normalizeRouteId(routeId)
        if routeId not in self.routes:
            return []
        return self.routes[routeId].getMeasureRanges()

    # tolerance - maximum accepted measure from start to nearest existing lrs if exact start measure was not found
    # returns ( QgsPoint, error )
    def eventPoint(self, routeId, start, tolerance=0):
        error = self.eventValuesError(routeId, start)
        if error: return None, error

        route = self.getRoute(routeId)
        geo, error = route.eventPoint(start, tolerance)
        return geo, error

    # tolerance - minimum missing gap which will be reported as error
    # returns ( QgsMultiPolyline, error )
    def eventMultiPolyLine(self, routeId, start, end, tolerance=0):
        error = self.eventValuesError(routeId, start, end, True)
        if error: return None, error

        route = self.getRoute(routeId)
        geo, error = route.eventMultiPolyLine(start, end, tolerance)
        return geo, error

    # ------------------- EVENTS -------------------

    def eventValuesError(self, routeId, start, end=None, linear=False):
        error = None
        missing = []
        if routeId is None: missing.append('route')
        if start is None: missing.append('start measure')
        if linear and end is None: missing.append('end measure')

        if missing:
            error = 'missing %s value' % ' and '.join(missing)

        route = self.getRouteIfExists(routeId)
        if not route:
            error = error + ', ' if error else ''
            error += 'route not available'

        return error

    # ------------------- MEASURE -------------------

    def deletePartSpatialIndex(self):
        if self.partSpatialIndex:
            del self.partSpatialIndex
        self.partSpatialIndex = None
        self.partSpatialIndexRoutePart = None

    def createPartSpatialIndex(self):
        self.deletePartSpatialIndex()
        self.partSpatialIndex = QgsSpatialIndex()
        self.partSpatialIndexRoutePart = {}
        fid = 1
        for route in self.routes.values():
            for i in range(len(route.parts)):
                feature = QgsFeature(fid)
                geo = QgsGeometry.fromPolyline(route.parts[i].polyline)
                feature.setGeometry(geo)
                self.partSpatialIndex.insertFeature(feature)
                self.partSpatialIndexRoutePart[fid] = [route.routeId, i]
                fid += 1

    # returns nearest routeId, partIdx within threshold
    def nearestRoutePart(self, point, threshold):
        if not self.partSpatialIndex:
            self.createPartSpatialIndex()
        rect = QgsRectangle(point.x() - threshold, point.y() - threshold, point.x() + threshold, point.y() + threshold)
        ids = self.partSpatialIndex.intersects(rect)
        # debug ( '%s' % ids )
        nearestRouteId = None
        nearestPartIdx = None
        nearestDist = sys.float_info.max
        for id in ids:
            routeId, partIdx = self.partSpatialIndexRoutePart[id]
            route = self.getRoute(routeId)
            part = route.parts[partIdx]
            geo = QgsGeometry.fromPolyline(part.polyline)
            (sqDist, nearestPnt, afterVertex) = geo.closestSegmentWithContext(point)
            dist = math.sqrt(sqDist)
            if dist < nearestDist:
                nearestDist = dist
                nearestRouteId = routeId
                nearestPartIdx = partIdx

        if nearestDist <= threshold:
            return nearestRouteId, nearestPartIdx

        return None, None

    # return routeId, measure
    # Note: it may happen that nearest point (projected) has no record on part,
    # in that case is returned None even if another record may be in threshold,
    # this is currently feature
    # TODO: search for nearest available referenced segments (records) instead
    # of part polylines?
    def pointMeasure(self, point, threshold):
        routeId, partIdx = self.nearestRoutePart(point, threshold)
        if routeId is not None and partIdx is not None:
            route = self.getRoute(routeId)
            part = route.parts[partIdx]
            measure = part.pointMeasure(point)
            if measure is not None:
                return routeId, measure

        return routeId, None