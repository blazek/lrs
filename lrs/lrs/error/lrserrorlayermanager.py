from qgis._core import QgsWkbTypes

from .lrslayermanager import LrsLayerManager
from .lrserrorfeature import LrsErrorFeature


class LrsErrorLayerManager(LrsLayerManager):
    def __init__(self, layer):
        super(LrsErrorLayerManager, self).__init__(layer)

    # test if error geometry type matches this layer
    def errorTypeMatch(self, error):
        if self.layer.geometryType() == QgsWkbTypes.PointGeometry and error.geo.type() != QgsWkbTypes.PointGeometry:
            return False
        if self.layer.geometryType() == QgsWkbTypes.LineGeometry and error.geo.type() != QgsWkbTypes.LineGeometry:
            return False
        return True

    # get errors of layer type (point or line)
    def addErrors(self, errors, crs):
        if not self.layer:
            return
        #debug("addErrors geometryType = %s" % self.layer.geometryType())

        features = []
        for error in errors:
            #debug("addErrors %s" % error)
            if not self.errorTypeMatch(error):
                continue
            feature = LrsErrorFeature(error)
            #debug("addErrors %s" % feature)
            features.append(feature)

        self.addFeatures(features, crs)

    def updateErrors(self, errorUpdates):
        # debug ( "%s" % errorUpdates )
        if not self.layer:
            return

        # delete
        self.deleteChecksums(errorUpdates['removedErrorChecksums'])

        # update
        features = []
        for error in errorUpdates['updatedErrors']:
            if not self.errorTypeMatch(error):
                continue

            feature = LrsErrorFeature(error)
            features.append(feature)
        self.updateFeatures(features, errorUpdates['crs'])

        # add new
        self.addErrors(errorUpdates['addedErrors'], errorUpdates['crs'])