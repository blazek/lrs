from abc import ABCMeta, abstractmethod

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

    def removeRecord(self, record):
        self.records.remove(record)

    def getRecordGeometry(self, record):
        polyline = polylineSegment(self.polyline, record.partFrom, record.partTo)
        geo = QgsGeometry.fromPolyline(polyline)
        return geo

    # returns QgsPointXY or None
    @abstractmethod
    def eventPoint(self, start):
        pass

    # returns [ [ QgsPolyline, measure_from, measure_to ], ... ]
    @abstractmethod
    def eventSegments(self, start, end):
        pass

    # get measure for nearest point on polyline
    # returns None if there is no record for the nearest point
    @abstractmethod
    def pointMeasure(self, point):
        pass