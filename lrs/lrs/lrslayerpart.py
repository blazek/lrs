from .lrsrecord import LrsRecord
from .lrspartbase import LrsPartBase


class LrsLayerPart(LrsPartBase):
    def __init__(self, polylineGeo):
        super(LrsLayerPart, self).__init__()
        self.polylineGeo = polylineGeo  # single polyline geometry
        self.polyline = polylineGeo.asPolyline()
        self.length = self.polylineGeo.length()
        linestring = self.polylineGeo.geometry()  # QgsLineString
        if linestring and linestring.numPoints() > 1:
            measure1 = linestring.mAt(0)
            measure2 = linestring.mAt(linestring.numPoints()-1)
            #debug('LrsLayerRoutePart %s - %s : %s - %s' % (measure1, measure2, 0, self.length))
            record = LrsRecord(measure1, measure2, 0, self.length)
            self.records.append(record)


