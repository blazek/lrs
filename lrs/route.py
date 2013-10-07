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
from part import LrsRoutePart
from error import LrsError

# LrsRoute keeps list of LrsLine 

class LrsRoute:

    def __init__(self, layer, routeId, transform):
        debug ('init route %s' % routeId )
        #self.lrsCrs = lrsCrs
        self.transform = transform
        self.layer = layer
        self.routeId = routeId
        self.errors = [] # list of LrsError
        
        # geometry parts of all lines as QgsPolyline (=QVector<QgsPoint>)
        self.polylines = []

        # list of LrsRoutePart
        self.parts = []

    def addLine( self, feature ):
        #self.lines.append( LrsLine( self.layer, feature ) )   
        # add copy of all geometry parts
        geo = feature.geometry()
        if not geo : return

        if self.transform:
            geo.transform( self.transform )

        # QGis::singleType and flatType are not in bindings (2.0)
        if geo.wkbType() in [ QGis.WKBLineString, QGis.WKBLineString25D]:
            self.polylines.append( geo.asPolyline() )
        else: # multiline
            self.polylines.extend ( geo.asMultiPolyline() )

        
    # create LrsRoutePart from eometryParts
    def buildParts(self):
        ##### check for duplicates
        duplicates = set()
        for i in range(len(self.polylines)-1):
            for j in range(i+1,len(self.polylines)):
                if polylinesIdentical( self.polylines[i], self.polylines[j] ):
                    debug( 'identical polylines %d and %d' % (i, j) )
                    duplicates.add(j)
        # make reverse ordered unique list of duplicates and delete
        duplicates = list( duplicates )
        duplicates.sort(reverse=True)
        for d in duplicates:
            geo = QgsGeometry()
            geo.fromPolyline( self.polylines[d] )
            self.errors.append( LrsError( LrsError.DUPLICATE_LINE, geo ) )
            del  self.polylines[d]
             
        ###### find forks
        nodes = {} 
        for polyline in self.polylines:
            for i in [0,-1]:    
                ph = pointHash( polyline[i] )
                if not nodes.has_key( ph ):
                    nodes[ ph ] = { 'point': polyline[i], 'count': 1 }
                else:
                    nodes[ ph ]['count'] += 1 

        for node in nodes.values():
            if node['count'] > 2:
                geo = QgsGeometry()
                geo.fromPoint( node['point'] )
                self.errors.append( LrsError( LrsError.FORK, geo ) )    

    def getErrors(self):
        return self.errors 
