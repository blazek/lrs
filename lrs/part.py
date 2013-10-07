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
from PyQt4.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *

from utils import *

# Chain of connected geometries

class LrsRoutePart:

    def __init__(self, layer, feature):
        debug ('init line' )
        self.layer = layer
        # store copy of the feature
        # TODO: consider storing fid only
        #self.feature = QgsFeature(feature)
        #self.routeId = routeId
        #self.lines = [] # list of LrsLine

    #def getFeature():
    #    return self.feature
