from abc import ABCMeta

from qgis._core import QgsGeometry

from .lrsrecord import LrsRecord
from .utils import polylinePoint, polylineSegment, doubleNear, measureAlongPolyline, segmentLength


# Route part
class LrsPartBase(metaclass=ABCMeta):
    def __init__(self):
        self.records = []  # LrsRecord list
        self.polyline = None
        self.polylineGeo = None
        self.length = 0

    def getRecords(self):
        return self.records

    def getMeasureRanges(self):
        ranges = []
        rang = None
        for record in self.records:
            if rang:
                if rang[1] == record.milestoneFrom:
                    rang[1] = record.milestoneTo
                    continue
                else:
                    rang = None

            if not rang:
                rang = [record.milestoneFrom, record.milestoneTo]
                ranges.append(rang)
        return ranges

    # returns QgsPoint or None
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

    # returns [ [ QgsPolyline, measure_from, measure_to ], ... ]
    def eventSegments(self, start, end):
        # debug ( "eventSegments start = %s end = %s" % (start,end) )
        segments = []
        if start is None or end is None: return segments
        start = float(start)
        end = float(end)

        # segment values
        seg = LrsRecord(None, None, None, None)
        nRecords = len(self.records)
        for i in range(nRecords):
            record = self.records[i]
            nextRecord = self.records[i + 1] if i < nRecords - 1 else None

            if end < record.milestoneFrom: break

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

    # get measure for nearest point on polyline
    # returns None if there is no record for the nearest point
    def pointMeasure(self, point):
        geo = QgsGeometry.fromPolyline(self.polyline)
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
        if not self.records: return None
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

    def getRecordGeometry(self, record):
        polyline = polylineSegment(self.polyline, record.partFrom, record.partTo)
        geo = QgsGeometry.fromPolyline(polyline)
        return geo

    def removeRecord(self, record):
        self.records.remove(record)

