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

class LrsDockWidget( QDockWidget, Ui_LrsDockWidget ):
    def __init__( self,parent, iface ):
        self.iface = iface
        self.mapUnitsPerMeasureUnit = None
        self.lrs = None # Lrs object
        self.errorPointLayer = None
        self.errorPointLayerManager = None
        self.errorLineLayer = None
        self.errorLineLayerManager = None
        self.qualityLayer = None
        self.qualityLayerManager = None
 
        super(LrsDockWidget, self).__init__(parent )
        
        # Set up the user interface from Designer.
        self.setupUi( self )

        # keep progress frame height
        self.genProgressFrame.setMinimumHeight( self.genProgressFrame.height() )
        self.hideProgress()

        ##### getTab 
        # initLayer, initField, fieldType did not work, fixed and created pull request
        # https://github.com/3nids/qgiscombomanager/pull/1

        self.genLineLayerCM = LrsLayerComboManager( self.genLineLayerCombo, geometryType = QGis.Line, settingsName = 'lineLayerId' )
        self.genLineRouteFieldCM = LrsFieldComboManager( self.genLineRouteFieldCombo, self.genLineLayerCM, settingsName = 'lineRouteField' )
        self.genPointLayerCM = LrsLayerComboManager( self.genPointLayerCombo, geometryType = QGis.Point, settingsName = 'pointLayerId' )
        self.genPointRouteFieldCM = LrsFieldComboManager( self.genPointRouteFieldCombo, self.genPointLayerCM, settingsName = 'pointRouteField' )
        self.genPointMeasureFieldCM = LrsFieldComboManager( self.genPointMeasureFieldCombo, self.genPointLayerCM, types = [ QVariant.Int, QVariant.Double ], settingsName = 'pointMeasureField' )

        self.genMapUnitsPerMeasureUnitWM = LrsWidgetManager( self.genMapUnitsPerMeasureUnitSpin, settingsName = 'mapUnitsPerMeasureUnit', defaultValue = 1000.0 )
        self.genThresholdWM = LrsWidgetManager( self.genThresholdSpin, settingsName = 'threshold', defaultValue = 200.0 )

        self.genLineLayerCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genLineRouteFieldCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genPointLayerCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genPointRouteFieldCombo.currentIndexChanged.connect(self.resetGenerateButtons)
        self.genPointMeasureFieldCombo.currentIndexChanged.connect(self.resetGenerateButtons)

        self.genButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.generateLrs)
        self.genButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetGenerateOptionsAndWrite)

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

        #### eventsTab
        self.eventsLayerCM = LrsLayerComboManager( self.eventsLayerCombo, settingsName = 'eventsLayerId' )
        self.eventsRouteFieldCM = LrsFieldComboManager( self.eventsRouteFieldCombo, self.eventsLayerCM, settingsName = 'eventsRouteField' )
        self.eventsMeasureStartFieldCM = LrsFieldComboManager( self.eventsMeasureStartFieldCombo, self.eventsLayerCM, types = [ QVariant.Int, QVariant.Double ], settingsName = 'eventsMeasureStartField' )
        self.eventsMeasureEndFieldCM = LrsFieldComboManager( self.eventsMeasureEndFieldCombo, self.eventsLayerCM, types = [ QVariant.Int, QVariant.Double ], allowNone = True, settingsName = 'eventsMeasureEndField' )

        self.eventsOutputNameWM = LrsWidgetManager( self.eventsOutputNameLineEdit, settingsName = 'eventsOutputName', defaultValue = 'LRS events' )
        self.eventsErrorFieldWM = LrsWidgetManager( self.eventsErrorFieldLineEdit, settingsName = 'eventsErrorField', defaultValue = 'lrs_err' )
        validator = QRegExpValidator( QRegExp( '[A-Za-z_][A-Za-z0-9_]+' ) )
        self.eventsErrorFieldLineEdit.setValidator( validator )

        self.eventsButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.createEvents)
        self.eventsButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetEventsOptionsAndWrite)
        self.eventsLayerCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsRouteFieldCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsMeasureStartFieldCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsMeasureEndFieldCombo.currentIndexChanged.connect(self.resetEventsButtons)
        self.eventsOutputNameLineEdit.textEdited.connect(self.resetEventsButtons)
        self.resetEventsOptions()
        self.resetEventsButtons()

        #### measureTab
        self.measureLayerCM = LrsLayerComboManager( self.measureLayerCombo, geometryType = QGis.Point, settingsName = 'measureLayerId' )
        self.measureThresholdWM = LrsWidgetManager( self.measureThresholdSpin, settingsName = 'measureThreshold', defaultValue = 200.0 )
        self.measureOutputNameWM = LrsWidgetManager( self.measureOutputNameLineEdit, settingsName = 'measureOutputName', defaultValue = 'LRS measure' )

        self.measureRouteFieldWM = LrsWidgetManager( self.measureRouteFieldLineEdit, settingsName = 'measureRouteField', defaultValue = 'route' )
        validator = QRegExpValidator( QRegExp( '[A-Za-z_][A-Za-z0-9_]+' ) )
        self.measureRouteFieldLineEdit.setValidator( validator )

        self.measureMeasureFieldWM = LrsWidgetManager( self.measureMeasureFieldLineEdit, settingsName = 'measureMeasureField', defaultValue = 'measure' )
        self.measureMeasureFieldLineEdit.setValidator( validator )


        self.measureButtonBox.button(QDialogButtonBox.Ok).clicked.connect(self.calculateMeasures)
        self.measureButtonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetMeasureOptionsAndWrite)
        self.measureLayerCombo.currentIndexChanged.connect(self.resetMeasureButtons)
        self.measureOutputNameLineEdit.textEdited.connect(self.resetMeasureButtons)
        self.measureRouteFieldLineEdit.textEdited.connect(self.resetMeasureButtons)
        self.measureMeasureFieldLineEdit.textEdited.connect(self.resetMeasureButtons)
        self.resetMeasureOptions()
        self.resetMeasureButtons()

        #####
        self.enableTabs()

        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.layersWillBeRemoved)
        
        QgsProject.instance().readProject.connect( self.projectRead )

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
        if self.genLineLayerCM.getLayer():
            self.generateLrs() # only when reloading!

    def close(self):
        if self.lrs:
            del self.lrs
        self.lrs = None
        QgsMapLayerRegistry.instance().layersWillBeRemoved.disconnect(self.layersWillBeRemoved)
        QgsProject.instance().readProject.disconnect( self.projectRead )

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
        self.errorTab.setEnabled( enable )
        self.eventsTab.setEnabled( enable )
        self.measureTab.setEnabled( enable )

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
        self.genMapUnitsPerMeasureUnitWM.reset()
        self.genThresholdWM.reset()
        
    def resetGenerateOptionsAndWrite(self):
        self.resetGenerateOptions()
        self.writeGenerateOptions()

    # save settings in project
    def writeGenerateOptions(self):
        self.genLineLayerCM.writeToProject()
        self.genLineRouteFieldCM.writeToProject()
        self.genPointLayerCM.writeToProject()
        self.genPointRouteFieldCM.writeToProject()
        self.genPointMeasureFieldCM.writeToProject()
        self.genMapUnitsPerMeasureUnitWM.writeToProject()
        self.genThresholdWM.writeToProject() 

    def readGenerateOptions(self):
        self.genLineLayerCM.readFromProject()
        self.genLineRouteFieldCM.readFromProject()
        self.genPointLayerCM.readFromProject()
        self.genPointRouteFieldCM.readFromProject()
        self.genPointMeasureFieldCM.readFromProject()
        self.genMapUnitsPerMeasureUnitWM.readFromProject()
        self.genThresholdWM.readFromProject()

    def generateLrs(self):
        #debug ( 'generateLrs')
        self.errorVisualizer.clearHighlight()
        
        self.writeGenerateOptions()

        crs = self.genLineLayerCM.getLayer().crs()
        if self.iface.mapCanvas().mapRenderer().hasCrsTransformEnabled():
            self.lrsCrs = self.iface.mapCanvas().mapRenderer().destinationCrs()

        #crs = self.genLineLayerCM.getLayer().crs() # debug 

        threshold = self.genThresholdSpin.value()
        self.mapUnitsPerMeasureUnit = self.genMapUnitsPerMeasureUnitSpin.value()
        self.lrs = Lrs ( self.genLineLayerCM.getLayer(), self.genLineRouteFieldCM.getFieldName(), self.genPointLayerCM.getLayer(), self.genPointRouteFieldCM.getFieldName(), self.genPointMeasureFieldCM.getFieldName(), crs = crs, threshold = threshold, mapUnitsPerMeasureUnit = self.mapUnitsPerMeasureUnit )

        self.lrs.progressChanged.connect(self.showProgress)
        self.lrs.calibrate()
        self.hideProgress()
    
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
        self.enableTabs()

    def showProgress(self, label, percent):
        self.genProgressLabel.show()
        self.genProgressBar.show()
        self.genProgressLabel.setText( label )
        self.genProgressBar.setValue( percent)

    def hideProgress(self):
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
        self.updateErrorLayers( errorUpdates )
        self.updateQualityLayer( errorUpdates )

    def errorSelectionChanged(self, selected, deselected ):
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
            self.errorLineLayer = LrsErrorLineLayer( self.iface.mapCanvas().mapRenderer().destinationCrs() )
            self.errorLineLayerManager = LrsErrorLayerManager(self.errorLineLayer)
            self.errorLineLayer.rendererV2().symbol().setColor( QColor(Qt.red) )
            self.resetErrorLineLayer()
            QgsMapLayerRegistry.instance().addMapLayers( [self.errorLineLayer,] )
            project.writeEntry( PROJECT_PLUGIN_NAME, "errorLineLayerId", self.errorLineLayer.id() )

        if not self.errorPointLayer:
            self.errorPointLayer = LrsErrorPointLayer( self.iface.mapCanvas().mapRenderer().destinationCrs() )
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
            self.qualityLayer = LrsQualityLayer(self.iface.mapCanvas().mapRenderer().destinationCrs())
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

        layer = self.eventsLayerCM.getLayer()
        routeFieldName = self.eventsRouteFieldCM.getFieldName()
        startFieldName = self.eventsMeasureStartFieldCM.getFieldName()
        endFieldName = self.eventsMeasureEndFieldCM.getFieldName()
        outputName = self.eventsOutputNameLineEdit.text()
        if not outputName: outputName = self.eventsOutputNameWM.defaultValue()
        errorFieldName = self.eventsErrorFieldLineEdit.text()
 
        # create new layer
        uri = "MultiLineString" if endFieldName else "Point"
        uri += "?crs=%s" %  self.iface.mapCanvas().mapRenderer().destinationCrs().authid()
        provider = QgsProviderRegistry.instance().provider( 'memory', uri )
        provider.addAttributes( layer.pendingFields().toList() )
        if errorFieldName:
            provider.addAttributes( [ QgsField( errorFieldName, QVariant.String, "string"), ]) 
        uri = provider.dataSourceUri()
        outputLayer = QgsVectorLayer ( uri, outputName, 'memory')

        outputFeatures = []
        fields = outputLayer.pendingFields()
        for feature in layer.getFeatures():
            routeId = feature[routeFieldName]
            start = feature[startFieldName]
            end = feature[endFieldName] if endFieldName else None
            #debug ( "event routeId = %s start = %s end = %s" % ( routeId, start, end ) )

            outputFeature = QgsFeature( fields ) # fields must exist during feature life!
            for field in layer.pendingFields():
                outputFeature[field.name()] = feature[field.name()]
            
            geo = QgsGeometry()
            if endFieldName:
                line, error = self.lrs.eventMultiPolyLine ( routeId, start, end )
                if line:
                    geo = QgsGeometry.fromMultiPolyline( line )
            else:
                point, error = self.lrs.eventPoint ( routeId, start )
                if point:
                    geo = QgsGeometry.fromPoint( point )
            
            if not geo: geo = QgsGeometry()
            if geo:
                outputFeature.setGeometry( geo )
            if errorFieldName and error:
                outputFeature[errorFieldName] = error

            outputFeatures.append( outputFeature )

        outputLayer.dataProvider().addFeatures( outputFeatures )

        QgsMapLayerRegistry.instance().addMapLayers( [outputLayer,] )

############################# MEASURE ####################################

    def resetMeasureOptions(self):
        #debug('resetMeasureOptions')
        self.measureLayerCM.reset() 
        self.measureThresholdWM.reset()
        self.measureOutputNameWM.reset()
        self.measureRouteFieldWM.reset()
        self.measureMeasureFieldWM.reset()

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

    def calculateMeasures(self):
        #debug('calculateMeasures')
        self.writeMeasureOptions()

        layer = self.measureLayerCM.getLayer()
        threshold = self.measureThresholdSpin.value()
        outputName = self.measureOutputNameLineEdit.text()
        if not outputName: outputName = self.measureOutputNameWM.defaultValue()
        routeFieldName = self.measureRouteFieldLineEdit.text()
        measureFieldName = self.measureMeasureFieldLineEdit.text()
 
        # create new layer
        uri = "Point?crs=%s" %  self.iface.mapCanvas().mapRenderer().destinationCrs().authid()
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
        for feature in layer.getFeatures():
            points = []
            
            geo = feature.geometry()
            if geo:
                if geo.wkbType() in [ QGis.WKBPoint, QGis.WKBPoint25D]:
                    points = [ geo.asPoint() ]
                elif geo.wkbType() in [ QGis.WKBMultiPoint, QGis.WKBMultiPoint25D]:
                    points = geo.asMultiPoint()

            # TODO: reprojection

            for point in points:
                outputFeature = QgsFeature( fields ) # fields must exist during feature life!
                outputFeature.setGeometry( QgsGeometry.fromPoint( point ) )
                
                for field in layer.pendingFields():
                    outputFeature[field.name()] = feature[field.name()]
                
                routeId, measure = self.lrs.pointMeasure ( point, threshold )
                debug ( "routeId = %s merasure = %s" % (routeId, measure) )

                if routeId is not None:
                    outputFeature[routeFieldName] = '%s' % routeId
                outputFeature[measureFieldName] = measure

                outputFeatures.append( outputFeature )

        outputLayer.dataProvider().addFeatures( outputFeatures )

        QgsMapLayerRegistry.instance().addMapLayers( [outputLayer,] )
