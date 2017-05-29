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
from PyQt5.QtCore import QObject
from .utils import debug


# The class representing existing layer with measures
class LrsLayer(QObject):
    def __init__(self, layer):
        super(LrsLayer, self).__init__()
        self.layer = layer
        self.routeFieldName = None  # field name

    def setRouteFieldName(self, routeField):
        self.routeFieldName = routeField

    def getRouteIds(self):
        debug("getRouteIds routeFieldName = %s" % self.routeFieldName)
        if not self.layer or not self.routeFieldName:
            return []
        ids = set()
        for feature in self.layer.getFeatures():
            ids.add(feature[self.routeFieldName])
        ids = list(ids)
        ids.sort()
        return ids

