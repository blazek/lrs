from .lrserrorfields import LRS_ERROR_FIELDS
from .lrsfeature import LrsFeature


class LrsErrorFeature(LrsFeature):
    def __init__(self, error):
        super(LrsErrorFeature, self).__init__(LRS_ERROR_FIELDS)
        error = error
        self.setGeometry(error.geo)
        self.checksum = error.getChecksum()

        values = {
            'error': error.typeLabel(),
            'route': '%s' % error.routeId,
            'measure': error.getMeasureString()
        }
        for name, value in values.items():
            self.setAttribute(name, value)

    def __str__(self):
        attributes = []
        for i in range(len(self.fields())):
            name = self.fields()[i].name()
            attributes.append( "%s:%s" % ( name, self.attribute(name) ) )
        s = "errorFeature: " + " ".join(attributes)
        if self.geometry():
            s += " " + self.geometry().exportToWkt()
        return s

    def getChecksum(self):
        return self.checksum