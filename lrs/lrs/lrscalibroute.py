# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsRoute
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
import operator
from functools import reduce

from .error.lrsqualityfeature import LrsQualityFeature
from .error.lrsqualityfields import LrsQualityFields
from .lrscalibpart import *
from .lrsmilestone import *
from .lrsorigin import LrsOrigin
from .lrsroutebase import LrsRouteBase


# Route used in calibration
# LrsRoute keeps list of LrsLine
class LrsCalibRoute(LrsRouteBase):
    def __init__(self, layer, routeId, snap, threshold, crs, measureUnit, distanceArea, **kwargs):
        # debug ('init route %s' % routeId )
        super(LrsCalibRoute, self).__init__(routeId, **kwargs)
        self.layer = layer
        self.snap = snap
        self.threshold = threshold
        self.crs = crs
        self.measureUnit = measureUnit
        self.distanceArea = distanceArea

        self.lines = []  # LrsLine list, may be empty
        self.points = []  # LrsPoint list, may be empty

        self.milestones = []  # LrsMilestone list
        # cached all errors, route itself and parts
        self.allErrors_ = []

    def addLine(self, line):
        self.lines.append(line)

    # returns: { removedErrorChecksums:[], updatedErrors:[], addedErrors[] }
    def calibrate(self, extrapolate):
        self.parts = []
        self.milestones = []
        self.errors = []
        self.allErrors_ = []

        if self.routeId is None:  # special case
            for line in self.lines:
                if not line.geo: continue
                origin = LrsOrigin(QgsWkbTypes.LineGeometry, line.fid)
                self.errors.append(LrsError(LrsError.NO_ROUTE_ID, line.geo, origins=[origin]))

            for point in self.points:
                if not point.geo: continue
                origin = LrsOrigin(QgsWkbTypes.PointGeometry, point.fid)
                self.errors.append(LrsError(LrsError.NO_ROUTE_ID, point.geo, origins=[origin]))

                # in addition it may be without measure
                if point.measure == None:
                    origin = LrsOrigin(QgsWkbTypes.PointGeometry, point.fid)
                    self.errors.append(LrsError(LrsError.NO_MEASURE, point.geo, origins=[origin]))

        elif len(self.lines) == 0:  # no lines -> orphan points
            for point in self.points:
                if not point.geo: continue
                origin = LrsOrigin(QgsWkbTypes.PointGeometry, point.fid)
                self.errors.append(
                    LrsError(LrsError.ORPHAN, point.geo, routeId=self.routeId, measure=point.measure, origins=[origin]))

                # in addition it may be without measure
                if point.measure == None:
                    origin = LrsOrigin(QgsWkbTypes.PointGeometry, point.fid)
                    self.errors.append(LrsError(LrsError.NO_MEASURE, point.geo, routeId=self.routeId, origins=[origin]))

        else:
            self.buildParts()
            self.createMilestones()
            self.attachMilestones()
            self.calibrateParts()
            if extrapolate:
                self.extrapolateParts()
            self.checkPartOverlaps()

    def calibrateAndGetUpdates(self, extrapolate):
        oldErrorChecksums = list(e.getChecksum() for e in self.getErrors())
        oldQualityChecksums = list(e.getChecksum() for e in self.getQualityFeatures())

        self.calibrate(extrapolate)

        newErrors = self.getErrors()
        newErrorChecksums = list(e.getChecksum() for e in newErrors)
        addedErrors = []
        updatedErrors = []
        removedErrorChecksums = []
        for checksum in oldErrorChecksums:
            if not checksum in newErrorChecksums:
                # debug ( 'removed error' )
                removedErrorChecksums.append(checksum)
        for error in newErrors:
            if error.getChecksum() in oldErrorChecksums:
                # debug ( 'updated error' )
                updatedErrors.append(error)
            else:
                # debug ( 'added error' )
                addedErrors.append(error)

        # simple remove and add for quality
        newQualityFeatures = self.getQualityFeatures()
        newQualityChecksums = list(f.getChecksum() for f in newQualityFeatures)
        addedQualityFeatures = []
        removedQualityChecksums = []
        for checksum in oldQualityChecksums:
            if not checksum in newQualityChecksums:
                removedQualityChecksums.append(checksum)
        for feature in newQualityFeatures:
            if not feature.getChecksum() in oldQualityChecksums:
                addedQualityFeatures.append(feature)

        return {'removedErrorChecksums': removedErrorChecksums,
                'updatedErrors': updatedErrors,
                'addedErrors': addedErrors,
                'removedQualityChecksums': removedQualityChecksums,
                'addedQualityFeatures': addedQualityFeatures}

    def getPartsNodes(self, parts):
        nodes = {}
        for part in parts:
            for i in [0, -1]:
                ph = pointHash(part.polyline[i])
                if not ph in nodes:
                    nodes[ph] = {'pnt': part.polyline[i], 'parts': [part]}
                else:
                    nodes[ph]['parts'].append(part)
        return nodes

    def joinParts(self, parts):
        # debug ( 'join %s parts' % ( len(parts)) )
        nodes = self.getPartsNodes(parts)
        joined = []
        while len(parts) > 0:
            part1 = parts.pop(0)
            joined.append(part1)
            polyline = part1.polyline
            while True:
                connected = False
                for part2 in parts:
                    polyline2 = part2.polyline

                    forks2 = [False, False]
                    for j in [0, -1]:
                        ph = pointHash(polyline2[j])
                        node = nodes[ph]
                        if len(node['parts']) > 2:
                            forks2[j] = True

                    if polyline[-1] == polyline2[0] and not forks2[0]:  # --1-->  --2-->
                        del polyline2[0]
                        polyline.extend(polyline2)
                        connected = True
                    elif polyline[-1] == polyline2[-1] and not forks2[-1]:  # --1--> <--2--
                        polyline2.reverse()
                        del polyline2[0]
                        polyline.extend(polyline2)
                        connected = True
                    elif polyline[0] == polyline2[-1] and not forks2[-1]:  # --2--> --1-->
                        del polyline[0]
                        polyline2.extend(polyline)
                        polyline = polyline2
                        connected = True
                    elif polyline[0] == polyline2[0] and not forks2[0]:  # <--2-- --1-->
                        polyline2.reverse()
                        del polyline[0]
                        polyline2.extend(polyline)
                        polyline = polyline2
                        connected = True

                    if connected:
                        part1.setPolyline(polyline)
                        part1.origins.extend(part2.origins)
                        parts.remove(part2)
                        break

                if not connected:  # no more parts can be connected
                    break
        # debug ( 'joined to %s parts' % ( len(joined)))
        return joined

    # create LrsRoutePart objects from geometryParts
    def buildParts(self):
        # debug ( 'routeId %s buildParts' % (self.routeId))
        self.parts = []
        polylines = []  # list of { polyline:, fid:, geoPart:, nGeoParts: }
        for line in self.lines:
            if not line.geo: continue
            # Qgis::singleType and flatType are not in bindings (2.0)
            polys = None  # list of QgsPolyline
            if QgsWkbTypes.isSingleType(line.geo.wkbType()):
                polys = [line.geo.asPolyline()]
            else:  # multi line
                polys = line.geo.asMultiPolyline()

            for i in range(len(polys)):
                poly = polys[i]

                if poly is None:
                    # TODO(?): report degenerated lines as errors
                    continue

                # clean duplicate coordinates
                for j in range(len(poly) - 1, 0, -1):
                    if poly[j].x() == poly[j - 1].x() and poly[j].y() == poly[j - 1].y():
                        del poly[j]

                if len(poly) < 2:
                    # TODO(?): report degenerated lines as errors
                    continue

                polylines.append({
                    'polyline': poly,
                    'fid': line.fid,
                    'geoPart': i,
                    'nGeoParts': len(polys),
                })

        # ------------------- snap ends -------------------
        if self.snap > 0:
            for i in range(len(polylines)):
                p1 = polylines[i]['polyline']
                # indexed by coor index:
                snapped = {0: False, -1: False}
                nearest = {0: None, -1: None}
                nearest_dist = {0: sys.float_info.max, -1: sys.float_info.max}
                for j in range(len(polylines)):
                    if j == i: continue
                    p2 = polylines[j]['polyline']
                    # debug ( '%s x %s' % (p1,p2) )
                    for ic in [0, -1]:
                        if not snapped[ic]:
                            if p1[ic] == p2[0] or p1[ic] == p2[-1]:
                                snapped[ic] = True
                            else:
                                for jc in [0, -1]:
                                    d = pointsDistance(p1[ic], p2[jc])
                                    if d <= self.snap and d < nearest_dist[ic]:
                                        nearest[ic] = [j, jc]
                                        nearest_dist[ic] = d
                # snap if not yet snapped and nearest found
                for ic in [0, -1]:
                    if not snapped[ic] and nearest[ic] is not None:
                        p2 = polylines[nearest[ic][0]]['polyline']
                        p1[ic] = p2[nearest[ic][1]]

        # ------------------- check for duplicates
        duplicates = set()
        for i in range(len(polylines) - 1):
            for j in range(i + 1, len(polylines)):
                if polylinesIdentical(polylines[i]['polyline'], polylines[j]['polyline']):
                    # debug( 'identical polylines %d and %d' % (i, j) )
                    duplicates.add(j)
        # make reverse ordered unique list of duplicates and delete
        duplicates = list(duplicates)
        duplicates.sort(reverse=True)
        for d in duplicates:  # delete going down (sorted reverse)
            geo = QgsGeometry.fromPolylineXY(polylines[d]['polyline'])
            origin = LrsOrigin(QgsWkbTypes.LineGeometry, polylines[d]['fid'], polylines[d]['geoPart'],
                               polylines[d]['nGeoParts'])
            self.errors.append(LrsError(LrsError.DUPLICATE_LINE, geo, routeId=self.routeId, origins=[origin]))
            del polylines[d]

        # ------------------- find forks -------------------
        nodes = {}
        for poly in polylines:
            polyline = poly['polyline']
            for i in [0, -1]:
                ph = pointHash(polyline[i])
                if not ph in nodes:
                    nodes[ph] = {'pnt': polyline[i], 'nlines': 1}
                else:
                    nodes[ph]['nlines'] += 1

        # moved to parallels block
        # for node in nodes.values():
        #    #debug( "nlines = %s" % node['nlines'] )
        #    if node['nlines'] > 2:
        #        geo = QgsGeometry.fromPoint( node['pnt'] )
        #        # origins sould not be necessary
        #        self.errors.append( LrsError( LrsError.FORK, geo, routeId = self.routeId ) )    

        # ------------------- join polylines to parts -------------------
        # TODO: similar code as joinParts, use common function
        while len(polylines) > 0:
            # polyline = polylines.pop(0)
            poly = polylines.pop(0)
            polyline = poly['polyline']
            origin = LrsOrigin(QgsWkbTypes.LineGeometry, poly['fid'], poly['geoPart'], poly['nGeoParts'])
            origins = [origin]
            while True:  # connect parts
                connected = False
                for i in range(len(polylines)):
                    # polyline2 = polylines[i]
                    poly2 = polylines[i]
                    polyline2 = poly2['polyline']

                    # don't connect in forks (we don't know which is better)
                    forks2 = [False, False]
                    for j in [0, -1]:
                        ph = pointHash(polyline2[j])
                        if nodes[ph]['nlines'] > 2:
                            forks2[j] = True

                    if polyline[-1] == polyline2[0] and not forks2[0]:  # --1-->  --2-->
                        del polyline2[0]
                        polyline.extend(polyline2)
                        connected = True
                    elif polyline[-1] == polyline2[-1] and not forks2[-1]:  # --1--> <--2--
                        polyline2.reverse()
                        del polyline2[0]
                        polyline.extend(polyline2)
                        connected = True
                    elif polyline[0] == polyline2[-1] and not forks2[-1]:  # --2--> --1-->
                        del polyline[0]
                        polyline2.extend(polyline)
                        polyline = polyline2
                        connected = True
                    elif polyline[0] == polyline2[0] and not forks2[0]:  # <--2-- --1-->
                        polyline2.reverse()
                        del polyline[0]
                        polyline2.extend(polyline)
                        polyline = polyline2
                        connected = True

                    if connected:
                        # print '%s part connected' % i
                        origin = LrsOrigin(QgsWkbTypes.LineGeometry, polylines[i]['fid'], polylines[i]['geoPart'],
                                           polylines[i]['nGeoParts'])
                        origins.append(origin)
                        del polylines[i]
                        break

                if not connected:  # no more parts can be connected
                    break

            part = LrsCalibPart(polyline, self.routeId, origins, self.crs, self.measureUnit, self.distanceArea)
            if part.length > 0:
                self.parts.append(part)
            else:
                # TODO(?): report degenerated lines as errors, should be catched already above however
                pass

        # debug ( 'num parts = %s' % len(self.parts) )
        # Find loops
        parallelParts = []
        for i in range(len(self.parts)):
            part1 = self.parts[i]
            if parallelParts and part1 in reduce(operator.add, parallelParts):  # already in parallels
                continue

            poly1 = part1.polyline
            parallels = []
            for j in range(len(self.parts)):
                if j == i: continue
                part2 = self.parts[j]
                poly2 = part2.polyline
                if (poly1[0] == poly2[0] and poly1[-1] == poly2[-1]) or (
                        poly1[0] == poly2[-1] and poly1[-1] == poly2[0]):
                    parallels.append(part2)

            if parallels:
                parallels.insert(0, part1)
                parallelParts.append(parallels)

        # if parallelParts:
        #    debug ( 'routeId %s parallelParts: %s' % (self.routeId, parallelParts ))

        for parallels in parallelParts:
            origins = []
            for part in parallels:
                origins.extend(part.origins)
                if self.parallelMode == 'error':
                    geo = QgsGeometry.fromPolylineXY(part.polyline)
                    self.errors.append(LrsError(LrsError.PARALLEL, geo, routeId=self.routeId, origins=part.origins))

                self.parts.remove(part)

            # forks
            if self.parallelMode == 'error':
                part = parallels[0]
                for i in [0, -1]:
                    geo = QgsGeometry.fromPointXY(part.polyline[i])
                    # origins sould not be necessary
                    self.errors.append(LrsError(LrsError.FORK, geo, routeId=self.routeId))

            if self.parallelMode == 'span':  # span by straight line
                part = parallels[0]
                polyline = [part.polyline[0], part.polyline[-1]]

                self.parts.append(
                    LrsCalibPart(polyline, self.routeId, origins, self.crs, self.measureUnit, self.distanceArea))

        # reconnect parts after parallels span
        if parallelParts and self.parallelMode == 'span':
            self.parts = self.joinParts(self.parts)

        # identify true forks (not parallels)
        nodes = self.getPartsNodes(self.parts)

        for node in nodes.values():
            if len(node['parts']) > 2:
                geo = QgsGeometry.fromPointXY(node['pnt'])
                self.errors.append(LrsError(LrsError.FORK, geo, routeId=self.routeId))
                # mark shortest forked parts as errors
        for ph, node in nodes.items():
            parts = node['parts']
            if len(parts) <= 2: continue

            parts.sort(key=lambda part: part.length)

            removeParts = parts[0:len(parts) - 2]
            for part in removeParts:
                # one part may be fork at both ends -> check if it was already removed
                if part in self.parts:
                    geo = QgsGeometry.fromPolylineXY(part.polyline)
                    self.errors.append(LrsError(LrsError.FORK_LINE, geo, routeId=self.routeId, origins=part.origins))
                    self.parts.remove(part)

        # join again after forks removed
        self.parts = self.joinParts(self.parts)

    def addPoint(self, point):
        self.points.append(point)

    def removePoint(self, fid):
        for i in range(len(self.points)):
            if self.points[i].fid == fid:
                del self.points[i]
                return

    def removeLine(self, fid):
        for i in range(len(self.lines)):
            if self.lines[i].fid == fid:
                del self.lines[i]
                return

    def createMilestones(self):
        self.milestones = []

        # check duplicates
        # TODO: maybe allow duplicates? Could be end/start of discontinuous segments
        nodes = {}
        for point in self.points:
            if not point.geo: continue

            if point.measure == None:
                origin = LrsOrigin(QgsWkbTypes.PointGeometry, point.fid)
                self.errors.append(LrsError(LrsError.NO_MEASURE, point.geo, routeId=self.routeId, origins=[origin]))
                continue

            pts = []
            if QgsWkbTypes.isSingleType(point.geo.wkbType()):
                pts = [point.geo.asPoint()]
            else:
                # multi (makes little sense)
                pts = point.geo.asMultiPoint()

            pnts = []  # list of { point:, geoPart: }
            for i in range(len(pts)):
                pnts.append({'point': pts[i], 'geoPart': i, 'nGeoParts': len(pts)})

            for p in pnts:
                pnt = p['point']
                ph = pointHash(pnt)

                origin = LrsOrigin(QgsWkbTypes.PointGeometry, point.fid, p['geoPart'], p['nGeoParts'])

                if not ph in nodes:
                    nodes[ph] = {
                        'pnt': pnt,
                        'npoints': 1,
                        'measures': [point.measure],
                        # 'fids': [ point.fid ],
                        # 'geoPart': [ p['geoPart'] ],
                        'origins': [origin]
                    }
                else:
                    nodes[ph]['npoints'] += 1
                    nodes[ph]['measures'].append(point.measure)
                    # nodes[ ph ]['fids'].append( point.fid )
                    # nodes[ ph ]['geoPart'].append( ['geoPart'] )
                    nodes[ph]['origins'].append(origin)

        for node in nodes.values():
            # debug ( "npoints = %s" % node['npoints'] )
            if node['npoints'] > 1:
                geo = QgsGeometry.fromPointXY(node['pnt'])
                self.errors.append(
                    LrsError(LrsError.DUPLICATE_POINT, geo, routeId=self.routeId, measure=node['measures'],
                             origins=node['origins']))

            measure = node['measures'][0]  # first if duplicates, for now
            self.milestones.append(
                LrsMilestone(node['origins'][0].fid, node['origins'][0].geoPart, node['origins'][0].nGeoParts,
                             node['pnt'], measure))

    # calculate measures along parts
    def attachMilestones(self):
        if self.routeId is None:
            return

        sqrThreshold = self.threshold * self.threshold
        for milestone in self.milestones:
            pointGeo = QgsGeometry.fromPointXY(milestone.pnt)

            nearSqDist = sys.float_info.max
            nearPartIdx = None
            nearSegment = None
            nearNearestPnt = None
            for i in range(len(self.parts)):
                part = self.parts[i]
                partGeo = QgsGeometry.fromPolylineXY(part.polyline)
                # use epsilon=0, see https://github.com/blazek/lrs/issues/15
                (sqDist, nearestPnt, afterVertex, leftOf) = partGeo.closestSegmentWithContext(milestone.pnt, 0)
                segment = afterVertex - 1
                # debug ('sqDist %s x %s' % (sqDist, sqrThreshold) )
                if sqDist <= sqrThreshold and sqDist < nearSqDist:
                    nearSqDist = sqDist
                    nearPartIdx = i
                    nearSegment = segment
                    nearNearestPnt = nearestPnt

            # debug ('nearest partIdx = %s segment = %s sqDist = %s' % ( nearPartIdx, nearSegment, nearSqDist) )
            if nearNearestPnt:  # found part in threshold
                milestone.partIdx = nearPartIdx
                nearPart = self.parts[nearPartIdx]
                milestone.partMeasure = measureAlongPolyline(nearPart.polyline, nearSegment, nearNearestPnt)

                nearPart.milestones.append(milestone)
            else:
                origin = LrsOrigin(QgsWkbTypes.PointGeometry, milestone.fid, milestone.geoPart, milestone.nGeoParts)
                self.errors.append(
                    LrsError(LrsError.OUTSIDE_THRESHOLD, pointGeo, routeId=self.routeId, measure=milestone.measure,
                             origins=[origin]))

    def calibrateParts(self):
        for part in self.parts:
            part.calibrate()

    def extrapolateParts(self):
        for part in self.parts:
            part.extrapolate()

    def getErrors(self):
        if not self.allErrors_:
            self.allErrors_ = list(self.errors)
            for part in self.parts:
                self.allErrors_.extend(part.getErrors())
        return self.allErrors_

    def getSegments(self):
        segments = []
        for part in self.parts:
            segments.extend(part.getSegments())
        return segments

    def getQualityFeatures(self):
        features = []
        fields = LrsQualityFields()
        for segment in self.getSegments():
            # m_len = self.mapUnitsPerMeasureUnit * (segment.record.milestoneTo - segment.record.milestoneFrom)
            m_len = segment.record.milestoneTo - segment.record.milestoneFrom
            # length = segment.geo.length()
            length = self.distanceArea.measureLength(segment.geo)
            qgisUnit = QgsUnitTypes.DistanceMeters if self.distanceArea.willUseEllipsoid() else self.crs.mapUnits()
            length = convertDistanceUnits(length, qgisUnit, self.measureUnit)
            err_abs = m_len - length
            err_rel = err_abs / length if length > 0 else 0
            feature = LrsQualityFeature()
            feature.setGeometry(segment.geo)
            feature.setAttribute('route', '%s' % segment.routeId)
            feature.setAttribute('m_from', segment.record.milestoneFrom)
            feature.setAttribute('m_to', segment.record.milestoneTo)
            feature.setAttribute('m_len', m_len)
            feature.setAttribute('len', length)
            feature.setAttribute('err_abs', err_abs)
            feature.setAttribute('err_rel', err_rel)
            feature.setAttribute('err_perc', abs(err_rel) * 100)
            features.append(feature)

        return features

    def getGoodMilestones(self):
        goodMilestones = []
        for part in self.parts:
            goodMilestones.extend(part.getGoodMilestones())
        return goodMilestones

    # Get sum of lengths with correct LRS in map units
    def getGoodLength(self):
        length = 0
        for part in self.parts:
            length += part.getGoodLength()
        return length

