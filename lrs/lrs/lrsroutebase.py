import sys
from abc import ABCMeta

from .error.lrserror import LrsError
from .utils import LrsUnits, formatMeasure, doubleNear


class LrsRouteBase(metaclass=ABCMeta):
    def __init__(self,routeId,**kwargs):
        self.routeId = routeId  # if None, keeps all lines and points without routeId
        self.measureUnit = LrsUnits.UNKNOWN
        # parallelMode, http://en.wikipedia.org/wiki/Multiple_edges:
        # 'error', 'exclude' (do not include in parts), span (replace by straight line)
        self.parallelMode = kwargs.get('parallelMode', 'error')
        self.parts = []  # LrsRoutePart subclasses list
        self.errors = []  # LrsError list of route errors

    def addPart(self, part):
        self.parts.append(part)

    def getMeasureRanges(self):
        ranges = []
        for part in self.parts:
            ranges.extend(part.getMeasureRanges())
        ranges.sort()
        return ranges

    def checkPartOverlaps(self):
        records = []
        overlaps = set()
        recordParts = {}
        for part in self.parts:
            for record in part.getRecords():
                records.append(record)
                recordParts[record] = part
        for record in records:
            for record2 in records:
                if record2 is record: continue
                if record.measureOverlaps(record2):
                    overlaps.add(record)

        # debug("overlaps: %s" % overlaps )
        for record in overlaps:
            part = recordParts[record]
            geo = part.getRecordGeometry(record)
            measureFrom = formatMeasure(record.milestoneFrom, self.measureUnit)
            measureTo = formatMeasure(record.milestoneTo, self.measureUnit)
            self.errors.append(
                LrsError(LrsError.DUPLICATE_REFERENCING, geo, routeId=self.routeId, measure=[measureFrom, measureTo]))
            part.removeRecord(record)

    # returns ( QgsPoint, error )
    def eventPoint(self, start, tolerance=0):
        for part in self.parts:
            point = part.eventPoint(start)
            if point:
                return point, None

        # try with tolerance
        if tolerance > 0:
            nearestPoint = None
            nearestMeasure = sys.float_info.max
            for part in self.parts:
                for record in part.records:
                    m = abs(record.milestoneFrom - start)
                    if m <= tolerance and m < nearestMeasure:
                        nearestPoint = part.eventPoint(record.milestoneFrom)
                        nearestMeasure = m

                    m = abs(record.milestoneTo - start)
                    if m <= tolerance and m < nearestMeasure:
                        nearestPoint = part.eventPoint(record.milestoneTo)
                        nearestMeasure = m

            if nearestPoint: return nearestPoint, None

        return None, 'measure not available'

    # returns ( QgsMultiPolyline, error )
    def eventMultiPolyLine(self, start, end, tolerance=0):
        multipolyline = []
        measures = []
        for part in self.parts:
            segments = part.eventSegments(start, end)
            for polyline, measure_from, measure_to in segments:
                multipolyline.append(polyline)
                measures.append([measure_from, measure_to])

        error = None
        if len(multipolyline) == 0:
            multipolyline = None
            error = 'segment not available'
        else:
            # make error message  for gaps
            measures.sort()
            # debug( '%s' % measures )
            for i in range(len(measures) - 1, 0, -1):
                if doubleNear(measures[i][0], measures[i - 1][1]):
                    measures[i - 1][1] = measures[i][1]
                    del measures[i]

            if start < measures[0][0]:
                measures.insert(0, [start, start])

            if end > measures[-1][1]:
                measures.append([end, end])

            gaps = []

            for i in range(len(measures) - 1):
                measureFrom = measures[i][1]
                measureTo = measures[i + 1][0]
                if measureTo - measureFrom < tolerance:
                    continue

                # measures are not formated (rounded) to show to user real data and dont hidden the true error by rounding
                gaps.append('%s-%s' % (measureFrom, measureTo))

            if gaps:
                error = 'segments %s not available' % ', '.join(gaps)
                # debug( error )

        # debug( '%s' % measures )
        return multipolyline, error


