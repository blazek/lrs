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
from line import LrsLine
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

        self.pointLayer.editingStarted.connect( self.pointLayerEditingStarted )
        self.pointLayer.editingStopped.connect( self.pointLayerEditingStopped )
        self.pointEditBuffer = None


        self.errors = [] # LrsError list

        self.lineTransform = None
        if self.lrsCrs and self.lrsCrs != lineLayer.crs():
            self.lineTransform = QgsCoordinateTransform( lineLayer.crs(), self.lrsCrs)

        self.pointTransform = None
        if self.lrsCrs and self.lrsCrs != pointLayer.crs():
            self.pointTransform = QgsCoordinateTransform( pointLayer.crs(), self.lrsCrs)

        # dictionary of LrsRoute
        self.routes = {} 

        self.orphanPoints = [] # LrsPoint list

        self.pointRoutes = {} # dict of LrsRoutes with point fid as keys

        self.calibrate()

    def disconnect(self):
        self.pointLayerEditingDisconnect()

    def calibrate(self):
        self.errors = [] # reset
        self.registerLines()
        self.registerPoints()
        for route in self.routes.values():
            route.calibrate()

    def registerLines (self):
        self.routes = {}
        feature = QgsFeature()
        iterator = self.lineLayer.getFeatures()
        while iterator.nextFeature(feature):
            routeId = feature[self.lineRouteField]
            debug ( "fid = %s routeId = %s" % ( feature.id(), routeId ) )
            geo = feature.geometry()
            if geo:
                if self.lineTransform:
                    geo.transform( self.lineTransform )

            if routeId == None or routeId == '':
                self.errors.append( LrsError( LrsError.NO_ROUTE_ID, geo, lineFid = feature.id() ) )
                continue

            if not self.routes.has_key(routeId):
                self.routes[routeId] = LrsRoute(self.lineLayer, routeId, self.threshold )
            route = self.routes[routeId]
            if geo:
                route.addLine ( LrsLine( feature.id(), routeId, geo ) ) 

        for route in self.routes.values():
            route.buildParts()

    def registerPoints (self):
        feature = QgsFeature()
        iterator = self.pointLayer.getFeatures()
        while iterator.nextFeature(feature):
            self.registerPoint ( feature )

    # returns LrsPoint
    def registerPoint (self, feature):
            routeId = feature[self.pointRouteField]
            measure = feature[self.pointMeasureField]
            debug ( "fid = %s routeId = %s measure = %s" % ( feature.id(), routeId, measure ) )
            geo = feature.geometry()
            if geo:
                if self.pointTransform:
                    geo.transform( self.pointTransform )

            if routeId == None or routeId == '':
                self.errors.append( LrsError( LrsError.NO_ROUTE_ID, geo, pointFid = feature.id() ) )
                return None

            if measure == None:
                self.errors.append( LrsError( LrsError.NO_MEASURE, geo, pointFid = feature.id() ) )
                return None

            point = LrsPoint( feature.id(), routeId, measure, geo )
            if not self.routes.has_key(routeId):
                self.orphanPoints.append ( point )
            else:
                self.routes[routeId].addPoint( point )
                self.pointRoutes[ feature.id() ] = self.routes[routeId]
                
            return point

    def getErrors(self):
        errors = list ( self.errors )
        for route in self.routes.values():
            errors.extend( route.getErrors() )
        for point in self.orphanPoints:
            errors.append( LrsError( LrsError.ORPHAN, point.geo, routeId = point.routeId, measure = point.measure, pointFid = point.fid ) )
        return errors

    def getSegments(self):
        segments = []
        for route in self.routes.values():
            segments.extend( route.getSegments() )
        return segments

    ################## Editing ##################
    def pointLayerEditingStarted(self):
        self.pointEditBuffer = self.pointLayer.editBuffer()
        self.pointEditBuffer.featureAdded.connect( self.pointFeatureAdded )
        self.pointEditBuffer.featureDeleted.connect( self.pointFeatureDeleted )

    def pointLayerEditingStopped(self):
        self.pointEditBuffer = None

    def pointLayerEditingDisconnect(self):
        if self.pointEditBuffer:
            self.pointEditBuffer.featureAdded.disconnect( self.pointFeatureAdded )
            self.pointEditBuffer.featureDeleted.disconnect( self.pointFeatureDeleted )

    # Warning: featureAdded is called first with temporary (negative fid)
    # then, when changes are commited, featureDeleted is called with that 
    # temporary id and featureAdded with real new id,
    # if changes are rollbacked, only featureDeleted is called

    def pointFeatureAdded( self, fid ):
        # added features have temporary negative id
        debug ( "feature added fid %s" % fid )
        feature = getLayerFeature( self.pointLayer, fid )
        point = self.registerPoint ( feature ) # returns LrsPoint or None
        if point and self.routes.has_key( point.routeId ):
            self.routes[point.routeId].calibrate()

    def pointFeatureDeleted( self, fid ):
        debug ( "feature deleted fid %s" % fid )
        # deleted feature cannot be read anymore from layer
        route = self.pointRoutes.get(fid)
        if route:
            route.removePoint( fid )
            route.calibrate()
        else:
            # TODO: orphan
            pass
            
