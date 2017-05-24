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
import os.path

from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from .lrsdockwidget import LrsDockWidget
from .utils import *


class LrsPlugin:
    def __init__(self, iface):
        # debug( "LrsPlugin.__init__" )
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        localePath = os.path.join(self.plugin_dir, 'i18n', 'lrsplugin_{}.qm'.format(locale))

        if os.path.exists(localePath):
            self.translator = QTranslator()
            self.translator.load(localePath)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        # debug( "LrsPlugin.initGui" )
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(":/plugins/lrs/icon.svg"),
            u"LRS", self.iface.mainWindow())
        self.action.setObjectName("lrsAction")
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu(u"&LRS", self.action)

        # Create the docked panel 
        # print "self.iface.mainWindow = %s" % self.iface.mainWindow()
        self.dockWidget = LrsDockWidget(self.iface.mainWindow(), self.iface)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockWidget)

    def unload(self):
        # debug( "LrsPlugin.unload" )
        self.dockWidget.close()
        self.iface.removeDockWidget(self.dockWidget)
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&LRS", self.action)
        self.iface.removeToolBarIcon(self.action)

    # run method that performs all the real work
    def run(self):
        # debug( "LrsPlugin.run" )

        # show the dialog
        self.dockWidget.show()
