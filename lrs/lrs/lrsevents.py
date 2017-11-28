# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsDockWidget
                                 A QGIS plugin
 Linear reference system builder and editor
                             -------------------
        begin                : 2017-5-20
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

from .utils import *


# Generates events
class LrsEvents(QObject):
    def __init__(self, iface, lrs, progressBar):
        # debug( "LrsEvents.__init__")
        self.iface = iface
        self.lrs = lrs  # Lrs object
        self.progressBar = progressBar

    def create(self, layer, featuresSelect, routeFieldName, startFieldName, endFieldName, errorFieldName, outputName):
        # create new layer
        geometryType = "MultiLineString" if endFieldName else "Point"
        uri = geometryType
        uri += "?crs=%s" % crsString(self.iface.mapCanvas().mapSettings().destinationCrs())
        provider = QgsProviderRegistry.instance().createProvider('memory', uri)
        # Because memory provider (QGIS 2.4) fails to parse PostGIS type names (like int8, float, float8 ...)
        # and negative length and precision we overwrite type names according to types and reset length and precision
        fieldsList = layer.pendingFields().toList()
        fixFields(fieldsList)
        provider.addAttributes(fieldsList)
        if errorFieldName:
            provider.addAttributes([QgsField(errorFieldName, QVariant.String, "string"), ])
        uri = provider.dataSourceUri()
        # debug('uri: %s' % uri)

        outputLayer = QgsVectorLayer(uri, outputName, 'memory')
        if not outputLayer.isValid():
            QMessageBox.information(self, 'Information', 'Cannot create memory layer with uri %s' % uri)

        checkFields(layer, outputLayer)

        # Not sure why attributes were set again here, the attributes are already in uri
        # outputLayer.startEditing()  # to add fields
        # for field in layer.pendingFields():
        #    if not outputLayer.addAttribute(field):
        #        QMessageBox.information(self, 'Information', 'Cannot add attribute %s' % field.name())

        # if errorFieldName:
        #    outputLayer.addAttribute(QgsField(errorFieldName, QVariant.String, "string"))

        # outputLayer.commitChanges()

        # It may happen that event goes slightly outside available lrs because of
        # decimal number inaccuracy. Thus we set tolerance used to try to find nearest point event within that
        # tolerance and skip smaller linear event errors (gaps)
        # 0.1m is too much and less than 0.01 m does not make sense in standard GIS
        #eventTolerance = convertDistanceUnits(0.01, LrsUnits.METER, self.lrs.measureUnit)

        # For LrsLayer with existing measure we don't know measure units, but it is little probable that it is
        # more than km or miles (if we stay on Earth) 0.0001 km = 10 cm tolerance should not be too much for
        # meters and it should sufficient for km
        # TODO: add tolerance widget?
        eventTolerance = 0.0001

        outputFeatures = []
        fields = outputLayer.pendingFields()
        #debug("create featuresSelect = %s" % featuresSelect)
        if featuresSelect == SELECTED_FEATURES:
            featuresIterator = layer.getSelectedFeatures()
            total = layer.selectedFeatureCount()
        else:
            featuresIterator = layer.getFeatures()
            total = layer.featureCount()
        count = 0
        for feature in featuresIterator:
            #debug("create feature.id = %s" % feature.id())
            routeId = feature[routeFieldName]
            start = feature[startFieldName]
            end = feature[endFieldName] if endFieldName else None
            # debug ( "event routeId = %s start = %s end = %s" % ( routeId, start, end ) )

            outputFeature = QgsFeature(fields)  # fields must exist during feature life!
            for field in layer.pendingFields():
                if outputFeature.fields().indexFromName(field.name()) >= 0:
                    outputFeature[field.name()] = feature[field.name()]

            geo = None
            if endFieldName:
                line, error = self.lrs.eventMultiPolyLine(routeId, start, end, eventTolerance)
                if line:
                    geo = QgsGeometry.fromMultiPolylineXY(line)
            else:
                point, error = self.lrs.eventPoint(routeId, start, eventTolerance)
                if point:
                    geo = QgsGeometry(QgsPoint(point))

            if geo:
                outputFeature.setGeometry(geo)

            if errorFieldName and error:
                outputFeature[errorFieldName] = error

            outputFeatures.append(outputFeature)

            count += 1
            percent = 100 * count / total;
            self.progressBar.setValue(percent)

        outputLayer.dataProvider().addFeatures(outputFeatures)

        QgsProject.instance().addMapLayers([outputLayer, ])

        self.progressBar.hide()
