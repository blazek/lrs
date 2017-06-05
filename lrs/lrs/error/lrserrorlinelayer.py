from .lrserrorlayer import LrsErrorLayer
from ..utils import crsString


class LrsErrorLineLayer(LrsErrorLayer):
    def __init__(self, crs):
        uri = "LineString?crs=%s" % crsString(crs)
        super(LrsErrorLineLayer, self).__init__(uri, 'LRS line errors')