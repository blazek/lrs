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
from ..utils import debug
from qgis.core import QgsCoordinateTransform, QgsProject


# Keeps track of features by checksum.
class LrsLayerManager(object):
    def __init__(self, layer):
        super(LrsLayerManager, self).__init__()
        self.layer = layer
        self.featureIds = {}  # dictionary of features with checksum keys

    # remove all features
    def clear(self):
        if not self.layer: return
        fids = []
        for feature in self.layer.getFeatures():
            fids.append(feature.id())

        self.layer.dataProvider().deleteFeatures(fids)

        for fid in fids:
            # hack to update attribute table
            self.layer.featureDeleted.emit(fid)

    # transform features if necessary to layer crs
    # modifies original feature geometry
    def transformFeatures(self, features, crs):
        if crs != self.layer.crs():
            transform = QgsCoordinateTransform(crs, self.layer.crs(), QgsProject.instance())
            for feature in features:
                # feature.geometry().transform(transform)  # does not work
                geo = feature.geometry()
                geo.transform(transform)
                feature.setGeometry(geo)
        return features

        # add features with getChecksum() method

    def addFeatures(self, features, crs):
        # debug('addFeatures layer.crs = {} features crs = {}'.format(self.layer.crs().authid(), crs.authid()))
        features = self.transformFeatures(features, crs)

        status, addedFeatures = self.layer.dataProvider().addFeatures(features)
        for feature, addedFeature in zip(features, addedFeatures):
            self.featureIds[feature.getChecksum()] = addedFeature.id()
            # hack to update attribute table
            self.layer.featureAdded.emit(addedFeature.id())

    # delete features by checksums
    def deleteChecksums(self, checksums):
        fids = []
        for checksum in checksums:
            fid = self.featureIds.get(checksum, None)
            if fid:
                fids.append(fid)

        if len(fids) > 0:
            self.layer.dataProvider().deleteFeatures(fids)

        for fid in fids:
            # hack to update attribute table
            self.layer.featureDeleted.emit(fid)

    def updateFeatures(self, features, crs):
        features = self.transformFeatures(features, crs)
        changedGeometries = {}
        changedAttributes = {}
        for feature in features:
            checksum = feature.getChecksum()
            fid = self.featureIds.get(checksum, None)
            if not fid: raise Exception("Error feature not found")
            changedGeometries[fid] = feature.geometry()
            changedAttributes[fid] = feature.getAttributeMap()
        # debug ( "changedGeometries: %s" % changedGeometries )
        self.layer.dataProvider().changeGeometryValues(changedGeometries)
        self.layer.dataProvider().changeAttributeValues(changedAttributes)

        # hack to update attribute table
        for fid, attr in changedAttributes.items():
            for i, value in attr.items():
                self.layer.attributeValueChanged.emit(fid, i, value)