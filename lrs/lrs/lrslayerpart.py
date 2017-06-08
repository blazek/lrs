import math

from qgis.core import QgsPointXY
from .utils import pointOnLine, pointsDistance, debug
from .lrsrecord import LrsRecord
from .lrspartbase import LrsPartBase


class LrsLayerPart(LrsPartBase):
    def __init__(self, polylineGeo):
        super(LrsLayerPart, self).__init__()
        self.polylineGeo = polylineGeo  # single polyline geometry
        self.polyline = polylineGeo.asPolyline()
        self.length = self.polylineGeo.length()
        self.linestring = self.polylineGeo.geometry()  # QgsLineString
        if self.linestring and self.linestring.numPoints() > 1:
            measure1 = self.linestring.mAt(0)
            measure2 = self.linestring.mAt(self.linestring.numPoints() - 1)
            # debug('LrsLayerRoutePart %s - %s : %s - %s' % (measure1, measure2, 0, self.length))
            record = LrsRecord(measure1, measure2, 0, self.length)
            self.records.append(record)

    # overridden
    def eventPoint(self, start):
        #debug("eventPoint start = %s" % start)
        if start is None:
            return None
        start = float(start)
        if self.records:  # we may have 1 or none (if removed duplicate)
            if self.records[0].containsMeasure(start):
                return self.linestringPoint(start)
        return None

    # get point on linestring with measures
    # returns QgsPointXY
    # Note that there is QgsGeometryAnalyzer.locateAlongMeasure()
    def linestringPoint(self, measure):
        #debug("linestringPoint measure = %s" % measure)
        if self.linestring.numPoints() < 2:
            return None
        for i in range(self.linestring.numPoints() - 1):
            measure1 = self.linestring.mAt(i)
            measure2 = self.linestring.mAt(i + 1)
            #debug("linestringPoint measure1 = %s  measure2 = %s" % (measure1, measure2))
            if measure1 == measure:
                return QgsPointXY(self.linestring.pointN(i))
            elif measure2 == measure:
                return QgsPointXY(self.linestring.pointN(i + 1))
            elif measure1 < measure < measure2:
                point1 = self.linestring.pointN(i)
                point2 = self.linestring.pointN(i + 1)
                length = pointsDistance(point1,point2)
                distance = (measure - measure1) * length / (measure2 - measure1)
                return pointOnLine(self.linestring.pointN(i), self.linestring.pointN(i + 1), distance)
        return None

    # overridden
    def eventSegments(self, start, end):
        #debug("eventMultiPolyLine start = %s end = %s" % (start, end))
        segments = []
        if start is None or end is None:
            return segments
        start = float(start)
        end = float(end)

        if self.records:  # we may have 1 or none (if removed duplicate)
            rec = LrsRecord(start, end, None, None)
            if self.records[0].measureOverlaps(rec):
                segment = self.linestringSegment(start, end)
                if segment:
                    segments.append(segment)

        return segments

    # return [ QgsPolyline, measure_from, measure_to ]
    # Note that there is QgsGeometryAnalyzer.locateBetweenMeasures()
    def linestringSegment(self, start, end):
        if self.linestring.numPoints() < 2:
            return None
        polyline = []
        minMeasure = self.linestring.mAt(0)
        maxMeasure = self.linestring.mAt(self.linestring.numPoints() - 1)
        fromMeasure = max(start, minMeasure)
        toMeasure = min(end, maxMeasure)

        if start >= minMeasure:  # start point is on linestring
            polyline.append(self.linestringPoint(start))

        for i in range(self.linestring.numPoints()):
            measure = self.linestring.mAt(i)
            if start < measure < end:
                polyline.append(QgsPointXY(self.linestring.pointN(i)))

        if end <= maxMeasure:  # end point is on linestring
            polyline.append(self.linestringPoint(end))

        return [polyline, fromMeasure, toMeasure]

    # overridden
    def pointMeasure(self, point):
        (sqDist, nearestPoint, afterVertex) = self.polylineGeo.closestSegmentWithContext(point)
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
