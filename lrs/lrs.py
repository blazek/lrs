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
from route import LrsRoute
from point import LrsPoint
from error import LrsError
#from line

# Main class to keep all data and process them

class Lrs:

    def __init__(self, lineLayer, lineRouteField, pointLayer, pointRouteField, pointMeasureField, **kwargs ):

        self.lineLayer = lineLayer
        self.lineRouteField = lineRouteField
        self.pointLayer = pointLayer
        self.pointRouteField = pointRouteField
        self.pointMeasureField = pointMeasureField
        # threshold - max distance between point and line in canvas CRS units
        self.threshold = kwargs.get('threshold', 10.0)
        self.lrsCrs = kwargs.get('crs')

        self.lineTransform = None
        if self.lrsCrs and self.lrsCrs != lineLayer.crs():
            self.lineTransform = QgsCoordinateTransform( lineLayer.crs(), self.lrsCrs)

        self.pointTransform = None
        if self.lrsCrs and self.lrsCrs != pointLayer.crs():
            self.pointTransform = QgsCoordinateTransform( pointLayer.crs(), self.lrsCrs)

        # dictionary of LrsRoute
        self.routes = {} 

        self.orphanPoints = []

        self.registerLines()
        self.registerPoints()

    def registerLines (self):
        feature = QgsFeature()
        iterator = self.lineLayer.getFeatures()
        while iterator.nextFeature(feature):
            routeId = feature[self.lineRouteField]
            debug ( "fid = %s routeId = %s" % ( feature.id(), routeId ) )
            if not self.routes.has_key(routeId):
                self.routes[routeId] = LrsRoute(self.lineLayer, routeId )
            route = self.routes[routeId]
            geo = feature.geometry()
            if geo:
                if self.lineTransform:
                    geo.transform( self.lineTransform )
                route.addLine ( geo ) 

        for route in self.routes.values():
            route.buildParts()

    def registerPoints (self):
        feature = QgsFeature()
        iterator = self.pointLayer.getFeatures()
        while iterator.nextFeature(feature):
            routeId = feature[self.pointRouteField]
            measure = feature[self.pointMeasureField]
            debug ( "fid = %s routeId = %s measure = %s" % ( feature.id(), routeId, measure ) )
            geo = feature.geometry()
            if geo:
                if self.pointTransform:
                    geo.transform( self.pointTransform )

            if geo.wkbType() in [ QGis.WKBPoint, QGis.WKBPoint25D]:
                pnts = [ geo.asPoint() ]
            else: # multi (makes little sense)
                pnts = geo.asMultiPoint()

            for pnt in pnts:
                point = LrsPoint( routeId, pnt, measure )
                if not self.routes.has_key(routeId):
                    self.orphanPoints.append ( point )
                else:
                    self.routes[routeId].addPoint( point )

        #for route in self.routes.values():
        #    route.buildParts()

    def getErrors(self):
        errors = []
        for route in self.routes.values():
            errors.extend( route.getErrors() )
        for point in self.orphanPoints:
            geo = QgsGeometry()
            geo.fromPoint( point.point )
            errors.append( LrsError( LrsError.ORPHAN, geo ) )    
        return errors


