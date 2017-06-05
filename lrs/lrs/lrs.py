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
# from PyQt4.QtGui import *
from .error.lrserror import *
from .lrsbase import LrsBase
from .lrsline import LrsLine
from .lrspoint import LrsPoint
from .lrsroute import LrsRoute


# Main class to keep all data and process them

class Lrs(LrsBase):
    progressChanged = pyqtSignal(str, float, name='progressChanged')
    updateErrors = pyqtSignal(dict, name='updateErrors')
    edited = pyqtSignal(name='edited')

    # progress counts
    CURRENT = 1  # current progress count
    TOTAL = 2  # sum of steps to do
    NLINES = 3  # number of lines
    NPOINTS = 4  # number of points
    NROUTES = 5  # number of routes

    # calibration steps
    REGISTERING_LINES = 1
    REGISTERING_POINTS = 2
    CALIBRATING_ROUTES = 3

    stateLabels = {
        REGISTERING_LINES: 'Registering lines',
        REGISTERING_POINTS: 'Registering points',
        CALIBRATING_ROUTES: 'Calibrating routes',
    }

    def __init__(self, lineLayer, lineRouteField, pointLayer, pointRouteField, pointMeasureField, **kwargs):
        super(Lrs, self).__init__(**kwargs)

        self.lineLayer = lineLayer
        self.lineRouteField = lineRouteField
        self.pointLayer = pointLayer
        self.pointRouteField = pointRouteField
        self.pointMeasureField = pointMeasureField
        # selectionMode: all,include,exclude selection
        self.selectionMode = kwargs.get('selectionMode', 'all')
        # selection is list of route ids to be included/excluded
        self.selection = []
        for routeId in kwargs.get('selection', []):
            self.selection.append(normalizeRouteId(routeId))
        # max lines gaps snap
        self.snap = kwargs.get('snap', 0.0)
        # threshold - max distance between point and line in canvas CRS units
        self.threshold = kwargs.get('threshold', 10.0)
        self.parallelMode = kwargs.get('parallelMode', 'error')
        self.crs = kwargs.get('crs')


        self.distanceArea = QgsDistanceArea()
        # QgsDistanceArea.setSourceCrs( QgsCoordinateReferenceSystem ) is missing in SIP in at least QGIS 2.0 
        self.distanceArea.setSourceCrs(self.crs)
        if self.crs.mapUnits() == QgsUnitTypes.DistanceDegrees:
            ellipsoid = self.crs.ellipsoidAcronym()
            if not ellipsoid: ellipsoid = "WGS84"
            self.distanceArea.setEllipsoid(ellipsoid)

        # extrapolate LRS before/after calibration points
        self.extrapolate = kwargs.get('extrapolate', False)

        # stored line route id QgsField to know type
        self.routeField = None

        self.pointLayer.editingStarted.connect(self.pointLayerEditingStarted)
        self.pointLayer.editingStopped.connect(self.pointLayerEditingStopped)
        self.pointEditBuffer = None
        if self.pointLayer.editBuffer():  # layer is already in editing mode
            self.pointLayerEditingStarted()

        self.lineLayer.editingStarted.connect(self.lineLayerEditingStarted)
        self.lineLayer.editingStopped.connect(self.lineLayerEditingStopped)
        self.lineEditBuffer = None
        if self.lineLayer.editBuffer():
            self.lineLayerEditingStarted()

        self.lines = {}  # dict of LrsLine with fid as key
        self.points = {}  # dict of LrsPoint with fid as key

        self.errors = []  # LrsError list

        self.progressCounts = {}

        # Numbers of features/lines/points currently not used because did not 
        # correspond well to list/layer of errors
        self.stats = {}  # statistics
        self.statsNames = (
            # ( 'lineFeatures', 'Total number of line features' ), # may be multilinestrings
            # ( 'lineFeaturesIncluded', 'Number of included line features' ), # selected
            # ( 'lines', 'Total number of line strings' ), # may be parts of multi
            # ( 'linesIncluded', 'Number of included line strings' ),
            # ( 'pointFeatures', 'Total number of point features' ), #may be multipoint
            # ( 'pointFeaturesIncluded', 'Number of included point features' ), # selected
            # ( 'points', 'Total number of points' ), # may be parts of multi
            # ( 'pointsIncluded', 'Number of included points' ), # selected
            # ( 'pointsOk', 'Number of included points successfully used in LRS' ),
            # ( 'pointsError', 'Number of included points with error' ),
            ('length', 'Total length of all lines'),
            ('lengthIncluded', 'Length of included lines'),
            ('lengthOk', 'Length of successfully created LRS'),
            # ( 'lengthError', 'Length of included lines without LRS' ),
        )

        self.lineTransform = None
        if self.crs and self.crs != lineLayer.crs():
            self.lineTransform = QgsCoordinateTransform(lineLayer.crs(), self.crs)

        self.pointTransform = None
        if self.crs and self.crs != pointLayer.crs():
            self.pointTransform = QgsCoordinateTransform(pointLayer.crs(), self.crs)

        self.wasEdited = False  # true if layers were edited since calibration

        QgsProject.instance().layersWillBeRemoved.connect(self.layersWillBeRemoved)

    def __del__(self):
        self.disconnect()

    def pointLayerDisconnect(self):
        if not self.pointLayer: return
        self.pointLayerEditingDisconnect()
        self.pointLayer.editingStarted.disconnect(self.pointLayerEditingStarted)
        self.pointLayer.editingStopped.disconnect(self.pointLayerEditingStopped)

    def lineLayerDisconnect(self):
        if not self.lineLayer: return
        self.lineLayerEditingDisconnect()
        self.lineLayer.editingStarted.disconnect(self.lineLayerEditingStarted)
        self.lineLayer.editingStopped.disconnect(self.lineLayerEditingStopped)

    def disconnect(self):
        QgsProject.instance().layersWillBeRemoved.disconnect(self.layersWillBeRemoved)
        self.pointLayerDisconnect()
        self.lineLayerDisconnect()

    def layersWillBeRemoved(self, layerIdList):
        project = QgsProject.instance()
        for id in layerIdList:
            if self.pointLayer and self.pointLayer.id() == id:
                self.pointLayerDisconnect()
                self.pointLayer = None
            if self.lineLayer and self.lineLayer.id() == id:
                self.lineLayerDisconnect()
                self.lineLayer = None

    # ------------------- COMMON -------------------
    # get route by id, create it if does not exist
    # routeId does not have to be normalized
    def getRoute(self, routeId):
        normalId = normalizeRouteId(routeId)
        # debug ( 'normalId = %s orig type = %s' % (normalId, type(routeId) ) )
        if normalId not in self.routes:
            self.routes[normalId] = LrsRoute(self.lineLayer, routeId, self.snap, self.threshold, self.crs,
                                             self.measureUnit, self.distanceArea, parallelMode=self.parallelMode)
        return self.routes[normalId]


    # test if process route according to selectionMode and selection
    def routeIdSelected(self, routeId):
        routeId = normalizeRouteId(routeId)
        if self.selectionMode == 'all':
            return True
        elif self.selectionMode == 'include':
            return routeId in self.selection
        elif self.selectionMode == 'exclude':
            return routeId not in self.selection

    # ------------------- GENERATE (CALIBRATE) -------------------

    def updateProgressTotal(self):
        cnts = self.progressCounts
        cnts[self.TOTAL] = cnts[self.NLINES]
        cnts[self.TOTAL] += cnts[self.NPOINTS]
        cnts[self.TOTAL] += cnts[self.NROUTES]  # calibrate routes
        # debug ("%s" % cnts )

    # increase progress, called after each step (line, point...)
    def progressStep(self, state):
        self.progressCounts[self.CURRENT] = self.progressCounts.get(self.CURRENT, 0) + 1
        percent = 100 * self.progressCounts[self.CURRENT] / self.progressCounts[self.TOTAL]
        # debug ( "percent = %s %s / %s" % (percent, self.progressCounts[self.CURRENT], self.progressCounts[self.TOTAL] ) )
        self.progressChanged.emit(self.stateLabels[state], percent)

    def calibrate(self):
        # debug ( 'Lrs.calibrate' )
        self.progressChanged.emit(self.stateLabels[self.REGISTERING_LINES], 0)

        self.points = {}
        self.lines = {}
        self.errors = []  # reset

        self.stats = {}
        for s in self.statsNames:
            self.stats[s[0]] = 0

        field = self.lineLayer.pendingFields().field(self.lineRouteField)
        self.routeField = QgsField(field.name(), field.type(), field.typeName(), field.length(), field.precision())

        self.progressCounts = {}
        # we don't know progressTotal at the beginning, but we can estimate it
        self.progressCounts[self.NLINES] = self.lineLayer.featureCount()
        self.progressCounts[self.NPOINTS] = self.pointLayer.featureCount()
        # estimation (precise later when routes are built)
        self.progressCounts[self.NROUTES] = self.progressCounts[self.NLINES]
        self.updateProgressTotal()

        self.registerLines()
        self.registerPoints()
        for route in self.routes.values():
            route.calibrate(self.extrapolate)
            self.progressStep(self.CALIBRATING_ROUTES)

            # count stats
        for route in self.routes.values():
            # self.stats['pointsOk'] += len ( route.getGoodMilestones() )
            self.stats['lengthOk'] += route.getGoodLength()

            # self.stats['pointsError'] = self.stats['pointsIncluded'] - self.stats['pointsOk']

    # -------------------------------- register / unregister features ----------------------

    def registerLineFeature(self, feature):
        routeId = feature[self.lineRouteField]
        if routeId == '' or routeId == NULL: routeId = None
        # debug ( "fid = %s routeId = %s" % ( feature.id(), routeId ) )

        if not self.routeIdSelected(routeId):
            return None

        geo = feature.geometry()
        if geo:
            if self.lineTransform:
                geo.transform(self.lineTransform)

        route = self.getRoute(routeId)
        line = LrsLine(feature.id(), routeId, geo)
        self.lines[feature.id()] = line
        route.addLine(line)
        return line

    def unregisterLineByFid(self, fid):
        line = self.lines[fid]
        route = self.getRoute(line.routeId)
        route.removeLine(fid)
        del self.lines[fid]

    def registerLines(self):
        self.routes = {}
        for feature in self.lineLayer.getFeatures():
            line = self.registerLineFeature(feature)
            # self.stats['lineFeatures'] += 1
            length = 0
            if feature.geometry():
                length = self.distanceArea.measureLength(feature.geometry())
            self.stats['length'] += length
            if line:
                # self.stats['lineFeaturesIncluded'] += 1
                # self.stats['linesIncluded'] += line.getNumParts()
                self.stats['lengthIncluded'] += length
            self.progressStep(self.REGISTERING_LINES)
            # precise number of routes
        self.progressCounts[self.NROUTES] = len(self.routes)
        self.updateProgressTotal()

    # returns LrsPoint
    def registerPointFeature(self, feature):
        routeId = feature[self.pointRouteField]
        if routeId == '' or routeId == NULL: routeId = None

        if not self.routeIdSelected(routeId): return None

        measure = feature[self.pointMeasureField]
        if measure == NULL: measure = None
        if measure is not None:
            # convert to float to don't care later about operations with integers
            measure = float(measure)
        # debug ( "fid = %s routeId = %s measure = %s" % ( feature.id(), routeId, measure ) )
        geo = feature.geometry()
        if geo:
            if self.pointTransform:
                geo.transform(self.pointTransform)

        point = LrsPoint(feature.id(), routeId, measure, geo)
        self.points[feature.id()] = point
        route = self.getRoute(routeId)
        route.addPoint(point)
        return point

    def unregisterPointByFid(self, fid):
        point = self.points[fid]
        route = self.getRoute(point.routeId)
        route.removePoint(fid)
        del self.points[fid]

    def registerPoints(self):
        for feature in self.pointLayer.getFeatures():
            point = self.registerPointFeature(feature)
            # self.stats['pointFeatures'] += 1
            # if point:
            # self.stats['pointFeaturesIncluded'] += 1
            # self.stats['pointsIncluded'] += point.getNumParts()
            self.progressStep(self.REGISTERING_POINTS)
            # route total may increase (e.g. orphans)
        self.progressCounts[self.NROUTES] = len(self.routes)
        self.updateProgressTotal()

    # -------------------33

    def getRouteIds(self):
        ids = []
        for route in self.routes.values():
            if route.routeId is not None:
                ids.append(route.routeId)

        ids.sort()
        return ids

    def getErrors(self):
        errors = list(self.errors)
        for route in self.routes.values():
            errors.extend(route.getErrors())
        return errors

    def getParts(self):
        parts = []
        for route in self.routes.values():
            parts.extend(route.parts)
        return parts

    def getSegments(self):
        segments = []
        for route in self.routes.values():
            segments.extend(route.getSegments())
        return segments

    def getQualityFeatures(self):
        features = []
        for route in self.routes.values():
            features.extend(route.getQualityFeatures())
        return features

    # ----------------------------- Editing ---------------------------------
    def pointLayerEditingStarted(self):
        self.pointEditBuffer = self.pointLayer.editBuffer()
        self.pointEditBuffer.featureAdded.connect(self.pointFeatureAdded)
        self.pointEditBuffer.featureDeleted.connect(self.pointFeatureDeleted)
        # some versions of PyQt fail (Win build) with new style connection if the signal has multiple params
        # self.pointEditBuffer.geometryChanged.connect( self.pointGeometryChanged )
        # QObject.connect(self.pointEditBuffer, SIGNAL("geometryChanged(QgsFeatureId, QgsGeometry &)"),
        #                self.pointGeometryChanged)
        # TODO: working?
        self.pointEditBuffer.geometryChanged["QgsFeatureId, QgsGeometry"].connect(self.pointGeometryChanged)
        self.pointEditBuffer.attributeValueChanged.connect(self.pointAttributeValueChanged)

    def pointLayerEditingStopped(self):
        self.pointEditBuffer = None

    def pointLayerEditingDisconnect(self):
        if self.pointEditBuffer:
            self.pointEditBuffer.featureAdded.disconnect(self.pointFeatureAdded)
            self.pointEditBuffer.featureDeleted.disconnect(self.pointFeatureDeleted)
            self.pointEditBuffer.geometryChanged.disconnect(self.pointGeometryChanged)
            self.pointEditBuffer.attributeValueChanged.disconnect(self.pointAttributeValueChanged)

    def lineLayerEditingStarted(self):
        self.lineEditBuffer = self.lineLayer.editBuffer()
        self.lineEditBuffer.featureAdded.connect(self.lineFeatureAdded)
        self.lineEditBuffer.featureDeleted.connect(self.lineFeatureDeleted)
        # self.lineEditBuffer.geometryChanged.connect( self.lineGeometryChanged )
        # QObject.connect(self.lineEditBuffer, SIGNAL("geometryChanged(QgsFeatureId, QgsGeometry &)"),
        #                self.lineGeometryChanged)
        # TODO: working?
        self.lineEditBuffer.geometryChanged["QgsFeatureId, QgsGeometry"].connect(self.lineGeometryChanged)
        self.lineEditBuffer.attributeValueChanged.connect(self.lineAttributeValueChanged)

    def lineLayerEditingStopped(self):
        self.lineEditBuffer = None

    def lineLayerEditingDisconnect(self):
        if self.lineEditBuffer:
            self.lineEditBuffer.featureAdded.disconnect(self.lineFeatureAdded)
            self.lineEditBuffer.featureDeleted.disconnect(self.lineFeatureDeleted)
            self.lineEditBuffer.geometryChanged.disconnect(self.lineGeometryChanged)
            self.lineEditBuffer.attributeValueChanged.disconnect(self.lineAttributeValueChanged)

    def setEdited(self):
        self.wasEdited = True
        self.edited.emit()

    def getEdited(self):
        return self.wasEdited

    def emitUpdateErrors(self, errorUpdates):
        errorUpdates['crs'] = self.crs
        self.updateErrors.emit(errorUpdates)

    # Warning: featureAdded is called first with temporary (negative fid)
    # then, when changes are commited, featureDeleted is called with that 
    # temporary id and featureAdded with real new id,
    # if changes are rollbacked, only featureDeleted is called

    # ------------------- point edit -------------------
    def pointFeatureAdded(self, fid):
        # added features have temporary negative id
        # debug ( "feature added fid %s" % fid )
        self.setEdited()
        feature = getLayerFeature(self.pointLayer, fid)
        point = self.registerPointFeature(feature)  # returns LrsPoint
        if not point: return  # route id not in selection

        route = self.getRoute(point.routeId)
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors(errorUpdates)

    def pointFeatureDeleted(self, fid):
        # debug ( "feature deleted fid %s" % fid )
        self.setEdited()
        # deleted feature cannot be read anymore from layer
        point = self.points.get(fid)
        if not point: return  # route id not in selection

        route = self.getRoute(point.routeId)
        self.unregisterPointByFid(fid)
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors(errorUpdates)

    def pointGeometryChanged(self, fid, geo):
        # debug ( "geometry changed fid %s" % fid )
        self.setEdited()

        # remove old
        point = self.points.get(fid)
        if not point: return  # route id not in selection

        route = self.getRoute(point.routeId)
        self.unregisterPointByFid(fid)

        # add new
        feature = getLayerFeature(self.pointLayer, fid)
        self.registerPointFeature(feature)

        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors(errorUpdates)

    def pointAttributeValueChanged(self, fid, attIdx, value):
        # debug ( "attribute changed fid = %s attIdx = %s value = %s " % (fid, attIdx, value) )
        self.setEdited()

        fields = self.pointLayer.pendingFields()
        routeIdx = fields.indexFromName(self.pointRouteField)
        measureIdx = fields.indexFromName(self.pointMeasureField)
        # debug ( "routeIdx = %s measureIdx = %s" % ( routeIdx, measureIdx) )

        if attIdx == routeIdx or attIdx == measureIdx:
            point = self.points.get(fid)
            if point:  # was in selection
                route = self.getRoute(point.routeId)
                self.unregisterPointByFid(fid)

                if attIdx == routeIdx:
                    # recalibrate old
                    errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
                    self.emitUpdateErrors(errorUpdates)

            feature = getLayerFeature(self.pointLayer, fid)
            point = self.registerPointFeature(feature)  # returns LrsPoint
            if point:  # route id in selection
                route = self.getRoute(point.routeId)
                errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
                self.emitUpdateErrors(errorUpdates)

    # --------------------------- line edit ---------------------------
    def lineFeatureAdded(self, fid):
        # added features have temporary negative id
        # debug ( "feature added fid %s" % fid )
        self.setEdited()
        feature = getLayerFeature(self.lineLayer, fid)
        line = self.registerLineFeature(feature)  # returns LrsLine
        if not line: return  # route id not in selection

        route = self.getRoute(line.routeId)
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors(errorUpdates)

    def lineFeatureDeleted(self, fid):
        # debug ( "feature deleted fid %s" % fid )
        # deleted feature cannot be read anymore from layer
        self.setEdited()
        line = self.lines.get(fid)
        if not line: return  # route id not in selection

        route = self.getRoute(line.routeId)
        self.unregisterLineByFid(fid)
        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors(errorUpdates)

    def lineGeometryChanged(self, fid, geo):
        # debug ( "geometry changed fid %s" % fid )
        self.setEdited()

        # remove old
        line = self.lines.get(fid)
        if not line: return  # route id not in selection

        route = self.getRoute(line.routeId)
        self.unregisterLineByFid(fid)

        # add new
        feature = getLayerFeature(self.lineLayer, fid)
        self.registerLineFeature(feature)

        errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
        self.emitUpdateErrors(errorUpdates)

    def lineAttributeValueChanged(self, fid, attIdx, value):
        # debug ( "attribute changed fid = %s attIdx = %s value = %s " % (fid, attIdx, value) )
        self.setEdited()

        fields = self.lineLayer.pendingFields()
        routeIdx = fields.indexFromName(self.lineRouteField)
        # debug ( "routeIdx = %s" % ( routeIdx, measureIdx) )

        if attIdx == routeIdx:
            line = self.lines.get(fid)
            if line:  # was in selection
                route = self.getRoute(line.routeId)
                self.unregisterLineByFid(fid)
                errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
                self.emitUpdateErrors(errorUpdates)

            feature = getLayerFeature(self.lineLayer, fid)

            line = self.registerLineFeature(feature)  # returns LrsLine
            if line:  # route id in selection
                route = self.getRoute(line.routeId)
                errorUpdates = route.calibrateAndGetUpdates(self.extrapolate)
                self.emitUpdateErrors(errorUpdates)



    # ------------------- STATS -------------------

    def getStatsHtmlRow(self, name, label):
        # return "%s : %s<br>" % ( label, self.stats[name] )
        value = self.stats[name]
        # lengths are in map units not in measure units
        # if 'length' in name.lower():
        #    value = formatMeasure( value, self.measureUnit )
        return "<tr><td>%s</td> <td>%s</td></tr>" % (label, value)

    def getStatsHtml(self):
        html = '''<html><head>
                    <style type="text/css">
                      table {
                        border: 1px solid gray;
                        border-spacing: 0px;
                      }
                      td {
                        padding: 5px;
                        border: 1px solid gray;
                        font-size: 10pt;
                      }
                      body {
                        font-size: 10pt;
                      }
                    </style>
                  </head><body>'''
        html += '<table border="1">'

        for s in self.statsNames:
            html += self.getStatsHtmlRow(s[0], s[1])

        html += '</table>'
        html += '<p>Lengths in map units.'
        html += '</body></html>'
        return html
