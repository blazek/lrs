class LrsSegment:
    def __init__(self, routeId, record, geo):
        self.routeId = routeId
        self.record = record  # LrsRecord
        self.geo = geo  # QgsGeometry