# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsDockWidget
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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

from ui_lrsdockwidget import Ui_LrsDockWidget
from utils import *
from error import *
from layer import *
from lrs import *
from combo import *
from widget import *
from selectiondialog import *

try:
    import psycopg2
    import psycopg2.extensions
    # use unicode!
    psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
    psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)
    havePostgis = True
except:
    havePostgis = False

class LrsDockWidget( QDockWidget, Ui_LrsDockWidget ):
    def __init__( self,parent, iface ):
        #debug( "LrsDockWidget.__init__")
        self.iface = iface
        self.lrs = None # Lrs object
        self.genSelectionDialog = None
        self.errorPointLayer = None
        self.errorPointLayerManager = None
        self.errorLineLayer = None
        self.errorLineLayerManager = None
        self.qualityLayer = None
        self.qualityLayerManager = None

        self.pluginDir = QFileInfo(QgsApplication.qgisUserDbFilePath()).path() + "python/plugins/lrs"
        # remember if export schema options has to be reset to avoid asking credential until necessary
        self.resetExportSchemaOptionsOnVisible = False
 
        super(LrsDockWidget, self).__init__(parent )
        
        # Set up the user interface from Designer.
        self.setupUi( self )

        # keep progress frame height
        self.genProgressFrame.setMinimumHeight( self.genProgressFrame.height() )
        self.hideGenProgress()

        self.tabWidget.currentChanged.connect(self.tabChanged)

        ##### genTab 
        # initLayer, initField, fieldType did not work, fixed and created pull request
        # https://github.com/3nids/qgiscombomanager/pull/1

        self.genLineLayerCM = LrsLayerComboManager( self.genLineLayerCombo, geometryType = QGis.Line, settingsName = 'lineLayerId' )
        self.genLineRouteFieldCM = LrsFieldComboManager( self.genLineRouteFieldCombo, self.genLineLayerCM, settingsName = 'lineRouteField' )
        self.genPointLayerCM = LrsLayerComboManager( self.genPointLayerCombo, geometryType = QGis.Point, settingsName = 'pointLayerId' )
        self.genPointRouteFieldCM = LrsFieldComboManager( self.genPointRouteFieldCombo, self.genPointLayerCM, settingsName = 'pointRouteField' )
        self.genPointMeasureFieldCM = LrsFieldComboManager( self.genPointMeasureFieldCombo, self.genPointLayerCM, types = [ QVariant.Int, QVariant.Double ], settingsName = 'pointMeasureField' )

        self.genMeasureUnitCM = LrsUnitComboManager( self.genMeasureUnitCombo, settingsName = 'measureUnit', defaultValue = LrsUnits.KILOMETER )

        self.genSelectionModeCM = LrsComboManager( self.genSelectionModeCombo, options = (('all', 'All routes'),('include', 'Include routes'),('exclude','Exclude routes')), defaultValue = 'all', settingsName = 'selectionMode' )
        self.genSelectionWM = LrsWidgetManager( self.genSelectionLineEdit, settingsName = 'selection' )


        self.genThresholdWM = LrsWidgetManager( self.genThresholdSpin, settingsName = 'threshold', defaultValue = 200.0 )
        self.genSnapWM = LrsWidgetManager( self.genSnapSpin, settingsName = 'snap', defaultValue = 0.0 )
        self.genParallelModeCM = LrsComboManager( self.genParallelModeCombo, options = (('error', 'Mark as errors'), ('span', 'Span by straight line'),('exclude','Exclude')), defaultValue = 'error', settingsName = 'parallelMode' )
        self.genExtrapolateWM = LrsWidgetManager( self.genExtrapolateCheckBox, settingsName = 'extrapolate', defaultValue = False )

        self.genLineLayerCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genLineLayerCombo.currentIndexChanged.connect(self.updateLabelsUnits)
        self.genLineRouteFieldCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genPointLayerCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genPointRouteFieldCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genPointMeasureFieldCombo.currentIndexChanged.connect(self.resetGenerateButtons)

        self.genSelectionModeCombo.currentIndexChanged.connect(self.enableGenerateSelection )
        self.genSelectionButton.clicked.connect(self.openGenerateSelectionDialog)

        self.genButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.generateLrs)
        self.genButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetGenerateOptionsAndWrite)
        self.genButtonBox.button(QDialogButtonBox.Help).clicked.connect(self.showHelp)

        self.enableGenerateSelection()

        ##### errorTab
        self.errorVisualizer = LrsErrorVisualizer ( self.iface.mapCanvas() )
        self.errorModel = None
        self.errorView.horizontalHeader().setStretchLastSection ( True )
        self.errorZoomButton.setEnabled( False) 
        self.errorZoomButton.setIcon( QgsApplication.getThemeIcon( '/mActionZoomIn.svg' ) )
        self.errorZoomButton.setText('Zoom')
        self.errorZoomButton.clicked.connect( self.errorZoom )
        self.errorFilterLineEdit.textChanged.connect( self.errorFilterChanged )

        self.addErrorLayersButton.clicked.connect( self.addErrorLayers )
        self.addQualityLayerButton.clicked.connect( self.addQualityLayer )
        self.errorButtonBox.button(QDialogButtonBox.Help).clicked.connect(self.showHelp)

        #### eventsTab
        self.eventsLayerCM = LrsLayerComboManager( self.eventsLayerCombo, settingsName = 'eventsLayerId' )
        self.eventsRouteFieldCM = LrsFieldComboManager( self.eventsRouteFieldCombo, self.eventsLayerCM, settingsName = 'eventsRouteField' )
        self.eventsMeasureStartFieldCM = LrsFieldComboManager( self.eventsMeasureStartFieldCombo, self.eventsLayerCM, types = [ QVariant.Int, QVariant.Double ], settingsName = 'eventsMeasureStartField' )
        self.eventsMeasureEndFieldCM = LrsFieldComboManager( self.eventsMeasureEndFieldCombo, self.eventsLayerCM, types = [ QVariant.Int, QVariant.Double ], allowNone = True, settingsName = 'eventsMeasureEndField' )

        self.eventsOutputNameWM = LrsWidgetManager( self.eventsOutputNameLineEdit, settingsName = 'eventsOutputName', defaultValue = 'LRS events' )
        self.eventsErrorFieldWM = LrsWidgetManager( self.eventsErrorFieldLineEdit, settingsName = 'eventsErrorField', defaultValue = 'lrs_err' )
        validator = QRegExpValidator( QRegExp( '[A-Za-z_][A-Za-z0-9_]+' ), None )
        self.eventsErrorFieldLineEdit.setValidator( validator )

        self.eventsButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.createEvents)
        self.eventsButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetEventsOptionsAndWrite)
        self.eventsButtonBox.button(QDialogButtonBox.Help).clicked.connect(self.showHelp)
        self.eventsLayerCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsRouteFieldCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsMeasureStartFieldCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsMeasureEndFieldCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsOutputNameLineEdit.textEdited.connect(self.resetEventsButtons)
        self.resetEventsOptions()
        self.resetEventsButtons()
        self.eventsProgressBar.hide()

        #### measureTab
        self.measureLayerCM = LrsLayerComboManager( self.measureLayerCombo, geometryType = QGis.Point, settingsName = 'measureLayerId' )
        self.measureThresholdWM = LrsWidgetManager( self.measureThresholdSpin, settingsName = 'measureThreshold', defaultValue = 200.0 )
        self.measureOutputNameWM = LrsWidgetManager( self.measureOutputNameLineEdit, settingsName = 'measureOutputName', defaultValue = 'LRS measure' )

        self.measureRouteFieldWM = LrsWidgetManager( self.measureRouteFieldLineEdit, settingsName = 'measureRouteField', defaultValue = 'route' )
        validator = QRegExpValidator( QRegExp( '[A-Za-z_][A-Za-z0-9_]+' ), None )
        self.measureRouteFieldLineEdit.setValidator( validator )

        self.measureMeasureFieldWM = LrsWidgetManager( self.measureMeasureFieldLineEdit, settingsName = 'measureMeasureField', defaultValue = 'measure' )
        self.measureMeasureFieldLineEdit.setValidator( validator )


        self.measureButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.calculateMeasures)
        self.measureButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetMeasureOptionsAndWrite)
        self.measureButtonBox.button(QDialogButtonBox.Help).clicked.connect(self.showHelp)
        self.measureLayerCombo.currentIndexChanged.connect(self.resetMeasureButtons)
        self.measureOutputNameLineEdit.textEdited.connect(self.resetMeasureButtons)
        self.measureRouteFieldLineEdit.textEdited.connect(self.resetMeasureButtons)
        self.measureMeasureFieldLineEdit.textEdited.connect(self.resetMeasureButtons)
        self.resetMeasureOptions()
        self.resetMeasureButtons()
        self.measureProgressBar.hide()

        #### export tab
        self.exportPostgisConnectionCM = LrsComboManager( self.exportPostgisConnectionCombo, settingsName = 'exportPostgisConnection' )
        self.exportPostgisSchemaCM = LrsComboManager( self.exportPostgisSchemaCombo, settingsName = 'exportPostgisSchema' )
        self.exportPostgisTableWM = LrsWidgetManager( self.exportPostgisTableLineEdit, settingsName = 'exportPostgisTable', defaultValue = 'lrs' )
        validator = QRegExpValidator( QRegExp( '[A-Za-z_][A-Za-z0-9_]+' ), None )
        self.exportPostgisTableLineEdit.setValidator( validator )

        
        self.exportPostgisConnectionCombo.currentIndexChanged.connect(self.resetExportSchemaOptions)
        self.exportPostgisConnectionCombo.currentIndexChanged.connect(self.resetExportButtons)
        self.exportPostgisSchemaCombo.currentIndexChanged.connect(self.resetExportButtons)
        self.exportPostgisTableLineEdit.textEdited.connect(self.resetExportButtons)
        self.exportButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.export)
        self.exportButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetExportOptionsAndWrite)
        self.exportButtonBox.button(QDialogButtonBox.Help).clicked.connect(self.showHelp)

        self.resetExportOptions()
        self.resetExportButtons()

        #### statistics tab
        # currently not used (did not correspond well to errors)
        self.tabWidget.removeTab( self.tabWidget.indexOf(self.statsTab) )

        #####
        self.enableTabs()

        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.layersWillBeRemoved)
        
        QgsProject.instance().readProject.connect( self.projectRead )

        self.iface.mapCanvas().mapRenderer().hasCrsTransformEnabled.connect(self.mapRendererCrsChanged)
        self.iface.mapCanvas().mapRenderer().destinationSrsChanged.connect(self.mapRendererCrsChanged)
        self.updateLabelsUnits()


        # newProject is currently missing in sip
        #QgsProject.instance().newProject.connect( self.projectNew )

        # read project if plugin was reloaded
        self.projectRead()

    def errorFilterChanged(self, text):
        if not self.sortErrorModel: return
        self.sortErrorModel.setFilterWildcard( text )

    def projectRead(self):
        #debug("projectRead")
        if not QgsProject: return

        project = QgsProject.instance()
        if not project: return

        self.readGenerateOptions()
        self.readEventsOptions()
        self.readMeasureOptions()
        self.readExportOptions()

        registry = QgsMapLayerRegistry.instance()

        ##### set error layers if stored in project
        errorLineLayerId = project.readEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId" )[0]
        self.errorLineLayer = registry.mapLayer( errorLineLayerId )
        if self.errorLineLayer:
            self.errorLineLayerManager = LrsErrorLayerManager(self.errorLineLayer)

        errorPointLayerId = project.readEntry( PROJECT_PLUGIN_NAME, "errorPointLayerId" )[0]
        self.errorPointLayer = registry.mapLayer( errorPointLayerId )
        if self.errorPointLayer:
            self.errorPointLayerManager = LrsErrorLayerManager(self.errorPointLayer)

        qualityLayerId = project.readEntry( PROJECT_PLUGIN_NAME, "qualityLayerId" )[0]
        self.qualityLayer = registry.mapLayer( qualityLayerId )
        if self.qualityLayer:
            self.qualityLayerManager = LrsQualityLayerManager ( self.qualityLayer )

        self.resetGenerateButtons()

        # debug
        #if self.genLineLayerCM.getLayer():
        #    self.generateLrs() # only when reloading!

    def projectNew(self):
        self.deleteLrs()
        self.resetGenerateOptions()
        self.resetEventsOptions()
        self.resetMeasureOptions()
        self.resetExportOptions()
        self.enableTabs()

    def deleteLrs(self):
        if self.lrs: del self.lrs
        self.lrs = None

    def close(self):
        #debug( "LrsDockWidget.close")
        self.deleteLrs()
        QgsMapLayerRegistry.instance().layersWillBeRemoved.disconnect(self.layersWillBeRemoved)
        QgsProject.instance().readProject.disconnect( self.projectRead )
        self.iface.mapCanvas().mapRenderer().hasCrsTransformEnabled.disconnect(self.mapRendererCrsChanged)
        self.iface.mapCanvas().mapRenderer().destinationSrsChanged.disconnect(self.mapRendererCrsChanged)

        # Must delete combo managers to disconnect!
        del self.genLineLayerCM
        del self.genLineRouteFieldCM
        del self.genPointLayerCM
        del self.genPointRouteFieldCM
        del self.genPointMeasureFieldCM
        del self.errorVisualizer

        del self.eventsLayerCM
        del self.eventsRouteFieldCM
        del self.eventsMeasureStartFieldCM
        del self.eventsMeasureEndFieldCM

        super(LrsDockWidget, self).close()
            
    def layersWillBeRemoved(self, layerIdList ):
        project = QgsProject.instance()
        for id in layerIdList:
            if self.errorPointLayer and self.errorPointLayer.id() == id:
                self.errorPointLayerManager = None
                self.errorPointLayer = None
                project.removeEntry( PROJECT_PLUGIN_NAME, "errorPointLayerId" )
            if self.errorLineLayer and self.errorLineLayer.id() == id:
                self.errorLineLayerManager = None
                self.errorLineLayer = None
                project.removeEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId" )
            if self.qualityLayer and self.qualityLayer.id() == id:
                self.qualityLayerManager = None
                self.qualityLayer = None
                project.removeEntry( PROJECT_PLUGIN_NAME, "qualityLayerId" )

    def enableTabs(self):
        enable = bool(self.lrs)
        self.statsTab.setEnabled( enable )
        self.errorTab.setEnabled( enable )
        self.eventsTab.setEnabled( enable )
        self.measureTab.setEnabled( enable )
        self.exportTab.setEnabled( enable )

    def tabChanged(self, index):
        #debug("tabChanged index = %s" % index )
        if self.tabWidget.widget(index) == self.exportTab:
           self.exportTabBecameVisible() 

    def mapRendererCrsChanged(self):
        self.updateLabelsUnits()

    def getUnitsLabel(self, crs):
        label = ""
        units = { QGis.Meters: 'meters', QGis.Feet: 'feets', QGis.Degrees: 'degrees' }
        if crs and units.has_key( crs.mapUnits() ):
            label = " (%s)" % units[crs.mapUnits()]
        return label

    def getThresholdLabel(self, crs):
        label = "Max point distance" + self.getUnitsLabel(crs)
        #debug ( 'label = %s' % label )
        return label

    def showHelp(self,anchor=None):
        helpFile = "file:///"+ self.pluginDir + "/help/build/html/index.html"
        #debug ( helpFile )
        QDesktopServices.openUrl(QUrl(helpFile))
        

############################ GENERATE (CALIBRATE) ###############################

    def resetGenerateButtons(self):
        enabled = self.genLineLayerCombo.currentIndex() != -1 and self.genLineRouteFieldCombo.currentIndex() != -1 and self.genPointLayerCombo.currentIndex() != -1 and self.genPointRouteFieldCombo.currentIndex() != -1 and self.genPointMeasureFieldCombo.currentIndex() != -1

        self.genButtonBox.button(QDialogButtonBox.Ok).setEnabled(enabled)

    def resetGenerateOptions(self):
        self.genLineLayerCM.reset() 
        self.genLineRouteFieldCM.reset() 
        self.genPointLayerCM.reset() 
        self.genPointRouteFieldCM.reset() 
        self.genPointMeasureFieldCM.reset() 
        self.genMeasureUnitCM.reset()
        self.genSelectionModeCM.reset()
        self.genSelectionWM.reset()
        self.genThresholdWM.reset()
        self.genSnapWM.reset()
        self.genParallelModeCM.reset()
        self.genExtrapolateWM.reset()

        self.resetGenerateButtons()
        
    def resetGenerateOptionsAndWrite(self):
        self.resetGenerateOptions()
        self.writeGenerateOptions()

    def enableGenerateSelection(self):
        enable = self.genSelectionModeCM.value() != 'all'
        self.genSelectionLineEdit.setEnabled(enable)
        self.genSelectionButton.setEnabled(enable)

    # save settings in project
    def writeGenerateOptions(self):
        self.genLineLayerCM.writeToProject()
        self.genLineRouteFieldCM.writeToProject()
        self.genPointLayerCM.writeToProject()
        self.genPointRouteFieldCM.writeToProject()
        self.genPointMeasureFieldCM.writeToProject()
        self.genMeasureUnitCM.writeToProject()
        self.genSelectionModeCM.writeToProject()
        self.genSelectionWM.writeToProject()
        self.genThresholdWM.writeToProject() 
        self.genSnapWM.writeToProject() 
        self.genParallelModeCM.writeToProject()
        self.genExtrapolateWM.writeToProject()

    def readGenerateOptions(self):
        self.genLineLayerCM.readFromProject()
        self.genLineRouteFieldCM.readFromProject()
        self.genPointLayerCM.readFromProject()
        self.genPointRouteFieldCM.readFromProject()
        self.genPointMeasureFieldCM.readFromProject()
        self.genMeasureUnitCM.readFromProject()
        self.genSelectionModeCM.readFromProject()
        self.genSelectionWM.readFromProject()
        self.genThresholdWM.readFromProject()
        self.genSnapWM.readFromProject()
        self.genParallelModeCM.readFromProject()
        self.genExtrapolateWM.readFromProject()

    def getGenerateSelection(self):
        return map( unicode.strip, self.genSelectionLineEdit.text().split(',') )

    def openGenerateSelectionDialog(self):
        if not self.genSelectionDialog:
            self.genSelectionDialog = LrsSelectionDialog()
            self.genSelectionDialog.accepted.connect( self.generateSelectionDialogAccepted )

        layer = self.genLineLayerCM.getLayer()
        fieldName = self.genLineRouteFieldCM.getFieldName()
        select = self.getGenerateSelection()
        self.genSelectionDialog.load( layer, fieldName, select )

        self.genSelectionDialog.show()

    def generateSelectionDialogAccepted(self):
        selection = self.genSelectionDialog.selected()
        selection = ",".join( map(str,selection) )
        self.genSelectionLineEdit.setText( selection )

    def getGenerateCrs(self):
        crs = None
        #debug ( "genLineLayerCM = %s" % self.genLineLayerCM )
        lineLayer = self.genLineLayerCM.getLayer()
        if lineLayer:
            crs = lineLayer.crs()

        #debug ('line layer  crs = %s' % self.genLineLayerCM.getLayer().crs().authid() )
        if self.iface.mapCanvas().mapRenderer().hasCrsTransformEnabled():
            #debug ('enabled mapCanvas crs = %s' % self.iface.mapCanvas().mapRenderer().destinationCrs().authid() )
            crs = self.iface.mapCanvas().mapRenderer().destinationCrs()
        return crs

    # set threshold units according to current crs
    def updateLabelsUnits(self):
        crs = self.getGenerateCrs()
        label = self.getThresholdLabel(crs)
        self.genThresholdLabel.setText(label)
        label = "Max lines snap" + self.getUnitsLabel(crs)
        self.genSnapLabel.setText(label)

    def generateLrs(self):
        #debug ( 'generateLrs')
        self.errorVisualizer.clearHighlight()
        
        self.writeGenerateOptions()

        crs = self.getGenerateCrs()

        selection = self.getGenerateSelection()
        snap = self.genSnapSpin.value()
        threshold = self.genThresholdSpin.value()
        parallelMode = self.genParallelModeCM.value()
        extrapolate = self.genExtrapolateCheckBox.isChecked()

        #self.mapUnitsPerMeasureUnit = self.genMapUnitsPerMeasureUnitSpin.value()
        measureUnit = self.genMeasureUnitCM.unit()

        self.lrs = Lrs ( self.genLineLayerCM.getLayer(), self.genLineRouteFieldCM.getFieldName(), self.genPointLayerCM.getLayer(), self.genPointRouteFieldCM.getFieldName(), self.genPointMeasureFieldCM.getFieldName(), selectionMode = self.genSelectionModeCM.value(), selection = selection, crs = crs, snap = snap, threshold = threshold, parallelMode = parallelMode, extrapolate = extrapolate, measureUnit = measureUnit )

        self.lrs.progressChanged.connect(self.showGenProgress)
        self.lrs.calibrate()
        self.hideGenProgress()

        #self.resetStats()   

        #### errors ##### 
        self.errorZoomButton.setEnabled( False)
        self.errorModel = LrsErrorModel()
        self.errorModel.addErrors( self.lrs.getErrors() )

        self.sortErrorModel = QSortFilterProxyModel()
        self.sortErrorModel.setFilterKeyColumn(-1) # all columns
        self.sortErrorModel.setFilterCaseSensitivity( Qt.CaseInsensitive )
        self.sortErrorModel.setDynamicSortFilter(True)
        self.sortErrorModel.setSourceModel( self.errorModel )
         
        self.errorView.setModel( self.sortErrorModel )
        self.sortErrorModel.sort(0)
        self.errorView.resizeColumnsToContents ()
        self.errorView.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Attention, if selectionMode is QTableView.SingleSelection, selection is not
        # cleared if deleted row was selected (at least one row is always selected)
        self.errorView.setSelectionMode(QTableView.SingleSelection)
        self.errorView.selectionModel().selectionChanged.connect(self.errorSelectionChanged)
        
        self.lrs.updateErrors.connect ( self.updateErrors )
        
        self.resetErrorLayers()
        self.resetQualityLayer()

        if self.errorPointLayer or self.errorLineLayer or self.qualityLayer:
            self.iface.mapCanvas().refresh()

        self.resetEventsButtons()
        self.resetMeasureButtons()
        self.resetExportButtons()
        self.updateMeasureUnits()
        self.enableTabs()

    def showGenProgress(self, label, percent):
        self.genProgressLabel.show()
        self.genProgressBar.show()
        self.genProgressLabel.setText( label )
        self.genProgressBar.setValue( percent)

    def hideGenProgress(self):
        self.genProgressLabel.hide()
        self.genProgressBar.hide()

############################### ERRORS ##########################################

    def updateErrors( self, errorUpdates):
        #debug ( "updateErrors" )
        # because SingleSelection does not allow to deselect row, we have to clear selection manually
        index = self.getSelectedErrorIndex()
        if index:
            rows = self.errorModel.rowsToBeRemoved( errorUpdates )
            selected = index.row()
            if selected in rows:
                self.errorView.selectionModel().clear()
        self.errorModel.updateErrors( errorUpdates )
        self.errorSelectionChanged()
        self.updateErrorLayers( errorUpdates )
        self.updateQualityLayer( errorUpdates )

    #def errorSelectionChanged(self, selected, deselected ):
    def errorSelectionChanged(self):
        error = self.getSelectedError()
        self.errorVisualizer.highlight( error, self.lrs.crs )
        self.errorZoomButton.setEnabled( error is not None ) 

    def getSelectedErrorIndex(self):
        sm = self.errorView.selectionModel()
        if not sm.hasSelection(): return None
        index = sm.selection().indexes()[0]
        index = self.sortErrorModel.mapToSource(index)
        return index

    def getSelectedError(self):
        index = self.getSelectedErrorIndex()
        if not index: return None
        return self.errorModel.getError(index)

    def errorZoom(self):
        error = self.getSelectedError()
        if not error: return
        self.errorVisualizer.zoom( error, self.lrs.crs )       

    # add new error layers to map
    def addErrorLayers(self):
        project = QgsProject.instance()

        if not self.errorLineLayer:
            self.errorLineLayer = LrsErrorLineLayer( self.lrs.crs )
            self.errorLineLayerManager = LrsErrorLayerManager(self.errorLineLayer)
            self.errorLineLayer.rendererV2().symbol().setColor( QColor(Qt.red) )
            self.resetErrorLineLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorLineLayer,] )
            project.writeEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId", self.errorLineLayer.id() )

        if not self.errorPointLayer:
            self.errorPointLayer = LrsErrorPointLayer( self.lrs.crs )
            self.errorPointLayerManager = LrsErrorLayerManager(self.errorPointLayer)
            self.errorPointLayer.rendererV2().symbol().setColor( QColor(Qt.red) )
            self.resetErrorPointLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorPointLayer,] )
            project.writeEntry( PROJECT_PLUGIN_NAME, "errorPointLayerId", self.errorPointLayer.id() )
   
    # reset error layers content (features)
    def resetErrorLayers(self):
        #debug ( "resetErrorLayers" )
        self.resetErrorPointLayer()
        self.resetErrorLineLayer()

    def updateErrorLayers(self, errorUpdates):
        if self.errorPointLayerManager:
            self.errorPointLayerManager.updateErrors( errorUpdates )
        if self.errorLineLayerManager:
            self.errorLineLayerManager.updateErrors( errorUpdates )

    def updateQualityLayer(self, errorUpdates):
        if self.qualityLayerManager:
            self.qualityLayerManager.update( errorUpdates )

    def resetErrorPointLayer(self):
        #debug ( "resetErrorPointLayer %s" % self.errorPointLayer )
        if not self.errorPointLayerManager: return
        self.errorPointLayerManager.clear()
        errors = self.lrs.getErrors()
        self.errorPointLayerManager.addErrors( errors, self.lrs.crs )

    def resetErrorLineLayer(self):
        if not self.errorLineLayerManager: return
        self.errorLineLayerManager.clear()
        errors = self.lrs.getErrors()
        self.errorLineLayerManager.addErrors( errors, self.lrs.crs )

    def addQualityLayer(self):
        if not self.qualityLayer:
            self.qualityLayer = LrsQualityLayer( self.lrs.crs )
            self.qualityLayerManager = LrsQualityLayerManager ( self.qualityLayer )

            self.resetQualityLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.qualityLayer,] )
            project = QgsProject.instance()
            project.writeEntry( PROJECT_PLUGIN_NAME, "qualityLayerId", self.qualityLayer.id() )

    def resetQualityLayer(self):
        #debug ( "resetQualityLayer %s" % self.qualityLayer )
        if not self.qualityLayerManager: return
        self.qualityLayerManager.clear()
        features = self.lrs.getQualityFeatures()
        self.qualityLayerManager.addFeatures( features, self.lrs.crs )
            
############################# EVENTS ###############################################

    def resetEventsOptions(self):
        self.eventsLayerCM.reset() 
        self.eventsRouteFieldCM.reset() 
        self.eventsMeasureStartFieldCM.reset() 
        self.eventsMeasureEndFieldCM.reset() 
        self.eventsOutputNameWM.reset()
        self.eventsErrorFieldWM.reset()

        self.resetEventsButtons()

    def resetEventsOptionsAndWrite(self):
        self.resetEventsOptions()
        self.writeEventsOptions()

    def resetEventsButtons(self):
        enabled = bool(self.lrs) and self.eventsLayerCombo.currentIndex() != -1 and self.eventsRouteFieldCombo.currentIndex() != -1 and self.eventsMeasureStartFieldCombo.currentIndex() != -1 and bool(self.eventsOutputNameLineEdit.text())

        self.eventsButtonBox.button(QDialogButtonBox.Ok).setEnabled(enabled)

    # save settings in project
    def writeEventsOptions(self):
        self.eventsLayerCM.writeToProject()
        self.eventsRouteFieldCM.writeToProject()
        self.eventsMeasureStartFieldCM.writeToProject()
        self.eventsMeasureEndFieldCM.writeToProject()
        self.eventsOutputNameWM.writeToProject()
        self.eventsErrorFieldWM.writeToProject()

    def readEventsOptions(self):
        self.eventsLayerCM.readFromProject()
        self.eventsRouteFieldCM.readFromProject()
        self.eventsMeasureStartFieldCM.readFromProject()
        self.eventsMeasureEndFieldCM.readFromProject()
        self.eventsOutputNameWM.readFromProject()
        self.eventsErrorFieldWM.readFromProject()

    def createEvents(self):
        self.writeEventsOptions()
        self.eventsProgressBar.show()

        layer = self.eventsLayerCM.getLayer()
        routeFieldName = self.eventsRouteFieldCM.getFieldName()
        startFieldName = self.eventsMeasureStartFieldCM.getFieldName()
        endFieldName = self.eventsMeasureEndFieldCM.getFieldName()
        outputName = self.eventsOutputNameLineEdit.text()
        if not outputName: outputName = self.eventsOutputNameWM.defaultValue()
        errorFieldName = self.eventsErrorFieldLineEdit.text()
 
        # create new layer
        geometryType = "MultiLineString" if endFieldName else "Point"
        uri = geometryType
        uri += "?crs=%s" %  crsString( self.iface.mapCanvas().mapRenderer().destinationCrs() )
        provider = QgsProviderRegistry.instance().provider( 'memory', uri )
        provider.addAttributes( layer.pendingFields().toList() )
        if errorFieldName:
            provider.addAttributes( [ QgsField( errorFieldName, QVariant.String, "string"), ]) 
        uri = provider.dataSourceUri()
        outputLayer = QgsVectorLayer ( uri, outputName, 'memory')

        outputFeatures = []
        fields = outputLayer.pendingFields()
        total = layer.featureCount()
        count = 0
        for feature in layer.getFeatures():
            routeId = feature[routeFieldName]
            start = feature[startFieldName]
            end = feature[endFieldName] if endFieldName else None
            #debug ( "event routeId = %s start = %s end = %s" % ( routeId, start, end ) )

            outputFeature = QgsFeature( fields ) # fields must exist during feature life!
            for field in layer.pendingFields():
                outputFeature[field.name()] = feature[field.name()]
            
            geo = None
            if endFieldName:
                line, error = self.lrs.eventMultiPolyLine ( routeId, start, end )
                if line:
                    geo = QgsGeometry.fromMultiPolyline( line )
            else:
                point, error = self.lrs.eventPoint ( routeId, start )
                if point:
                    geo = QgsGeometry.fromPoint( point )
            
            # Because of bug #9309 in memory provider in 2.0 it was crashing if geometry
            # was not set on feature. OTOH, if empty geometry (created by QgsGeometry()
            # which does not construct correct WKBNoGeometry) was set on a feature, 
            # QgsVectorFileWriter was giving errors when saving memory layer.
            if QGis.QGIS_VERSION_INT < 20100:
                if not geo: 
                    # QgsGeometry() does not construct correct WKBNoGeometry
                    # QgsGeometry.fromWkt('MULTILINESTRING/POINT EMPTY') is cousing later crash
                    geo = QgsGeometry()
                
            if geo:
                outputFeature.setGeometry( geo )

            if errorFieldName and error:
                outputFeature[errorFieldName] = error

            outputFeatures.append( outputFeature )

            count += 1
            percent = 100 * count / total;
            self.eventsProgressBar.setValue( percent)

        outputLayer.dataProvider().addFeatures( outputFeatures )

        QgsMapLayerRegistry.instance().addMapLayers( [outputLayer,] )
            
        self.eventsProgressBar.hide()

############################# MEASURE ####################################

    def resetMeasureOptions(self):
        #debug('resetMeasureOptions')
        self.measureLayerCM.reset() 
        self.measureThresholdWM.reset()
        self.measureOutputNameWM.reset()
        self.measureRouteFieldWM.reset()
        self.measureMeasureFieldWM.reset()

        self.resetMeasureButtons()

    def resetMeasureOptionsAndWrite(self):
        self.resetMeasureOptions()
        self.writeMeasureOptions()

    def resetMeasureButtons(self):
        #debug('resetMeasureButtons')
        enabled = bool(self.lrs) and self.measureLayerCombo.currentIndex() != -1 and bool(self.measureOutputNameLineEdit.text()) and bool(self.measureRouteFieldLineEdit.text()) and bool(self.measureMeasureFieldLineEdit.text())

        self.measureButtonBox.button(QDialogButtonBox.Ok).setEnabled(enabled)

    # save settings in project
    def writeMeasureOptions(self):
        self.measureLayerCM.writeToProject()
        self.measureThresholdWM.writeToProject()
        self.measureOutputNameWM.writeToProject()
        self.measureRouteFieldWM.writeToProject()
        self.measureMeasureFieldWM.writeToProject()

    def readMeasureOptions(self):
        self.measureLayerCM.readFromProject()
        self.measureThresholdWM.readFromProject()
        self.measureOutputNameWM.readFromProject()
        self.measureRouteFieldWM.readFromProject()
        self.measureMeasureFieldWM.readFromProject()

    # set threshold units according to current crs
    def updateMeasureUnits(self):
        crs = self.lrs.crs if self.lrs.crs else None
        label = self.getThresholdLabel(crs)
        self.measureThresholdLabel.setText(label)

    def calculateMeasures(self):
        #debug('calculateMeasures')
        self.writeMeasureOptions()

        self.measureProgressBar.show()

        layer = self.measureLayerCM.getLayer()
        threshold = self.measureThresholdSpin.value()
        outputName = self.measureOutputNameLineEdit.text()
        if not outputName: outputName = self.measureOutputNameWM.defaultValue()
        routeFieldName = self.measureRouteFieldLineEdit.text()
        measureFieldName = self.measureMeasureFieldLineEdit.text()
 
        # create new layer
        #uri = "Point?crs=%s" %  crsString ( self.iface.mapCanvas().mapRenderer().destinationCrs() )
        uri = "Point?crs=%s" %  crsString ( layer.crs() )
        provider = QgsProviderRegistry.instance().provider( 'memory', uri )
        provider.addAttributes( layer.pendingFields().toList() )
        provider.addAttributes( [ 
            QgsField( routeFieldName, QVariant.String, "string"), 
            QgsField( measureFieldName, QVariant.Double, "double"), 
        ]) 

        uri = provider.dataSourceUri()
        outputLayer = QgsVectorLayer ( uri, outputName, 'memory')

        outputFeatures = []
        fields = outputLayer.pendingFields()
        total = layer.featureCount()
        count = 0
        transform = None
        if layer.crs() != self.lrs.crs:
            transform = QgsCoordinateTransform( layer.crs(), self.lrs.crs)
        for feature in layer.getFeatures():
            points = []
            
            geo = feature.geometry()
            if geo:
                if geo.wkbType() in [ QGis.WKBPoint, QGis.WKBPoint25D]:
                    points = [ geo.asPoint() ]
                elif geo.wkbType() in [ QGis.WKBMultiPoint, QGis.WKBMultiPoint25D]:
                    points = geo.asMultiPoint()

            for point in points:
                outputFeature = QgsFeature( fields ) # fields must exist during feature life!
                outputFeature.setGeometry( QgsGeometry.fromPoint( point ) )
                
                for field in layer.pendingFields():
                    outputFeature[field.name()] = feature[field.name()]
                
                if transform:
                    point = transform.transform( point )
                routeId, measure = self.lrs.pointMeasure ( point, threshold )
                #debug ( "routeId = %s merasure = %s" % (routeId, measure) )

                if routeId is not None:
                    outputFeature[routeFieldName] = '%s' % routeId
                outputFeature[measureFieldName] = measure

                outputFeatures.append( outputFeature )

            count += 1
            percent = 100 * count / total;
            self.measureProgressBar.setValue( percent)

        outputLayer.dataProvider().addFeatures( outputFeatures )

        QgsMapLayerRegistry.instance().addMapLayers( [outputLayer,] )

        self.measureProgressBar.hide()

############################ EXPORT ##################################

    def getPostgisConnection(self, connectionName):
        settings = QSettings()
        key = '/PostgreSQL/connections'

        settings.beginGroup( u'/%s/%s' % (key, connectionName) )

        if not settings.contains( 'database' ): return None

        connection = { 'name': connectionName }
        
        settingsList = ['service', 'host', 'port', 'database', 'username', 'password']
        service, host, port, database, username, password = map(lambda x: settings.value(x, '', type=str), settingsList)
        
        sslmode = settings.value("sslmode", QgsDataSourceURI.SSLprefer, type=int)

        uri = QgsDataSourceURI()
        if service:
            uri.setConnection(service, database, username, password, sslmode)
        else:
            uri.setConnection(host, port, database, username, password, sslmode)

        connection['uri'] = uri

        return connection

    def getPostgisConnections(self):
        settings = QSettings()
        connections = []
        key = '/PostgreSQL/connections'
        settings.beginGroup( key );
        for connectionName in settings.childGroups():
            connection = self.getPostgisConnection( connectionName )
            if connection:
                connections.append( connection )
        return connections

    def resetExportOptions(self):
        options = []
        for connection in self.getPostgisConnections():
            options.append( [ connection['name'], connection['name']  ] )
        self.exportPostgisConnectionCM.setOptions ( options )
        self.exportPostgisConnectionCM.reset()
        self.exportPostgisSchemaCM.reset()
        self.exportPostgisTableWM.reset()

        self.resetExportButtons()

    def exportTabVisible(self):
        return self.tabWidget.currentWidget() == self.exportTab

    def exportTabBecameVisible(self):
        #debug("exportTabBecameVisible" )
        if self.resetExportSchemaOptionsOnVisible:
            self.resetExportSchemaOptions()

    def resetExportSchemaOptions(self):
        if self.exportPostgisConnectionCombo.currentIndex() == -1: 
            self.exportPostgisSchemaCM.clear()
            return

        # do not reset options until the tab is visible to avoid asking credentials
        # this will only happen if project is loaded when export tab is not active
        if not self.exportTabVisible():
            self.exportPostgisSchemaCM.clear()
            self.resetExportSchemaOptionsOnVisible = True
            return

        conn = self.openPostgisConnection()
        if not conn: 
            self.exportPostgisSchemaCM.clear()
            return

        try:
            # set current schema as default
            schema = self.postgisSelect ( conn, "select current_schema()")[0][0]
            self.exportPostgisSchemaCM.defaultValue = schema

            options = [ (r[0], r[0]) for r in self.postgisSelect ( conn, "select nspname from pg_catalog.pg_namespace where nspname <> 'information_schema' and nspname !~ '^pg_'") ]
            #debug('options: %s' % options)


            self.exportPostgisSchemaCM.setOptions ( options )
                        
            if self.resetExportSchemaOptionsOnVisible: 
                self.exportPostgisSchemaCM.readFromProject()
            
            self.resetExportSchemaOptionsOnVisible = False

            conn.close()
            
        except Exception, e:
            conn.close()
            QMessageBox.critical( self, 'Error', '%s' % e )
            return

    def resetExportOptionsAndWrite(self):
        self.resetExportOptions()
        self.writeExportOptions()

    def resetExportButtons(self):
        enabled = bool(self.lrs) and self.exportPostgisConnectionCombo.currentIndex() != -1 and self.exportPostgisSchemaCombo.currentIndex() != -1 and bool(self.exportPostgisTableLineEdit.text())
        self.exportButtonBox.button(QDialogButtonBox.Ok).setEnabled(enabled)

    def writeExportOptions(self):
        self.exportPostgisConnectionCM.writeToProject()
        self.exportPostgisSchemaCM.writeToProject()
        self.exportPostgisTableWM.writeToProject()

    def readExportOptions(self):
        self.exportPostgisConnectionCM.readFromProject()
        self.exportPostgisSchemaCM.readFromProject()
        self.exportPostgisTableWM.readFromProject()

    # open connection asking credentials in cycle
    def openPostgisConnection(self):
        connectionName = self.exportPostgisConnectionCM.value()
        connection = self.getPostgisConnection( connectionName )
        if not connection: # should not happen
            QMessageBox.critical( self, 'Error', 'Connection not defined')
            return

        uri = connection['uri']

        username = uri.username()
        password = uri.password()
        while True:
            uri.setUsername( username )
            uri.setPassword( password )
            
            #debug('connection: %s' % uri.connectionInfo() ) 
            try:
                conn = psycopg2.connect( uri.connectionInfo().encode('utf-8') )
                #debug('connected ok' ) 
                return conn
            except Exception,e:
                #QMessageBox.critical( self, 'Error', 'Cannot connect: %s' % e )
                err = '%s' % e
                (ok, username, password) = QgsCredentials.instance().get(uri.connectionInfo(), username, password, err)
                # Put the credentials back (for yourself and the provider), as QGIS removes it when you "get" it
                if ok: 
                    QgsCredentials.instance().put( uri.connectionInfo(), username, password )
                else:
                    return None

    def postgisExecute(self, conn, sql):
        #debug('sql: %s' % sql )
        cur = conn.cursor() 
        cur.execute( sql )  

    def postgisSelect(self, conn, sql):
        #debug('sql: %s' % sql )
        cur = conn.cursor() 
        cur.execute( sql )  
        return cur.fetchall()

    def export(self):
        #debug('export')
        self.writeExportOptions()

        # TODO: disable tab instead
        if not havePostgis:
            QMessageBox.critical( self, 'Error', 'psycopg2 not installed')
            return

        conn = self.openPostgisConnection()
        #debug('conn: %s' % conn ) 
        if not conn: return

        try:
            outputSchema = self.exportPostgisSchemaCM.value()
            tables = [ r[0] for r in self.postgisSelect ( conn, "SELECT table_name FROM information_schema.tables where table_schema = '%s'" % outputSchema ) ]
            #debug('tables: %s' % tables)        

            outputTable = self.exportPostgisTableLineEdit.text()
            if outputTable in tables:
                answer = QMessageBox.question( self, 'Table exists', "Table '%s' already exists in schema '%s'. Overwrite?" % (outputTable, outputSchema), QMessageBox.Yes | QMessageBox.Abort )
                if answer == QMessageBox.Abort:
                    return 
                else:
                    sql = "drop table %s.%s" % (outputSchema, outputTable)
                    self.postgisExecute ( conn, sql )
            
            routeField = self.lrs.routeField
            routeFieldName = routeField.name().replace( " ", "_" )
            routeFieldStr = "%s " % routeFieldName
            if routeField.type() == QVariant.String:
                routeFieldStr += "varchar(%s)" % routeField.length()
            elif routeField.type() == QVariant.Int:
                routeFieldStr += "int"
            elif routeField.type() == QVariant.Double:
                routeFieldStr += "double precision"
            else:
                routeFieldStr += "varchar(20)"

            sql = "create table %s.%s ( %s, m_from double precision, m_to double precision)" % (outputSchema, outputTable, routeFieldStr)
            self.postgisExecute ( conn, sql )

            srid = -1
            authid = self.lrs.crs.authid()
            if authid.lower().startswith('epsg:'):
                srid = authid.split(':')[1]
            sql = "select AddGeometryColumn('%s', '%s', 'geom', %s, 'LINESTRINGM', 3)" % ( outputSchema, outputTable, srid )
            self.postgisExecute ( conn, sql )

            for part in self.lrs.getParts():
                if not part.records: continue
                wkt = part.getWktWithMeasures()
                if not wkt: continue

                if routeField.type() == QVariant.Int or routeField.type() == QVariant.Double:
                    routeVal = part.routeId
                else:
                    routeVal = "'%s'" % part.routeId

                sql = "insert into %s.%s ( %s, m_from, m_to, geom) values ( %s, %s, %s, GeometryFromText('%s', %s))" % ( outputSchema, outputTable, routeFieldName, routeVal, part.milestoneMeasureFrom(), part.milestoneMeasureTo(), wkt, srid )
                self.postgisExecute ( conn, sql )

            conn.commit()
            conn.close()

        except Exception, e:
            conn.close()
            QMessageBox.critical( self, 'Error', '%s' % e )
            return

        QMessageBox.information( self, 'Information', 'Exported successfully' )

################################## STATS ##########################################

    def resetStats(self):
        #debug ( 'setStats' )
        html = self.lrs.getStatsHtml() if self.lrs else ''
        self.statsTextEdit.setHtml( html )
        

