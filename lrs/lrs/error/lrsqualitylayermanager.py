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