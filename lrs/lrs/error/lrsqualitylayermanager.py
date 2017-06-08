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
from .lrslayermanager import LrsLayerManager


class LrsQualityLayerManager(LrsLayerManager):
    def __init__(self, layer):
        super(LrsQualityLayerManager, self).__init__(layer)

    def update(self, errorUpdates):
        # debug ( "%s" % errorUpdates )
        if not self.layer:
            return

        # delete
        self.deleteChecksums(errorUpdates['removedQualityChecksums'])

        # no update, only remove and add

        # add new
        self.addFeatures(errorUpdates['addedQualityFeatures'], errorUpdates['crs'])