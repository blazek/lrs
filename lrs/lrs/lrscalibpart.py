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
from .error.lrserror import *
from .lrsorigin import LrsOrigin
from .lrspartbase import LrsPartBase
from .lrsrecord import LrsRecord
from .lrssegment import LrsSegment


# Route part loaded from LRS layer
# Chain of connected geometries for calibration
class LrsCalibPart(LrsPartBase):
    def __init__(self, polyline, routeId, origins, crs, measureUnit, distanceArea):
        # debug ('init route part' )
        super(LrsCalibPart, self).__init__()
        self.setPolyline(polyline)
        self.routeId = routeId
        self.origins = origins  # list of LrsOrigin
        self.crs = crs
        self.measureUnit = measureUnit
        self.distanceArea = distanceArea
        self.milestones = []  # LrsMilestone list, all input milestones
        self.goodMilestones = []  # milestones ok, used for LRS
        self.errors = []  # LrsError list

    def setPolyline(self, polyline):
        self.polyline = polyline
        # debug('setPolyline polyline: %s %s' % (type(polyline), polyline))
        # debug('setPolyline first: %s %s' % (type(polyline[0]), polyline[0]))
        # QgsGeometry.fromPolyline() returns None if polyline has only one point
        self.polylineGeo = QgsGeometry.fromPolylineXY(self.polyline)
        if self.polylineGeo is not None:
            self.length = self.polylineGeo.length()

    def calibrate(self):
        # debug ( 'calibrate part routeId = %s' % self.routeId )

        if len(self.milestones) < 2:
            self.errors.append(
                LrsError(LrsError.NOT_ENOUGH_MILESTONES, self.polylineGeo, routeId=self.routeId, origins=self.origins))
            return

        # create list of milestones sorted by partMeasure
        milestones = list(self.milestones)
        # sort by partMeasure and measure
        milestones.sort(key=lambda milestone: (milestone.partMeasure, milestone.measure))

        # for milestone in milestones:
        #    debug ( 'partMeasure = %s measure = %s' % ( milestone.partMeasure, milestone.measure ) )

        # find direction
        up = down = 0
        for i in range(len(milestones) - 1):
            if milestones[i].measure == milestones[i + 1].measure:
                # Could also be reported as error, but should not harm
                pass
            elif milestones[i].measure < milestones[i + 1].measure:
                up += 1
            else:
                down += 1

        if up == down:
            self.errors.append(
                LrsError(LrsError.DIRECTION_GUESS, self.polylineGeo, routeId=self.routeId, origins=self.origins))
            return
        elif down > up:  # revert
            self.polyline.reverse()
            self.setPolyline(self.polyline)  # create polylineGeo
            milestones.reverse()
            # recalculate partMeasures
            for milestone in milestones:
                milestone.partMeasure = self.length - milestone.partMeasure

        # remove milestones in wrong direction, to do it well is not trivial because
        # sequence of milestones in correct order may appear in wrong place, e.g.7,8,3,4
        # or it may happen that correct sequence is interrupted by wrong milestone but in
        # correct order respect to longest sequence e.g. 1,2,0,3,4,5
        # Algorithm: 
        #     While there are milestones in wrong order:
        #         * for each milestones calculate correctness score
        #         * mark as error all milestones with lowest score

        while True:
            done = True

            # calculate scores
            # score: number of milestones to which it is in correct order minus 
            #        number of milestones to which it is in wrong order,
            #        if both have the same measure, it is considered wrong order
            scores = []

            for i in range(len(milestones)):
                score = 0
                for j in range(len(milestones)):
                    if i == j: continue
                    mi = milestones[i].measure
                    mj = milestones[j].measure
                    if (i < j and mi < mj) or (i > j and mi > mj):
                        score += 1
                    else:
                        score -= 1  # includes equal measures
                        done = False  # at least one in wron order

                scores.append(score)

            if done:
                break  # all in correct order

            # find lowest score
            minScore = sys.maxsize
            for i in range(len(scores)):
                if scores[i] < minScore: minScore = scores[i]

            # mark all with lowest score as errors, if more neighbours have the same score
            # e.g. measures: 3,0,4,5, both 3 and 0 have score +1, both are marked as 
            # error because we cannot decide which is correct
            for i in range(len(milestones) - 1, -1, -1):
                if scores[i] == minScore:
                    m = milestones[i]
                    geo = QgsGeometry.fromPointXY(m.pnt)
                    origin = LrsOrigin(QgsWkbTypes.PointGeometry, m.fid, m.geoPart, m.nGeoParts)
                    self.errors.append(LrsError(LrsError.WRONG_MEASURE, geo, routeId=self.routeId, measure=m.measure,
                                                origins=[origin]))
                    del milestones[i]

        self.goodMilestones = milestones

        # create calibration table
        for i in range(len(milestones) - 1):
            m1 = milestones[i]
            m2 = milestones[i + 1]
            # usually should not happen, report as error?
            if doubleNear(m1.measure, m2.measure): continue
            if doubleNear(m1.partMeasure, m2.partMeasure): continue
            self.records.append(LrsRecord(m1.measure, m2.measure, m1.partMeasure, m2.partMeasure))

    # calculate segment measure in measure units, used for extrapolate
    def segmentLengthInMeasureUnits(self, partFrom, partTo):
        if self.distanceArea.willUseEllipsoid():
            polyline = polylineSegment(self.polyline, partFrom, partTo)
            geo = QgsGeometry.fromPolylineXY(polyline)
            length = self.distanceArea.measureLength(geo)
            qgisUnit = QgsUnitTypes.DistanceMeters
        else:
            length = partTo - partFrom
            qgisUnit = self.crs.mapUnits()
        length = convertDistanceUnits(length, qgisUnit, self.measureUnit)
        return length

    # extrapolate before and after (add calculated records)
    def extrapolate(self):
        # debug ('extrapolate part')
        if not self.records: return  # direction unknown

        record = self.records[0]
        if record.partFrom > 0 and not doubleNear(record.partFrom, 0):
            # measure = record.milestoneFrom - record.partFrom / self.mapUnitsPerMeasureUnit
            length = self.segmentLengthInMeasureUnits(0, record.partFrom)
            measure = record.milestoneFrom - length

            # debug ('routeId = %s measure = %s' % (self.routeId,measure) )
            self.records.insert(0, LrsRecord(measure, record.milestoneFrom, 0, record.partFrom))

        record = self.records[-1]
        # debug ('routeId = %s partTo = %s length = %s' % (self.routeId,record.partTo,self.length) )
        if record.partTo < self.length and not doubleNear(record.partTo, self.length):
            # measure = record.milestoneTo + (self.length - record.partTo) / self.mapUnitsPerMeasureUnit
            length = self.segmentLengthInMeasureUnits(record.partTo, self.length)
            measure = record.milestoneTo + length
            # debug ('routeId = %s measure = %s' % (self.routeId,measure) )
            self.records.append(LrsRecord(record.milestoneTo, measure, record.partTo, self.length))

    def getGoodMilestones(self):
        return self.goodMilestones

    def getSegments(self):
        segments = []
        for record in self.records:
            geo = self.getRecordGeometry(record)
            segments.append(LrsSegment(self.routeId, record, geo))
        return segments

    # Get sum of lengths with correct LRS in map units
    def getGoodLength(self):
        length = 0
        for record in self.records:
            length += record.partTo - record.partFrom
        return length

    def getErrors(self):
        return self.errors

    def getWktWithMeasures(self):
        # debug('getWktWithMeasures')
        coors = self.getCoordinatesWithMeasures()
        if not coors or len(coors) < 2: return None
        coors = ['%f %f %f' % (c[0], c[1], c[2]) for c in coors]
        return 'LINESTRINGM ( %s )' % ", ".join(coors)

    def getGeometryWithMeasures(self):
        # debug('getGeometryWithMeasures')
        coors = self.getCoordinatesWithMeasures()
        if not coors or len(coors) < 2: return None

        linestring = QgsLineString()
        for c in coors:
            point = QgsPoint(c[0], c[1])
            point.addMValue(c[2])
            linestring.addVertex(point)
        return 	QgsGeometry(linestring)

    # overridden
    def eventPoint(self, start):
        # debug( "part.eventPoint() start = %s" % start )
        if start is None:
            return None
        start = float(start)
        for record in self.records:
            if record.containsMeasure(start):
                m = record.partMeasure(start)
                point = polylinePoint(self.polyline, m)
                return point
        return None

    # overridden
    def eventSegments(self, start, end):
        # debug ( "eventSegments start = %s end = %s" % (start,end) )
        segments = []
        if start is None or end is None:
            return segments
        start = float(start)
        end = float(end)

        # segment values
        seg = LrsRecord(None, None, None, None)
        nRecords = len(self.records)
        for i in range(nRecords):
            record = self.records[i]
            nextRecord = self.records[i + 1] if i < nRecords - 1 else None

            if end < record.milestoneFrom:
                break

            # debug ( "record.milestoneFrom = %s record.milestoneTo = %s" % ( record.milestoneFrom, record.milestoneTo ) )
            if seg.milestoneFrom is None:
                if start <= record.milestoneFrom:
                    # debug ( "start before or at record.milestoneFrom" )
                    seg.milestoneFrom = record.milestoneFrom
                    seg.partFrom = record.partFrom
                elif record.measureWithin(start):
                    seg.milestoneFrom = start
                    seg.partFrom = record.partMeasure(start)

            if seg.milestoneFrom is not None:
                if end == record.milestoneTo:
                    # debug ( "end at record.milestoneTo" )
                    seg.milestoneTo = record.milestoneTo
                    seg.partTo = record.partTo
                elif record.measureWithin(end):
                    # debug ( "end within record" )
                    seg.milestoneTo = end
                    seg.partTo = record.partMeasure(end)
                elif nextRecord and record.continues(nextRecord):
                    # debug ( "next record continues" )
                    pass
                else:
                    # debug ( "seg.milestoneTo set tot record.milestoneTo" )
                    seg.milestoneTo = record.milestoneTo
                    seg.partTo = record.partTo

            if seg.milestoneTo is not None:
                polyline = polylineSegment(self.polyline, seg.partFrom, seg.partTo)
                segments.append([polyline, seg.milestoneFrom, seg.milestoneTo])

                start = seg.milestoneTo
                seg = LrsRecord(None, None, None, None)

            if doubleNear(start, end): break

        return segments

    # overridden
    def pointMeasure(self, point):
        geo = QgsGeometry.fromPolylineXY(self.polyline)
        (sqDist, nearestPoint, afterVertex) = geo.closestSegmentWithContext(point)
        segment = afterVertex - 1
        partMeasure = measureAlongPolyline(self.polyline, segment, nearestPoint)
        return self.getMilestoneMeasure(partMeasure)

    def getMilestoneMeasure(self, partMeasure):
        for record in self.records:
            if record.containsPartMeasure(partMeasure):
                measure = record.measure(partMeasure)
                return measure

        return None

    # beginning of first record
    def milestoneMeasureFrom(self):
        if not self.records:
            return None
        return self.records[0].milestoneFrom

    # end of last record
    def milestoneMeasureTo(self):
        if not self.records: return None
        return self.records[-1].milestoneTo

    # return list of coordinates with measures [[x,y,m],...]
    # for valid LRS
    def getCoordinatesWithMeasures(self):
        # debug('getCoordinatesWithMeasures routeId = %s' % self.routeId )
        coors = []
        if not self.records: return coors

        # get measures for polyline
        partMeasure = 0
        for i in range(len(self.polyline)):
            if i > 0:
                partMeasure += segmentLength(self.polyline, i - 1)
            # debug('partMeasure = %s' % partMeasure )
            measure = self.getMilestoneMeasure(partMeasure)
            # debug('measure = %s' % measure )
            if measure is not None:
                point = self.polyline[i]
                coor = [point.x(), point.y(), measure]
                coors.append(coor)

        # debug('coors: %s' % coors )
        # add coordinates for milestones
        for record in self.records:
            point = polylinePoint(self.polyline, record.partFrom)
            if point:
                coor = [point.x(), point.y(), record.milestoneFrom]
                coors.append(coor)

        point = polylinePoint(self.polyline, self.records[-1].partTo)
        if point:
            coor = [point.x(), point.y(), self.records[-1].milestoneTo]
            coors.append(coor)

        # debug('coors: %s' % coors )

        # sort by measure
        coors.sort(key=lambda x: x[2])

        # remove coordinates too close each other
        for i in range(len(coors) - 1, 0, -1):
            if doubleNear(coors[i][2], coors[i - 1][2]):
                del coors[i]

        return coors