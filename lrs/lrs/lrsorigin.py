from hashlib import md5


class LrsOrigin(object):
    def __init__(self, geoType, fid, geoPart=-1, nGeoParts=-1):
        self.geoType = geoType  # QgsWkbTypes.PointGeometry or QgsWkbTypes.LineGeometry
        self.fid = fid
        # geoPart and nGeoParts are -1 if the origin is full geometry, e.g. NO_ROUTE_ID
        self.geoPart = geoPart
        self.nGeoParts = nGeoParts  # number of geometry parts in feature

    def getChecksum(self):
        s = "%s-%s-%s-%s" % (self.geoType, self.fid, self.geoPart, self.nGeoParts)
        m = md5(s.encode())
        return m.digest()


