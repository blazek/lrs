from PyQt5.QtCore import pyqtSignal, Qt, QModelIndex
from PyQt5.QtGui import QStandardItem
from qgis._core import QgsMapLayer, QgsProject, QgsWkbTypes

from ..lrs.utils import debug
from .lrscombomanagerbase import LrsComboManagerBase


class LrsLayerComboManager(LrsComboManagerBase):
    layerChanged = pyqtSignal(QgsMapLayer)

    def __init__(self, comboOrList, **kwargs):
        super(LrsLayerComboManager, self).__init__(comboOrList, **kwargs)
        self.geometryType = kwargs.get('geometryType', None)  # QgsWkbTypes.GeometryType
        self.geometryHasM = kwargs.get('geometryHasM', False)  # has measure

        self.connectCurrentIndexChanged()  # connect to this class method

        QgsProject.instance().layersAdded.connect(self.canvasLayersChanged)
        QgsProject.instance().layersRemoved.connect(self.canvasLayersChanged)
        # nameChanged is emitted by layer, see canvasLayersChanged

    def __del__(self):
        if not QgsProject:
            return
        QgsProject.instance().layersAdded.disconnect(self.canvasLayersChanged)
        QgsProject.instance().layersRemoved.disconnect(self.canvasLayersChanged)

    def currentIndexChanged(self, idx):
        debug("LrsLayerComboManager currentIndexChanged idx = %s" % idx)
        super(LrsLayerComboManager, self).currentIndexChanged(idx)
        self.layerChanged.emit(self.getLayer())

    def layerId(self):
        idx = self.comboList[0].currentIndex()
        if idx != -1:
            return self.comboList[0].itemData(idx, Qt.UserRole)
        return None

    def getLayer(self):
        if not QgsProject:
            return
        lId = self.layerId()
        return QgsProject.instance().mapLayer(lId)

    def canvasLayersChanged(self):
        self.debug("LrsLayerComboManager currentIndexChanged")
        self.reload()

    def reload(self):
        # https://qgis.org/api/classQgsMapLayerComboBox.html#af4d245f67261e82719290ca028224b3c
        self.debug("LrsLayerComboManager reload")

        if not QgsProject:
            return
        # layers = []
        # for layer in QgsProject.instance().mapLayers().values():
        #     print(layer)
        #     if layer.type() != QgsMapLayer.VectorLayer:
        #         continue
        #     if self.geometryType is not None and layer.geometryType() != self.geometryType:
        #         continue
        #     if self.geometryHasM and not QgsWkbTypes.hasM(layer.wkbType()):
        #         continue
        #     layers.append(layer)

        # delete removed layers
        for i in range(self.model.rowCount() - 1, -1, -1):
            lid = self.model.item(i).data(Qt.UserRole)
            if lid not in QgsProject.instance().mapLayers().keys():
                # debug("canvasLayersChanged remove lid = %s" % lid)
                self.model.removeRows(i, 1)

        # add new layers
        for layer in QgsProject.instance().mapLayers().values():
            # print(layer)
            if layer.type() != QgsMapLayer.VectorLayer:
                continue
            if self.geometryType is not None and layer.geometryType() != self.geometryType:
                continue
            if self.geometryHasM and not QgsWkbTypes.hasM(layer.wkbType()):
                continue

            start = self.model.index(0, 0, QModelIndex())
            indexes = self.model.match(start, Qt.UserRole, layer.id(), Qt.MatchFixedString)
            if len(indexes) == 0:  # add new
                item = QStandardItem(layer.name())
                item.setData(layer.id(), Qt.UserRole)
                self.model.appendRow(item)
                layer.nameChanged.connect(self.canvasLayersChanged)
            else:  # update text
                index = indexes[0]
                item = self.model.item(index.row(), index.column())
                item.setText(layer.name())

        self.proxy.sort(0)