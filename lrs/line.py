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
from qgis.PyQt.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *

from .utils import *

class LrsLine(object):

    def __init__(self, fid, routeId, geo ):
        self.fid = fid # line
        self.routeId = routeId
        self.geo = QgsGeometry(geo) # store copy of QgsGeometry, may be None

    def getNumParts(self):
        if not self.geo: return 0

        if self.geo.isMultipart():
            return len( self.geo.asMultiPolyline() )

        return 1
