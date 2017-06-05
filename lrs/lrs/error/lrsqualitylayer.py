from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from qgis._core import QgsVectorLayer, QgsProviderRegistry, QgsWkbTypes

from .lrsqualityfields import LRS_QUALITY_FIELDS
from ..utils import crsString


class LrsQualityLayer(QgsVectorLayer):
    def __init__(self, crs):
        uri = "LineString?crs=%s" % crsString(crs)
        provider = QgsProviderRegistry.instance().createProvider('memory', uri)
        provider.addAttributes(LRS_QUALITY_FIELDS.toList())
        uri = provider.dataSourceUri()
        super(LrsQualityLayer, self).__init__(uri, 'LRS quality', 'memory')

        # min, max, color, label
        styles = [
            [0, 10, QColor(Qt.green), '0 - 10 % error'],
            [10, 30, QColor(Qt.blue), '10 - 30 % error'],
            [30, 1000000, QColor(Qt.red), '> 30 % error']
        ]
        ranges = []
        for style in styles:
            symbol = QgsSymbolV2.defaultSymbol(QgsWkbTypes.LineGeometry)
            symbol.setColor(style[2])
            range = QgsRendererRangeV2(style[0], style[1], symbol, style[3])
            ranges.append(range)

        renderer = QgsGraduatedSymbolRendererV2('err_perc', ranges)
        self.setRendererV2(renderer)


