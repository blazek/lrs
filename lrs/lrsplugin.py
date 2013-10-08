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
from PyQt4.QtGui import *
from qgis.core import *
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from lrsdockwidget import LrsDockWidget
import os.path


class LrsPlugin:

    def __init__(self, iface):
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
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(":/plugins/lrsplugin/icon.png"),
            u"LRS", self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&LRS", self.action)

        # Create the docked panel 
        print "self.iface.mainWindow = %s" % self.iface.mainWindow()
        self.dockWidget = LrsDockWidget(self.iface.mainWindow(), self.iface)
        self.iface.addDockWidget(Qt.RightDockWidgetArea,self.dockWidget)


    def unload(self):
        print "unload"
        self.dockWidget.close()
        self.iface.removeDockWidget(self.dockWidget)
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&LRS", self.action)
        self.iface.removeToolBarIcon(self.action)

    # run method that performs all the real work
    def run(self):
        print "run"

        # show the dialog
        #self.dockWidget.show()

        # Run the dialog event loop
        #result = self.dock.exec_()
        # See if OK was pressed
        #if result == 1:
            # do something useful (delete the line containing pass and
            # substitute with your code)
            #pass
