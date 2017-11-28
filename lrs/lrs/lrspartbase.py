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
"""
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
        geo = QgsGeometry.fromPolylineXY(polyline)
        return geo

    def __str__(self):
        return "part %s" % ",".join( list("%s" %r for r in self.records) )

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