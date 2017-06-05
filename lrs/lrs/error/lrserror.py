# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsError
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
from hashlib import md5

from ..utils import *


# Origin of geometry part used for error checksums, it allows to update errors when
# geometry is changed, but error remains. 
# The identification by origin unfortunately fails if geometry part is deleted and thus
# geoPart numbers are changed. That is why there is also nGeoParts
# Class representing error in LRS
class LrsError(QObject):
    # Error type enums
    DUPLICATE_LINE = 1
    DUPLICATE_POINT = 2
    FORK = 3  # more than 2 lines connected in one node
    ORPHAN = 4  # orphan point, no line with such routeId
    OUTSIDE_THRESHOLD = 5  # out of the threshold from line
    NOT_ENOUGH_MILESTONES = 6  # part has less than 2 milestones attached
    NO_ROUTE_ID = 7  # missing route id
    NO_MEASURE = 8  # missing point measure attribute value
    DIRECTION_GUESS = 9  # cannot guess part direction
    WRONG_MEASURE = 10  # milestones in wrong position
    DUPLICATE_REFERENCING = 11  # multiple route segments measures overlap
    PARALLEL = 12  # parallel line
    FORK_LINE = 13  # parts connected in fork

    def __init__(self, type, geo, **kwargs):
        super(LrsError, self).__init__()
        self.type = type
        self.geo = QgsGeometry(geo)  # store copy of QgsGeometry
        self.message = kwargs.get('message', '')
        self.routeId = kwargs.get('routeId', None)
        self.measure = kwargs.get('measure', None)  # may be list !
        # self.lineFid = kwargs.get('lineFid', None)
        # self.pointFid = kwargs.get('pointFid', None) # may be list !
        # multigeometry part
        # self.geoPart = kwargs.get('geoPart', None) # may be list !
        self.origins = kwargs.get('origins', [])  # list of LrsOrigin

        # checksum cache
        self.originChecksum_ = None
        self.checksum_ = None
        # self.fullChecksum_ = None

        # initialized here to allow stranslation, how to translate static variables?
        self.typeLabels = {
            self.DUPLICATE_LINE: self.tr('Duplicate line'),
            self.DUPLICATE_POINT: self.tr('Duplicate point'),
            self.FORK: self.tr('Fork'),
            self.ORPHAN: self.tr('Orphan point'),
            self.OUTSIDE_THRESHOLD: self.tr('Out of threshold'),
            self.NOT_ENOUGH_MILESTONES: self.tr('Not enough points'),
            self.NO_ROUTE_ID: self.tr('Missing route id'),
            self.NO_MEASURE: self.tr('Missing measure'),
            self.DIRECTION_GUESS: self.tr('Cannot guess direction'),
            self.WRONG_MEASURE: self.tr('Wrong measure'),
            self.DUPLICATE_REFERENCING: self.tr('Duplicate referencing'),
            self.PARALLEL: self.tr('Parallel line'),
            self.FORK_LINE: self.tr('Fork line'),
        }

    def __str__(self):
        return "error: %s %s %s %s %s" % (self.type, self.typeLabel(), self.message, self.routeId, self.measure)

    def typeLabel(self):
        if not self.type in self.typeLabels:
            return "Unknown error"
        return self.typeLabels[self.type]

    # get string of simple value or list
    def getValueString(self, value):
        if value == None:
            return ""
        elif isinstance(value, list):
            vals = list(value)
            vals.sort()
            return " ".join(map(str, vals))
        else:
            return str(value)

    def getMeasureString(self):
        return self.getValueString(self.measure)

    # def getPointFidString(self):
    #    return self.getValueString ( self.pointFid )

    # def getGeoPartString(self):
    #    return self.getValueString ( self.geoPart )

    def getOriginChecksum(self):
        if not self.originChecksum_:
            checksums = []
            for origin in self.origins:
                checksums.append(origin.getChecksum())

            checksums.sort()

            m = md5()
            for checksum in checksums:
                m.update(checksum)
            self.originChecksum_ = m.digest()

        return self.originChecksum_

    # base checksum, mostly using origin, maybe used to update errors, 
    # calculation depends on error type
    def getChecksum(self):
        if not self.checksum_:
            m = md5(str(self.type).encode())

            if self.type == self.DUPLICATE_LINE:
                m.update(self.geo.exportToWkb())
            elif self.type == self.DUPLICATE_POINT:
                m.update(self.geo.exportToWkb())
            elif self.type == self.FORK:
                m.update(str(self.routeId).encode())
                m.update(self.geo.exportToWkb())
            elif self.type == self.ORPHAN:
                m.update(self.getOriginChecksum())
            elif self.type == self.OUTSIDE_THRESHOLD:
                m.update(self.getOriginChecksum())
            elif self.type == self.NOT_ENOUGH_MILESTONES:
                m.update(str(self.routeId).encode())
                m.update(self.getOriginChecksum())
            elif self.type == self.NO_ROUTE_ID:
                m.update(self.getOriginChecksum())
            elif self.type == self.NO_MEASURE:
                m.update(self.getOriginChecksum())
            elif self.type == self.DIRECTION_GUESS:
                m.update(self.getOriginChecksum())
            elif self.type == self.WRONG_MEASURE:
                m.update(self.getOriginChecksum())
            elif self.type == self.DUPLICATE_REFERENCING:
                m.update(str(self.routeId).encode())
                m.update(self.geo.exportToWkb())
                m.update(self.getMeasureString().encode())
            elif self.type == self.PARALLEL:
                m.update(self.getOriginChecksum())
            elif self.type == self.FORK_LINE:
                m.update(self.getOriginChecksum())

            self.checksum_ = m.digest()
        return self.checksum_

        # full checksum
        # def getFullChecksum(self):
        # if not self.fullChecksum_:
        # s  = "%s-%s-%s-%s-%s" % ( self.type, self.geo.exportToWkb(), self.routeId, self.getMeasureString(), self.getOriginChecksum() )
        # m = md5( s )
        # self.fullChecksum_ = m.digest()
        # return self.fullChecksum_

