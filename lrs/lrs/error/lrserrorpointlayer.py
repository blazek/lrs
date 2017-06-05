from .lrserrorlayer import LrsErrorLayer
from ..utils import crsString


class LrsErrorPointLayer(LrsErrorLayer):
    def __init__(self, crs):
        uri = "Point?crs=%s" % crsString(crs)
        super(LrsErrorPointLayer, self).__init__(uri, 'LRS point errors')