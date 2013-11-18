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

# keeps track of features by checksum
class LrsErrorLayerManager(object):

    def __init__(self, layer ):
        super(LrsErrorLayerManager, self).__init__()
        self.layer = layer
        self.featureIds = {} # dictionary of features with checksum keys
        
    # test if error geometry type matches this layer
    def errorTypeMatch(self, error): 
        if self.layer.geometryType() == QGis.Point and error.geo.wkbType() != QGis.WKBPoint: return False
        if self.layer.geometryType() == QGis.Line and error.geo.wkbType() != QGis.WKBLineString: return False
        return True

    def getMaxFid(self):
        fid = 0
        for feature in self.layer.getFeatures( QgsFeatureRequest() ):
            fid = max( fid, feature.id() )
        return fid 

    # get errors of layer type (point or line)
    def addErrors(self, errors):
        if not self.layer: return
    
        fields = self.layer.pendingFields()
        features = []
        checksums = []
        for error in errors:
            if not self.errorTypeMatch( error): continue
            feature = QgsFeature( fields )
            feature.setGeometry( error.geo )
            #feature.setAttribute( 'error', error.typeLabel() )
            #feature.setAttribute( 'route', '%s' % error.routeId )
            #feature.setAttribute( 'measure', error.getMeasureString() )
            for name, value in self.errorAttributesMap( error).iteritems():
                feature.setAttribute( name, value )
            features.append( feature )
            checksums.append( error.getChecksum() )

        self.layer.dataProvider().addFeatures( features )

        # hack to keep track of features in memory provider
        # we believe that QgsMemoryProvider::addFeatures is processing
        # features in list in the list order and increases nextFeatureId
        # which may in theory change in future
        maxFid = self.getMaxFid()
        for checksum in reversed(checksums):
            self.featureIds[checksum] = maxFid
            # hack to update attribute table
            self.layer.featureAdded.emit( maxFid )
            maxFid -= 1

    def errorAttributesMap(self, error):
        attributesMap = {}
        fields = self.layer.pendingFields()
        values = {
            'error': error.typeLabel(),
            'route': '%s' % error.routeId,
            'measure': error.getMeasureString()
        }
        for i in range(len(fields)):
            name = fields[i].name()
            if values.has_key(name):
                attributesMap[i] = values.get( name )
        return attributesMap

    def updateErrors(self, errorUpdates):
        debug ( "%s" % errorUpdates )
        if not self.layer: return

        # delete
        fids = []
        for checksum in errorUpdates['removedErrorChecksums']:
            fid = self.featureIds.get( checksum , None )
            if fid:
                fids.append ( fid )
                # hack to update attribute table
                self.layer.featureDeleted.emit( fid )

        if len (fids) > 0:
            self.layer.dataProvider().deleteFeatures( fids )

        # update 
        changedGeometries = {}
        changedAttributes = {}
        for error in errorUpdates['updatedErrors']:
            if not self.errorTypeMatch( error): continue
            checksum = error.getChecksum()
            fid = long ( self.featureIds.get( checksum , None ) )
            if not fid:
                raise Exception( "Error feature not found" )
            debug ( "feature = %s" % getLayerFeature( self.layer, fid ) )
            changedGeometries[fid] = error.geo
            changedAttributes[fid] = self.errorAttributesMap( error )
        debug ( "changedGeometries: %s" % changedGeometries )
        self.layer.dataProvider().changeGeometryValues(changedGeometries)
        self.layer.dataProvider().changeAttributeValues(changedAttributes)

        # hack to update attribute table
        for fid, attr in changedAttributes.iteritems():
            for i, value in attr.iteritems():
                self.layer.attributeValueChanged.emit(fid, i, value )

        # add new
        self.addErrors( errorUpdates['addedErrors'] ) 
