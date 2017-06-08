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