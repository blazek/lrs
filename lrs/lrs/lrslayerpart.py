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
 ***************************************************************************/
"""
import math
from qgis.core import QgsPoint, QgsPointXY
from .utils import pointXYOnLine, pointsDistance, debug, offsetPt
from .lrsrecord import LrsRecord
from .lrspartbase import LrsPartBase


class LrsLayerPart(LrsPartBase):
    def __init__(self, polylineGeo):
        super(LrsLayerPart, self).__init__()
        self.polylineGeo = polylineGeo  # single polyline geometry
        self.polyline = polylineGeo.asPolyline()
        self.length = self.polylineGeo.length()
        self.linestring = self.polylineGeo.get()  # QgsLineString
        if self.linestring and self.linestring.numPoints() > 1:
            measure1 = self.linestring.mAt(0)
            measure2 = self.linestring.mAt(self.linestring.numPoints() - 1)
            # debug('LrsLayerRoutePart %s - %s : %s - %s' % (measure1, measure2, 0, self.length))
            record = LrsRecord(measure1, measure2, 0, self.length)
            self.records.append(record)

    # overridden
    def eventPointXY(self, start, startOffset=0.0):
        #debug("eventPoint start = %s" % start)
        if start is None:
            return None
        start = float(start)
        if self.records:  # we may have 1 or none (if removed duplicate)
            if self.records[0].containsMeasure(start):
                return self.linestringPointXY(start, startOffset)
        return None

    # get point on linestring with measures
    # returns QgsPointXY
    # Note that there is QgsGeometryAnalyzer.locateAlongMeasure()
    # But QGIS 3 : QgsGeometryAnalyzer. Use the equivalent Processing algorithms instead
    # See QgsGeometryUtils linePerpendicularAngle() interpolatePointOnLine()
    def linestringPointXY(self, measure, offset=0.0):
        #debug("linestringPoint measure = %s" % measure)
        if self.linestring.numPoints() < 2:
            return None
        #offset = 0.0
        for i in range(self.linestring.numPoints() - 1):
            measure1 = self.linestring.mAt(i)
            measure2 = self.linestring.mAt(i + 1)
            #debug("linestringPoint measure1 = %s  measure2 = %s" % (measure1, measure2))

            if measure1 == measure:
                # Offset
                point1 = self.linestring.pointN(i - 1)
                point2 = self.linestring.pointN(i)
                if offset != 0.0:
                    pt = offsetPt(point1, point2, offset)
                else:
                    pt = QgsPointXY(self.linestring.pointN(i))

                #return QgsPointXY(self.linestring.pointN(i))
                return pt
            elif measure2 == measure:
                # Offset
                point1 = self.linestring.pointN(i)
                point2 = self.linestring.pointN(i + 1)
                if offset != 0.0:
                    pt = offsetPt(point1, point2, offset)
                else:
                    pt = QgsPointXY(self.linestring.pointN(i + 1))

                #return QgsPointXY(self.linestring.pointN(i + 1))
                return pt
            elif measure1 < measure < measure2:
                point1 = self.linestring.pointN(i)
                point2 = self.linestring.pointN(i + 1)
                length = pointsDistance(point1, point2)
                distance = (measure - measure1) * length / (measure2 - measure1)
                #return pointXYOnLine(self.linestring.pointN(i), self.linestring.pointN(i + 1), distance)
                return pointXYOnLine(self.linestring.pointN(i), self.linestring.pointN(i + 1), distance, offset)
        return None

    # overridden
    def eventSegments(self, start, end, oStart=0.0, oEnd=0.0):
        #debug("eventMultiPolyLine start = %s end = %s" % (start, end))
        segments = []
        if start is None or end is None:
            return segments
        start = float(start)
        end = float(end)

        if self.records:  # we may have 1 or none (if removed duplicate)
            rec = LrsRecord(min(start, end), max(start, end), None, None)
            if self.records[0].measureOverlaps(rec):
                segment = self.linestringSegment(start, end, oStart, oEnd)
                if segment:
                    segments.append(segment)

        return segments

    # return [ QgsPolyline, measure_from, measure_to ]
    # Note that there is QgsGeometryAnalyzer.locateBetweenMeasures()
    def linestringSegment(self, start, end, oStart=0.0, oEnd=0.0):
        #debug('offset %s - %s' % (oStart, oEnd))
        if self.linestring.numPoints() < 2:
            return None
        polyline = []
        minMeasure = self.linestring.mAt(0)
        maxMeasure = self.linestring.mAt(self.linestring.numPoints() - 1)
        fromMeasure = max(start, minMeasure) if start <= end else min(start, maxMeasure)
        toMeasure = min(end, maxMeasure) if start <= end else max(end, minMeasure)

        # map the given start and end measures (which may specify a linear
        # event in either direction) to measures within the linestring, which
        # always increase uniformly
        linestringSegmentStart = min(start, end)
        linestringSegmentEnd = max(start, end)

        if linestringSegmentStart >= minMeasure:  # start point is on linestring
            polyline.append(self.linestringPointXY(linestringSegmentStart, oStart))

        # Incremental offset
        iOffset = (oEnd - oStart) / (toMeasure - fromMeasure)

        for i in range(self.linestring.numPoints()):
            measure = self.linestring.mAt(i)
            if linestringSegmentStart < measure < linestringSegmentEnd:
                # Offset
                if oStart != 0.0:
                    if oStart != oEnd:
                        dOffset = iOffset * (self.linestring.mAt(i) - fromMeasure)
                        offset = oStart + dOffset
                        #debug('oS %s oE %s dO %s MaxM %s M %s ' % (oStart, oEnd, dOffset, maxMeasure, self.linestring.mAt(i)))
                        #debug('oS %s oE %s dO %s iO %s M %s ' % (oStart, oEnd, dOffset, iOffset, self.linestring.mAt(i)))
                    else:
                        offset = oStart

                    polyline.append(offsetPt(
                        QgsPointXY(self.linestring.pointN(i-1)),
                        QgsPointXY(self.linestring.pointN(i)), 
                        offset))
                    
                else:
                    polyline.append(QgsPointXY(self.linestring.pointN(i)))

        if linestringSegmentEnd <= maxMeasure:  # end point is on linestring
            polyline.append(self.linestringPointXY(linestringSegmentEnd, oEnd))

        # if the given start and end measures specify a linear event in the
        # opposite direction, reverse the direction of the segment to match
        if start > end:
            polyline = reversed(polyline)

        return [polyline, fromMeasure, toMeasure]

    # overridden
    def pointMeasure(self, point):
        (sqDist, nearestPoint, afterVertex, leftOf) = self.polylineGeo.closestSegmentWithContext(point, 0)
        if afterVertex == 0:
            return self.linestring.mAt(0)
        else:
            measure1 = self.linestring.mAt(afterVertex - 1)
            measure2 = self.linestring.mAt(afterVertex)
            point1 = self.linestring.pointN(afterVertex - 1)
            point2 = self.linestring.pointN(afterVertex)
            distance = pointsDistance(point1, nearestPoint)
            length = pointsDistance(point1, point2)
            measure = measure1 + (measure2 - measure1) * distance / length
            return measure
