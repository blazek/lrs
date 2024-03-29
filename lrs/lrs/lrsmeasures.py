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

# Note that there is QgsGeometryAnalyzer.eventLayer() working with low level WKB (z coordinates)


# Calculate measures
class LrsMeasures(QObject):
    def __init__(self, iface, lrs, progressBar):
        # debug( "LrsMeasures.__init__")
        self.iface = iface
        self.lrs = lrs  # Lrs object
        self.progressBar = progressBar

    def calculate(self, layer, routeFieldName, outputRouteFieldName, measureFieldName, threshold, outputName):
        # get the  lrs layer's route field, to obtain its type
        lrsFields = self.lrs.layer.fields()
        lrsRouteField = lrsFields.at(lrsFields.indexFromName(self.lrs.routeFieldName))

        # create new layer
        # it may happen that memory provider does not support all fields types, see #10, check if fields exists
        # uri = "Point?crs=%s" %  crsString ( self.iface.mapCanvas().mapSettings().destinationCrs() )
        uri = "Point?crs=%s" % crsString(layer.crs())
        provider = QgsProviderRegistry.instance().createProvider('memory', uri)
        fieldsList = layer.fields().toList()
        fixFields(fieldsList)
        provider.addAttributes(fieldsList)
        provider.addAttributes([
            QgsField(outputRouteFieldName, lrsRouteField.type(), lrsRouteField.typeName()),
            QgsField(measureFieldName, QVariant.Double, "double"),
        ])

        uri = provider.dataSourceUri()
        outputLayer = QgsVectorLayer(uri, outputName, 'memory')

        checkFields(layer, outputLayer)

        # Not sure why attributes were set again here, the attributes are already in uri
        # outputLayer.startEditing()  # to add fields
        # for field in layer.fields():
        #     if not outputLayer.addAttribute(field):
        #         QMess        # create new layerageBox.information(self, 'Information', 'Cannot add attribute %s' % field.name())
        #
        # outputLayer.addAttribute(QgsField(outputRouteFieldName, QVariant.String, "string"))
        # outputLayer.addAttribute(QgsField(measureFieldName, QVariant.Double, "double"))
        # outputLayer.commitChanges()

        outputFeatures = []
        fields = outputLayer.fields()
        total = layer.featureCount()
        count = 0
        transform = None
        if layer.crs() != self.lrs.crs:
            transform = QgsCoordinateTransform(layer.crs(), self.lrs.crs, QgsProject.instance())
        for feature in layer.getFeatures():
            featureRouteId = None
            points = []

            geo = feature.geometry()
            if geo:
                if QgsWkbTypes.isSingleType(geo.wkbType()):
                    points = [geo.asPoint()]
                else:
                    points = geo.asMultiPoint()

            # fetch the route, if any, specified by the feature
            if routeFieldName is not None:
                featureRouteId = feature[routeFieldName]
                if (type(featureRouteId) is QVariant) and featureRouteId.isNull():
                    featureRouteId = None
                else:
                    featureRoute = self.lrs.getRouteIfExists(featureRouteId)

            for point in points:
                outputFeature = QgsFeature(fields)  # fields must exist during feature life!
                outputFeature.setGeometry(QgsGeometry.fromPointXY(point))

                for field in layer.fields():
                    if outputFeature.fields().indexFromName(field.name()) >= 0:
                        outputFeature[field.name()] = feature[field.name()]

                if transform:
                    point = transform.transform(point)

                # measure along the feature's route, if it specifies one; otherwise, find the nearest route and
                # measure along it
                if featureRouteId is not None:
                    routeId = featureRouteId
                    measure = featureRoute.pointMeasure(point) if featureRoute is not None else None
                else:
                    routeId, measure = self.lrs.pointMeasure(point, threshold)
                # debug ( "routeId = %s merasure = %s" % (routeId, measure) )

                if routeId is not None:
                    outputFeature[outputRouteFieldName] = routeId
                outputFeature[measureFieldName] = measure

                outputFeatures.append(outputFeature)

            count += 1
            percent = 100 * count / total
            self.progressBar.setValue(int(percent))

        outputLayer.dataProvider().addFeatures(outputFeatures)

        QgsProject.instance().addMapLayers([outputLayer, ])

        self.progressBar.hide()
