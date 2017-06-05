from PyQt5.QtCore import QVariant
from qgis._core import QgsFields, QgsField


class LrsQualityFields(QgsFields):
    def __init__(self):
        super(LrsQualityFields, self).__init__()

        fields = [
            QgsField('route', QVariant.String, "string"),
            QgsField('m_from', QVariant.Double, "double"),
            QgsField('m_to', QVariant.Double, "double"),
            QgsField('m_len', QVariant.Double, "double"),
            QgsField('len', QVariant.Double, "double"),
            QgsField('err_abs', QVariant.Double, "double"),
            QgsField('err_rel', QVariant.Double, "double"),
            QgsField('err_perc', QVariant.Double, "double"),  # relative in percents
        ]
        for field in fields:
            self.append(field)


LRS_QUALITY_FIELDS = LrsQualityFields()