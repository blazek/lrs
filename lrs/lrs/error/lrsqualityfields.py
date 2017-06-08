# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsPlugin
                                 A QGIS plugin
 Linear reference system builder and editor
                              -------------------
        begin                : 2017-5-29
        copyright            : (C) 2017 by Radim Blažek
        email                : radim.blazek@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
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