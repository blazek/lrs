from qgis._core import QgsFeature


class LrsFeature(QgsFeature):
    def __init__(self, fields):
        super(LrsFeature, self).__init__(fields)

    def getAttributeMap(self):
        attributeMap = {}
        for i in range(len(self.fields())):
            name = self.fields()[i].name()
            attributeMap[i] = self.attribute(name)
        return attributeMap