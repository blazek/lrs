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
from error import *

# keeps track of features by checksum
class LrsLayerManager(object):

    def __init__(self, layer ):
        super(LrsLayerManager, self).__init__()
        self.layer = layer
        self.featureIds = {} # dictionary of features with checksum keys

    # add features with getChecksum() method
    def addFeatures(self, features):
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

    def updateFeatures(self, features):
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
    def addErrors(self, errors):
        if not self.layer: return
    
        features = []
        for error in errors:
            if not self.errorTypeMatch( error): continue
            feature = LrsErrorFeature( error )
            #feature.setGeometry( error.geo )
            #for name, value in self.errorAttributesMap( error).iteritems():
            #    feature.setAttribute( name, value )
            features.append( feature )

        self.addFeatures(features)



    def updateErrors(self, errorUpdates):
        debug ( "%s" % errorUpdates )
        if not self.layer: return

        # delete
        self.deleteChecksums( errorUpdates['removedErrorChecksums'] )

        # update 
        features = []
        for error in errorUpdates['updatedErrors']:
            if not self.errorTypeMatch( error): continue

            feature = LrsErrorFeature( error )
            features.append( feature)
        self.updateFeatures(features)

        # add new
        self.addErrors( errorUpdates['addedErrors'] ) 

class LrsQualityLayerManager(LrsLayerManager):

    def __init__(self, layer ):
        super(LrsQualityLayerManager, self).__init__(layer)
        

    def update(self, errorUpdates):
        debug ( "%s" % errorUpdates )
        if not self.layer: return

        # delete
        self.deleteChecksums( errorUpdates['removedQualityChecksums'] )

        # no update, only remove and add

        # add new
        self.addFeatures( errorUpdates['addedQualityFeatures'] ) 
