from PyQt5.QtCore import QVariant
from qgis._core import QgsFields, QgsField


class LrsErrorFields(QgsFields):
    def __init__(self):
        super(LrsErrorFields, self).__init__()

        fields = [
            QgsField('error', QVariant.String, "string"),  # error type, avoid 'type' which could be keyword
            QgsField('route', QVariant.String, "string"),
            QgsField('measure', QVariant.String, "string"),
        ]

        for field in fields:
            self.append(field)


LRS_ERROR_FIELDS = LrsErrorFields()