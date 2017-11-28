# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsPlugin
                                 A QGIS plugin
 Linear reference system builder and editor
                              -------------------
        begin                : 2013-10-02
        copyright            : (C) 2013 by Radim Blažek
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
# Import the PyQt and QGIS libraries
from qgis.core import QgsVectorLayer, QgsProviderRegistry


# changes done to vector layer attributes are not stored correctly in project file
# http://hub.qgis.org/issues/8997 -> recreate temporary provider first to construct uri


# To add methods on layers, we must use manager, not extended QgsVectorLayer,
# because layers may be stored in project and created by QGIS.
# Inherited layers are only used to create layer with type and attributes
from .lrserrorfields import LRS_ERROR_FIELDS


class LrsErrorLayer(QgsVectorLayer):
    def __init__(self, uri, baseName):
        provider = QgsProviderRegistry.instance().createProvider('memory', uri)
        provider.addAttributes(LRS_ERROR_FIELDS.toList())
        uri = provider.dataSourceUri()
        # debug ( 'uri = %s' % uri )
        super(LrsErrorLayer, self).__init__(uri, baseName, 'memory')
