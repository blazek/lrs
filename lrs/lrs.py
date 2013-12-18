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
import time
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
    progressChanged = pyqtSignal( str, float, name = 'progressChanged' )
    updateErrors = pyqtSignal(dict, name = 'updateErrors')

    # progress counts
    CURRENT = 1 # current progress count
    TOTAL = 2 # sum of steps to do
    NLINES = 3 # number of lines
    NPOINTS = 4 # number of points
    NROUTES = 5 # number of routes

    # calibration steps
    REGISTERING_LINES = 1
    REGISTERING_POINTS = 2
    BUILDING_PARTS = 3
    CALIBRATING_ROUTES = 4

    stateLabels = {
        REGISTERING_LINES: 'Registering lines',
        REGISTERING_POINTS: 'Registering points',
        BUILDING_PARTS: 'Building routes',
        CALIBRATING_ROUTES: 'Calibrating routes',
    }

    def __init__(self, lineLayer, lineRouteField, pointLayer, pointRouteField, pointMeasureField, **kwargs ):
        super(Lrs, self).__init__()

        self.lineLayer = lineLayer
        self.lineRouteField = lineRouteField
        self.pointLayer = pointLayer
        self.pointRouteField = pointRouteField
        self.pointMeasureField = pointMeasureField
        # selectionMode: all,include,exclude selection
        self.selectionMode = kwargs.get('selectionMode', 'all')
        # selection is list of route ids to be included/excluded
        self.selection = []
        for routeId in kwargs.get('selection', [] ):
            self.selection.append( normalizeRouteId( routeId ) )
        # max lines gaps snap
        self.snap = kwargs.get('snap', 0.0)
        # threshold - max distance between point and line in canvas CRS units
        self.threshold = kwargs.get('threshold', 10.0)
        self.crs = kwargs.get('crs')
        #self.mapUnitsPerMeasureUnit = kwargs.get('mapUnitsPerMeasureUnit',1000.0)
        self.measureUnit = kwargs.get('measureUnit', LrsUnits.UNKNOWN)
        if self.measureUnit == LrsUnits.UNKNOWN:
            raise Exception( "measureUnit not set" )

        self.distanceArea = QgsDistanceArea()
        # QgsDistanceArea.setSourceCrs( QgsCoordinateReferenceSystem ) is missing in SIP
        #self.distanceArea.setSourceCrs( self.crs )
        self.distanceArea.setSourceCrs( self.crs.srsid() )
        if self.crs.mapUnits() == QGis.Degrees:
            self.distanceArea.setEllipsoidalMode( True )
            ellipsoid = self.crs.ellipsoidAcronym()
            if not ellipsoid: ellipsoid = "WGS84"
            self.distanceArea.setEllipsoid( ellipsoid )
        
        # extrapolate LRS before/after calibration points
        self.extrapolate = kwargs.get('extrapolate', False)

        self.pointLayer.editingStarted.connect( self.pointLayerEditingStarted )
        self.pointLayer.editingStopped.connect( self.pointLayerEditingStopped )
        self.pointEditBuffer = None
        if self.pointLayer.editBuffer(): # layer is already in editing mode
            self.pointLayerEditingStarted()

        self.lineLayer.editingStarted.connect( self.lineLayerEditingStarted )
        self.lineLayer.editingStopped.connect( self.lineLayerEditingStopped )
        self.lineEditBuffer = None
        if self.lineLayer.editBuffer():
            self.lineLayerEditingStarted()

        self.lines = {} # dict of LrsLine with fid as key
        self.points = {} # dict of LrsPoint with fid as key

        self.errors = [] # LrsError list

        self.progressCounts = {}

        self.lineTransform = None
        if self.crs and self.crs != lineLayer.crs():
            self.lineTransform = QgsCoordinateTransform( lineLayer.crs(), self.crs)

        self.pointTransform = None
        if self.crs and self.crs != pointLayer.crs():
            self.pointTransform = QgsCoordinateTransform( pointLayer.crs(), self.crs)

        # dictionary of LrsRoute, key is normalized route id
        self.routes = {} 

        self.partSpatialIndex = None
        self.partSpatialIndexRoutePart = None

        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.layersWillBeRemoved)        

    def __del__(self):
        self.disconnect()

    def pointLayerDisconnect(self):
        if not self.pointLayer: return
        self.pointLayerEditingDisconnect()
        self.pointLayer.editingStarted.disconnect( self.pointLayerEditingStarted )
        self.pointLayer.editingStopped.disconnect( self.pointLayerEditingStopped )
        
    def lineLayerDisconnect(self):
        if not self.lineLayer: return
        self.lineLayerEditingDisconnect()
        self.lineLayer.editingStarted.disconnect( self.lineLayerEditingStarted )
        self.lineLayer.editingStopped.disconnect( self.lineLayerEditingStopped )

    def disconnect(self):
        QgsMapLayerRegistry.instance().layersWillBeRemoved.disconnect(self.layersWillBeRemoved)
        self.pointLayerDisconnect()
        self.lineLayerDisconnect()

    def layersWillBeRemoved(self, layerIdList ):
        project = QgsProject.instance()
        for id in layerIdList:
            if self.pointLayer and self.pointLayer.id() == id:
                self.pointLayerDisconnect()
                self.pointLayer = None
            if self.lineLayer and self.lineLayer.id() == id:
                self.lineLayerDisconnect()
                self.lineLayer = None

##################### COMMON ###############################################
    
    # test if process route according to selectionMode and selection
    def routeIdSelected(self, routeId):
        routeId = normalizeRouteId( routeId )
        if self.selectionMode == 'all':
            return True
        elif self.selectionMode == 'include':
            return routeId in self.selection
        elif self.selectionMode == 'exclude':
            return routeId not in self.selection

##################### GENERATE (CALIBRATE) #################################

    def updateProgressTotal(self):
        cnts = self.progressCounts
        cnts[self.TOTAL] = cnts[self.NLINES]
        cnts[self.TOTAL] += cnts[self.NPOINTS]
        cnts[self.TOTAL] += cnts[self.NROUTES] # build parts
        cnts[self.TOTAL] += cnts[self.NROUTES] # calibrate routes
        #debug ("%s" % cnts )

    # increase progress, called after each step (line, point...)
    def progressStep(self, state):
        self.progressCounts[self.CURRENT] = self.progressCounts.get(self.CURRENT,0) + 1
        percent = 100 * self.progressCounts[self.CURRENT] / self.progressCounts[self.TOTAL]
        #debug ( "percent = %s %s / %s" % (percent, self.progressCounts[self.CURRENT], self.progressCounts[self.TOTAL] ) ) 
        self.progressChanged.emit( self.stateLabels[state], percent )

    def calibrate(self):
        self.progressChanged.emit( self.stateLabels[self.REGISTERING_LINES], 0 )

        self.points = {}
        self.lines = {} 
        self.errors = [] # reset

        self.progressCounts = {}
        # we dont know progressTotal at the beginning, but we can estimate it
        self.progressCounts[self.NLINES] =  self.lineLayer.featureCount()
        self.progressCounts[self.NPOINTS] =  self.pointLayer.featureCount()
        # estimation (precise later when routes are built)
        self.progressCounts[self.NROUTES] = self.progressCounts[self.NLINES]
        self.updateProgressTotal()

        self.registerLines()
        self.registerPoints()
        self.buildParts()
        for route in self.routes.values():
            route.calibrate(self.extrapolate)

    def buildParts(self):
        for route in self.routes.values():
            route.buildParts()
            self.progressStep(self.BUILDING_PARTS) 

    # get route by id, create it if does not exist
    # routeId does not have to be normalized
    def getRoute(self, routeId):
        normalId = normalizeRouteId( routeId )
        if not self.routes.has_key( normalId ):
            self.routes[normalId] = LrsRoute(self.lineLayer, routeId, self.snap, self.threshold, self.crs, self.measureUnit, self.distanceArea )
        return self.routes[normalId]

    # get route by id if exists otherwise returns None
    # routeId does not have to be normalized
    def getRouteIfExists(self, routeId):
        normalId = normalizeRouteId( routeId )
        if not self.routes.has_key( normalId ): return None
        return self.routes[normalId]

    ####### register / unregister features

    def registerLineFeature (self, feature):
        routeId = feature[self.lineRouteField]
        if routeId == '' or routeId == NULL: routeId = None
        #debug ( "fid = %s routeId = %s" % ( feature.id(), routeId ) )

        if not self.routeIdSelected(routeId): return

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
        for feature in self.lineLayer.getFeatures():
            self.registerLineFeature(feature)
            self.progressStep(self.REGISTERING_LINES) 
        # precise number of routes
        self.progressCounts[self.NROUTES] = len( self.routes )
        self.updateProgressTotal()

    # returns LrsPoint
    def registerPointFeature (self, feature):
        routeId = feature[self.pointRouteField]
        if routeId == '' or routeId == NULL: routeId = None

        if not self.routeIdSelected(routeId): return

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
        for feature in self.pointLayer.getFeatures():
            self.registerPointFeature ( feature )
            self.progressStep(self.REGISTERING_POINTS) 
        # route total may increase (e.g. orphans)
        self.progressCounts[self.NROUTES] = len( self.routes )
        self.updateProgressTotal()

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

    def getQualityFeatures(self):
        features = []
        for route in self.routes.values():
            features.extend( route.getQualityFeatures() )
        return features

    ################## Editing ##################
    def pointLayerEditingStarted(self):
        self.pointEditBuffer = self.pointLayer.editBuffer()
        self.pointEditBuffer.featureAdded.connect( self.pointFeatureAdded )
        self.pointEditBuffer.featureDeleted.connect( self.pointFeatureDeleted )
        # some versions of PyQt fail (Win build) with new style connection if the signal has multiple params
        #self.pointEditBuffer.geometryChanged.connect( self.pointGeometryChanged )
        QObject.connect(self.pointEditBuffer, SIGNAL("geometryChanged(QgsFeatureId, QgsGeometry &)"), self.pointGeometryChanged )
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
        #self.lineEditBuffer.geometryChanged.connect( self.lineGeometryChanged )
        QObject.connect(self.lineEditBuffer, SIGNAL("geometryChanged(QgsFeatureId, QgsGeometry &)"), self.lineGeometryChanged )
        self.lineEditBuffer.attributeValueChanged.connect( self.lineAttributeValueChanged )

    def lineLayerEditingStopped(self):
        self.lineEditBuffer = None

    def lineLayerEditingDisconnect(self):
        if self.lineEditBuffer:
            self.lineEditBuffer.featureAdded.disconnect( self.lineFeatureAdded )
            self.lineEditBuffer.featureDeleted.disconnect( self.lineFeatureDeleted )
            self.lineEditBuffer.geometryChanged.disconnect( self.lineGeometryChanged )
            self.lineEditBuffer.attributeValueChanged.disconnect( self.lineAttributeValueChanged )
    
    def emitUpdateErrors(self, errorUpdates):
        errorUpdates['crs'] = self.crs
        self.updateErrors.emit ( errorUpdates )

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
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors( errorUpdates )

    def pointFeatureDeleted( self, fid ):
        #debug ( "feature deleted fid %s" % fid )
        # deleted feature cannot be read anymore from layer
        point = self.points[fid]
        route = self.getRoute( point.routeId )
        self.unregisterPointByFid(fid)
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors( errorUpdates )
            
    def pointGeometryChanged( self, fid, geo ):
        #debug ( "geometry changed fid %s" % fid )

        #remove old
        point = self.points[fid]
        route = self.getRoute( point.routeId )
        self.unregisterPointByFid(fid)
        
        # add new
        feature = getLayerFeature( self.pointLayer, fid )
        self.registerPointFeature ( feature )

        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors( errorUpdates )

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
                errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
                self.emitUpdateErrors( errorUpdates )

            point = self.registerPointFeature ( feature ) # returns LrsPoint
            route = self.getRoute( point.routeId )
            errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
            self.emitUpdateErrors( errorUpdates )
    
    #### line edit ####
    def lineFeatureAdded( self, fid ):
        # added features have temporary negative id
        #debug ( "feature added fid %s" % fid )
        feature = getLayerFeature( self.lineLayer, fid )
        line = self.registerLineFeature ( feature ) # returns LrsLine
        route = self.getRoute( line.routeId )
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors( errorUpdates )

    def lineFeatureDeleted( self, fid ):
        #debug ( "feature deleted fid %s" % fid )
        # deleted feature cannot be read anymore from layer
        line = self.lines[fid]
        route = self.getRoute( line.routeId )
        self.unregisterLineByFid(fid)
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors( errorUpdates )
            
    def lineGeometryChanged( self, fid, geo ):
        #debug ( "geometry changed fid %s" % fid )

        #remove old
        line = self.lines[fid]
        route = self.getRoute( line.routeId )
        self.unregisterLineByFid(fid)
        
        # add new
        feature = getLayerFeature( self.lineLayer, fid )
        self.registerLineFeature ( feature )

        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors( errorUpdates )

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
            errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
            self.emitUpdateErrors( errorUpdates )

            line = self.registerLineFeature ( feature ) # returns LrsLine
            route = self.getRoute( line.routeId )
            errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
            self.emitUpdateErrors( errorUpdates )


##################### EVENTS ######################################

    def eventValuesError(self, routeId, start, end = None, linear = False):
        error = None
        missing = []
        if routeId is None: missing.append( 'route' )
        if start is None: missing.append( 'start measure' )
        if linear and end is None: missing.append( 'end measure' )

        if missing:
            error = 'missing %s value' % ' and '.join( missing )

        route = self.getRouteIfExists( routeId )
        if not route:
            error = error + ', ' if error else ''
            error += 'route not available'

        return error

    # returns ( QgsPoint, error )
    def eventPoint(self, routeId, start):
        error = self.eventValuesError( routeId, start)
        if error: return None, error

        route = self.getRoute( routeId )
        geo, error = route.eventPoint( start )
        return geo, error
        
    # returns ( QgsMultiPolyline, error )
    def eventMultiPolyLine(self, routeId, start, end):
        error = self.eventValuesError( routeId, start, end, True)
        if error: return None, error

        route = self.getRoute( routeId )
        geo, error = route.eventMultiPolyLine( start, end)
        return geo, error

############################# MEASURE ####################################

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
                geo = QgsGeometry.fromPolyline( route.parts[i].polyline )
                feature.setGeometry( geo )
                self.partSpatialIndex.insertFeature( feature )
                self.partSpatialIndexRoutePart[fid] = [ route.routeId, i ]
                fid += 1

    # returns nearest routeId, partIdx within threshold 
    def nearestRoutePart(self, point, threshold ):
        if not self.partSpatialIndex:
            self.createPartSpatialIndex()
        rect = QgsRectangle( point.x()-threshold, point.y()-threshold, point.x()+threshold, point.y()+threshold )
        ids = self.partSpatialIndex.intersects( rect )
        #debug ( '%s' % ids )
        nearestRouteId = None
        nearestPartIdx = None
        nearestDist = sys.float_info.max
        for id in ids:
            routeId, partIdx = self.partSpatialIndexRoutePart[id]
            route = self.getRoute( routeId )
            part = route.parts[partIdx]
            geo = QgsGeometry.fromPolyline( part.polyline )
            ( sqDist, nearestPnt, afterVertex ) = geo.closestSegmentWithContext( point )
            dist = math.sqrt( sqDist )
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
    def pointMeasure ( self, point, threshold ):
        routeId, partIdx = self.nearestRoutePart( point, threshold)
        if routeId is not None and partIdx is not None:
            route = self.getRoute( routeId )
            part = route.parts[partIdx]
            measure = part.pointMeasure( point )
            if measure is not None:
                return routeId, measure
            
        return routeId, None

