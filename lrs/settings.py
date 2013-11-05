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
from qgissettingmanager import *

class LrsSettings(SettingManager):

    def __init__(self):
        SettingManager.__init__(self, PROJECT_PLUGIN_NAME )

        # project settings
        self.addSetting('lineLayerId', 'string', 'project', '')
        self.addSetting('lineRouteField', 'string', 'project', '')
        self.addSetting('pointLayerId', 'string', 'project', '')
        self.addSetting('pointRouteField', 'string', 'project', '')
        self.addSetting('pointMeasureField', 'string', 'project', '')
        self.addSetting('threshold', 'double', 'project', 200.0)
        self.addSetting('mapUnitsPerMeasureUnit', 'double', 'project', 1000.0)
