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

from utils import *
from error import *

# To add methods on layers, we must use manager, not extended QgsVectorLayer, 
# because layers may be stored in project and created by QGIS.
# Inherited layers are only used to create layer with type and attributes
class LrsErrorLayer(QgsVectorLayer):

    def __init__(self, uri, baseName ):
        provider = QgsProviderRegistry.instance().provider( 'memory', uri )
        provider.addAttributes( LRS_ERROR_FIELDS.toList()  )
        uri = provider.dataSourceUri()
        super(LrsErrorLayer, self).__init__( uri, baseName, 'memory')

# changes done to vector layer attributes are not store correctly in project file
# http://hub.qgis.org/issues/8997 -> recreate temporary provider first to construct uri

class LrsErrorPointLayer(LrsErrorLayer):

    def __init__(self, crs ):
        uri = "Point?crs=%s" %  crs.authid()
        super(LrsErrorPointLayer, self).__init__( uri, 'LRS point errors' )
        
class LrsErrorLineLayer(LrsErrorLayer):

    def __init__(self, crs ):
        uri = "LineString?crs=%s" %  crs.authid()
        super(LrsErrorLineLayer, self).__init__( uri, 'LRS line errors' )

class LrsQualityLayer(QgsVectorLayer):

    def __init__(self, crs ):
        uri = "LineString?crs=%s" %  crs.authid()
        provider = QgsProviderRegistry.instance().provider( 'memory', uri )
        provider.addAttributes( LRS_QUALITY_FIELDS.toList() )
        uri = provider.dataSourceUri()
        super(LrsQualityLayer, self).__init__( uri, 'LRS quality', 'memory')

        # min, max, color, label
        styles = [
            [ 0, 10, QColor(Qt.green), '0 - 10 % error' ],
            [ 10, 30, QColor(Qt.blue), '10 - 30 % error' ],
            [ 30, 1000000, QColor(Qt.red), '> 30 % error' ]
        ]
        ranges = []
        for style in styles:
            symbol = QgsSymbolV2.defaultSymbol(  QGis.Line )
            symbol.setColor( style[2] )
            range = QgsRendererRangeV2 ( style[0], style[1], symbol, style[3] )
            ranges.append(range)

        renderer = QgsGraduatedSymbolRendererV2( 'err_perc', ranges)
        self.setRendererV2 ( renderer )


# Keeps track of features by checksum.
class LrsLayerManager(object):

    def __init__(self, layer ):
        super(LrsLayerManager, self).__init__()
        self.layer = layer
        self.featureIds = {} # dictionary of features with checksum keys

    # remove all features
    def clear(self):
        if not self.layer: return
        fids = []
        for feature in self.layer.getFeatures():
            fids.append( feature.id() )

        self.layer.dataProvider().deleteFeatures( fids )
        
        for fid in fids:
            # hack to update attribute table
            self.layer.featureDeleted.emit( fid )

    # transform features if necessary to layer crs
    # modifies original feature geometry
    def transformFeatures(self, features, crs):
        if crs != self.layer.crs():
            transform = QgsCoordinateTransform( crs, self.layer.crs())   
            for feature in features:
                feature.geometry().transform( transform )
        return features 

    # add features with getChecksum() method
    def addFeatures(self, features, crs):
        features = self.transformFeatures(features, crs)
 
        status, addedFeatures = self.layer.dataProvider().addFeatures( features )
        for feature, addedFeature in zip(features,addedFeatures):
            self.featureIds[feature.getChecksum()] = addedFeature.id()
            # hack to update attribute table
            self.layer.featureAdded.emit( addedFeature.id() )

    # delete features by checksums
    def deleteChecksums(self,checksums):
        fids = []
        for checksum in checksums:
            fid = self.featureIds.get( checksum , None )
            if fid:
                fids.append ( fid )

        if len (fids) > 0:
            self.layer.dataProvider().deleteFeatures( fids )

        for fid in fids:
            # hack to update attribute table
            self.layer.featureDeleted.emit( fid )

    def updateFeatures(self, features, crs):
        features = self.transformFeatures(features, crs)
        changedGeometries = {}
        changedAttributes = {}
        for feature in features:
            checksum = feature.getChecksum()
            fid = self.featureIds.get( checksum , None ) 
            if not fid: raise Exception( "Error feature not found" )
            changedGeometries[fid] = feature.geometry()
            changedAttributes[fid] = feature.getAttributeMap()
        #debug ( "changedGeometries: %s" % changedGeometries )
        self.layer.dataProvider().changeGeometryValues(changedGeometries)
        self.layer.dataProvider().changeAttributeValues(changedAttributes)

        # hack to update attribute table
        for fid, attr in changedAttributes.iteritems():
            for i, value in attr.iteritems():
                self.layer.attributeValueChanged.emit(fid, i, value )

class LrsErrorLayerManager(LrsLayerManager):

    def __init__(self, layer ):
        super(LrsErrorLayerManager, self).__init__(layer)
        
    # test if error geometry type matches this layer
    def errorTypeMatch(self, error): 
        if self.layer.geometryType() == QGis.Point and error.geo.wkbType() != QGis.WKBPoint: return False
        if self.layer.geometryType() == QGis.Line and error.geo.wkbType() != QGis.WKBLineString: return False
        return True


    # get errors of layer type (point or line)
    def addErrors(self, errors, crs):
        if not self.layer: return

        features = []
        for error in errors:
            if not self.errorTypeMatch( error): continue
            feature = LrsErrorFeature( error )
            features.append( feature )

        self.addFeatures(features, crs)



    def updateErrors(self, errorUpdates):
        #debug ( "%s" % errorUpdates )
        if not self.layer: return

        # delete
        self.deleteChecksums( errorUpdates['removedErrorChecksums'] )

        # update 
        features = []
        for error in errorUpdates['updatedErrors']:
            if not self.errorTypeMatch( error): continue

            feature = LrsErrorFeature( error )
            features.append( feature)
        self.updateFeatures(features, errorUpdates['crs'])

        # add new
        self.addErrors( errorUpdates['addedErrors'], errorUpdates['crs'] ) 

class LrsQualityLayerManager(LrsLayerManager):

    def __init__(self, layer ):
        super(LrsQualityLayerManager, self).__init__(layer)
        

    def update(self, errorUpdates):
        #debug ( "%s" % errorUpdates )
        if not self.layer: return

        # delete
        self.deleteChecksums( errorUpdates['removedQualityChecksums'] )

        # no update, only remove and add

        # add new
        self.addFeatures( errorUpdates['addedQualityFeatures'], errorUpdates['crs'] ) 
