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
from error import *
#from line

# Main class to keep all data and process them

class Lrs(QObject):
    updateErrors = pyqtSignal(dict, name = 'updateErrors')

    def __init__(self, lineLayer, lineRouteField, pointLayer, pointRouteField, pointMeasureField, **kwargs ):
        super(Lrs, self).__init__()

        self.lineLayer = lineLayer
        self.lineRouteField = lineRouteField
        self.pointLayer = pointLayer
        self.pointRouteField = pointRouteField
        self.pointMeasureField = pointMeasureField
        # threshold - max distance between point and line in canvas CRS units
        self.threshold = kwargs.get('threshold', 10.0)
        self.mapUnitsPerMeasureUnit = kwargs.get('mapUnitsPerMeasureUnit',1000.0)
        self.lrsCrs = kwargs.get('crs')

        self.pointLayer.editingStarted.connect( self.pointLayerEditingStarted )
        self.pointLayer.editingStopped.connect( self.pointLayerEditingStopped )
        self.pointEditBuffer = None
        self.lineLayer.editingStarted.connect( self.lineLayerEditingStarted )
        self.lineLayer.editingStopped.connect( self.lineLayerEditingStopped )
        self.lineEditBuffer = None

        self.lines = {} # dict of LrsLine with fid as key
        self.points = {} # dict of LrsPoint with fid as key

        self.errors = [] # LrsError list

        self.lineTransform = None
        if self.lrsCrs and self.lrsCrs != lineLayer.crs():
            self.lineTransform = QgsCoordinateTransform( lineLayer.crs(), self.lrsCrs)

        self.pointTransform = None
        if self.lrsCrs and self.lrsCrs != pointLayer.crs():
            self.pointTransform = QgsCoordinateTransform( pointLayer.crs(), self.lrsCrs)

        # dictionary of LrsRoute
        self.routes = {} 

        self.calibrate()


    def disconnect(self):
        self.pointLayerEditingDisconnect()
        self.lineLayerEditingDisconnect()

    def calibrate(self):
        self.points = {}
        self.lines = {} 
        self.errors = [] # reset
        self.registerLines()
        self.buildParts()
        self.registerPoints()
        for route in self.routes.values():
            route.calibrate()

    def buildParts(self):
        for route in self.routes.values():
            route.buildParts()

    # get route by id, create it if does not exist
    def getRoute(self, routeId):
        if not self.routes.has_key(routeId):
            self.routes[routeId] = LrsRoute(self.lineLayer, routeId, self.threshold )
        return self.routes[routeId]

    ####### register / unregister features

    def registerLineFeature (self, feature):
        routeId = feature[self.lineRouteField]
        if routeId == '' or routeId == NULL: routeId = None
        #debug ( "fid = %s routeId = %s" % ( feature.id(), routeId ) )

        geo = feature.geometry()
        if geo:
            if self.lineTransform:
                geo.transform( self.lineTransform )

        route = self.getRoute( routeId )
        line = LrsLine( feature.id(), routeId, geo )
        self.lines[feature.id()] = line
        route.addLine ( line ) 
        return line

    def unregisterLineByFid(self, fid ):
        line = self.lines[fid]
        route = self.getRoute( line.routeId )
        route.removeLine( fid )
        del self.lines[fid]

    def registerLines (self):
        self.routes = {}
        feature = QgsFeature()
        iterator = self.lineLayer.getFeatures()
        while iterator.nextFeature(feature):
            self.registerLineFeature(feature)

    # returns LrsPoint
    def registerPointFeature (self, feature):
        routeId = feature[self.pointRouteField]
        if routeId == '' or routeId == NULL: routeId = None
        measure = feature[self.pointMeasureField]
        if measure == NULL: measure = None
        #debug ( "fid = %s routeId = %s measure = %s" % ( feature.id(), routeId, measure ) )
        geo = feature.geometry()
        if geo:
            if self.pointTransform:
                geo.transform( self.pointTransform )

        point = LrsPoint( feature.id(), routeId, measure, geo )
        self.points[feature.id()] = point
        route = self.getRoute( routeId )
        route.addPoint( point )
        return point

    def unregisterPointByFid(self, fid ):
        point = self.points[fid]
        route = self.getRoute( point.routeId )
        route.removePoint( fid )
        del self.points[fid]

    def registerPoints (self):
        feature = QgsFeature()
        iterator = self.pointLayer.getFeatures()
        while iterator.nextFeature(feature):
            self.registerPointFeature ( feature )

    #############################################33

    def getErrors(self):
        errors = list ( self.errors )
        for route in self.routes.values():
            errors.extend( route.getErrors() )
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
        self.pointEditBuffer.geometryChanged.connect( self.pointGeometryChanged )
        self.pointEditBuffer.attributeValueChanged.connect( self.pointAttributeValueChanged )

    def pointLayerEditingStopped(self):
        self.pointEditBuffer = None

    def pointLayerEditingDisconnect(self):
        if self.pointEditBuffer:
            self.pointEditBuffer.featureAdded.disconnect( self.pointFeatureAdded )
            self.pointEditBuffer.featureDeleted.disconnect( self.pointFeatureDeleted )
            self.pointEditBuffer.geometryChanged.disconnect( self.pointGeometryChanged )
            self.pointEditBuffer.attributeValueChanged.disconnect( self.pointAttributeValueChanged )

    def lineLayerEditingStarted(self):
        self.lineEditBuffer = self.lineLayer.editBuffer()
        self.lineEditBuffer.featureAdded.connect( self.lineFeatureAdded )
        self.lineEditBuffer.featureDeleted.connect( self.lineFeatureDeleted )
        self.lineEditBuffer.geometryChanged.connect( self.lineGeometryChanged )
        self.lineEditBuffer.attributeValueChanged.connect( self.lineAttributeValueChanged )

    def lineLayerEditingStopped(self):
        self.lineEditBuffer = None

    def lineLayerEditingDisconnect(self):
        if self.lineEditBuffer:
            self.lineEditBuffer.featureAdded.disconnect( self.lineFeatureAdded )
            self.lineEditBuffer.featureDeleted.disconnect( self.lineFeatureDeleted )
            self.lineEditBuffer.geometryChanged.disconnect( self.lineGeometryChanged )
            self.lineEditBuffer.attributeValueChanged.disconnect( self.lineAttributeValueChanged )


    

    # Warning: featureAdded is called first with temporary (negative fid)
    # then, when changes are commited, featureDeleted is called with that 
    # temporary id and featureAdded with real new id,
    # if changes are rollbacked, only featureDeleted is called

    #### point edit ####
    def pointFeatureAdded( self, fid ):
        # added features have temporary negative id
        #debug ( "feature added fid %s" % fid )
        feature = getLayerFeature( self.pointLayer, fid )
        point = self.registerPointFeature ( feature ) # returns LrsPoint
        route = self.getRoute( point.routeId )
        errorUpdates = route.calibrate()
        self.updateErrors.emit ( errorUpdates )

    def pointFeatureDeleted( self, fid ):
        #debug ( "feature deleted fid %s" % fid )
        # deleted feature cannot be read anymore from layer
        point = self.points[fid]
        route = self.getRoute( point.routeId )
        self.unregisterPointByFid(fid)
        errorUpdates = route.calibrate()
        self.updateErrors.emit ( errorUpdates )
            
    def pointGeometryChanged( self, fid, geo ):
        #debug ( "geometry changed fid %s" % fid )

        #remove old
        point = self.points[fid]
        route = self.getRoute( point.routeId )
        self.unregisterPointByFid(fid)
        
        # add new
        feature = getLayerFeature( self.pointLayer, fid )
        self.registerPointFeature ( feature )

        errorUpdates = route.calibrate()
        self.updateErrors.emit ( errorUpdates )

    def pointAttributeValueChanged( self, fid, attIdx, value ):
        #debug ( "attribute changed fid = %s attIdx = %s value = %s " % (fid, attIdx, value) )

        fields = self.pointLayer.pendingFields()
        routeIdx = fields.indexFromName ( self.pointRouteField )
        measureIdx = fields.indexFromName ( self.pointMeasureField )
        #debug ( "routeIdx = %s measureIdx = %s" % ( routeIdx, measureIdx) )
        
        if attIdx == routeIdx or attIdx == measureIdx:
            point = self.points[fid]
            route = self.getRoute( point.routeId )
            feature = getLayerFeature( self.pointLayer, fid )
            self.unregisterPointByFid(fid)

            if attIdx == routeIdx:
                # recalibrate old
                errorUpdates = route.calibrate()
                self.updateErrors.emit ( errorUpdates )

            point = self.registerPointFeature ( feature ) # returns LrsPoint
            route = self.getRoute( point.routeId )
            errorUpdates = route.calibrate()
            self.updateErrors.emit ( errorUpdates )
    
    #### line edit ####
    def lineFeatureAdded( self, fid ):
        # added features have temporary negative id
        #debug ( "feature added fid %s" % fid )
        feature = getLayerFeature( self.lineLayer, fid )
        line = self.registerLineFeature ( feature ) # returns LrsLine
        route = self.getRoute( line.routeId )
        errorUpdates = route.calibrate()
        self.updateErrors.emit ( errorUpdates )

    def lineFeatureDeleted( self, fid ):
        #debug ( "feature deleted fid %s" % fid )
        # deleted feature cannot be read anymore from layer
        line = self.lines[fid]
        route = self.getRoute( line.routeId )
        self.unregisterLineByFid(fid)
        errorUpdates = route.calibrate()
        self.updateErrors.emit ( errorUpdates )
            
    def lineGeometryChanged( self, fid, geo ):
        #debug ( "geometry changed fid %s" % fid )

        #remove old
        line = self.lines[fid]
        route = self.getRoute( line.routeId )
        self.unregisterLineByFid(fid)
        
        # add new
        feature = getLayerFeature( self.lineLayer, fid )
        self.registerLineFeature ( feature )

        errorUpdates = route.calibrate()
        self.updateErrors.emit ( errorUpdates )

    def lineAttributeValueChanged( self, fid, attIdx, value ):
        #debug ( "attribute changed fid = %s attIdx = %s value = %s " % (fid, attIdx, value) )

        fields = self.lineLayer.pendingFields()
        routeIdx = fields.indexFromName ( self.lineRouteField )
        #debug ( "routeIdx = %s" % ( routeIdx, measureIdx) )
        
        if attIdx == routeIdx:
            line = self.lines[fid]
            route = self.getRoute( line.routeId )
            feature = getLayerFeature( self.lineLayer, fid )

            self.unregisterLineByFid(fid)
            errorUpdates = route.calibrate()
            self.updateErrors.emit ( errorUpdates )

            line = self.registerLineFeature ( feature ) # returns LrsLine
            route = self.getRoute( line.routeId )
            errorUpdates = route.calibrate()
            self.updateErrors.emit ( errorUpdates )