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
from time import sleep

from .error.lrserror import *
from .lrsbase import LrsBase
from .lrslayerpart import LrsLayerPart
from .lrslayerroute import LrsLayerRoute


# The class representing existing layer with measures
class LrsLayer(LrsBase):
    def __init__(self, layer, **kwargs):
        super(LrsLayer, self).__init__(**kwargs)
        self.layer = layer
        self.crs = layer.crs()
        self.routeFieldName = None  # field name

    def setRouteFieldName(self, routeField):
        self.routeFieldName = routeField

    # load from layer
    def load(self, progressFunction):
        debug("load %s %s" % (self.layer.name(), self.routeFieldName))
        self.reset()
        if not self.routeFieldName:
            return
        total = self.layer.featureCount()
        count = 0
        for feature in self.layer.getFeatures():
            # sleep(1)  # progress debug
            geo = feature.geometry()
            # if geo:
            #     if self.lineTransform:
            #         geo.transform(self.lineTransform)

            routeId = feature[self.routeFieldName]
            route = self.getRoute(routeId)
            #line = LrsLine(feature.id(), routeId, geo)
            #self.lines[feature.id()] = line
            if geo:
                for g in geo.asGeometryCollection():
                    part = LrsLayerPart(g)
                    route.addPart(part)

            count += 1
            percent = 100 * count / total;
            progressFunction(percent)

        for route in self.routes.values():
            route.checkPartOverlaps()

    # get route by id, create it if does not exist
    # routeId does not have to be normalized
    def getRoute(self, routeId):
        normalId = normalizeRouteId(routeId)
        # debug ( 'normalId = %s orig type = %s' % (normalId, type(routeId) ) )
        if normalId not in self.routes:
            self.routes[normalId] = LrsLayerRoute(routeId, parallelMode='error')
        return self.routes[normalId]

    def getRouteIds(self):
        #debug("getRouteIds routeFieldName = %s" % self.routeFieldName)
        if not self.layer or not self.routeFieldName:
            return []
        ids = set()
        for feature in self.layer.getFeatures():
            ids.add(feature[self.routeFieldName])
        ids = list(ids)
        ids.sort()
        return ids

