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
from hashlib import md5

from .lrsfeature import LrsFeature
from .lrsqualityfields import LRS_QUALITY_FIELDS


class LrsQualityFeature(LrsFeature):
    def __init__(self):
        super(LrsQualityFeature, self).__init__(LRS_QUALITY_FIELDS)
        self.checksum_ = None

    # full checksum, cannot be used to update existing feature because contains
    # geometry + all attributes
    def getChecksum(self):
        if not self.checksum_:
            #m = md5("%s" % self.geometry().exportToWkb())
            m = md5(self.geometry().exportToWkb())

            for attribute in self.attributes():
                m.update(str(attribute).encode())

            self.checksum_ = m.digest()
        return self.checksum_


