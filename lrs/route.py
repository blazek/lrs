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

    def __init__(self, layer, routeId):
        debug ('init route %s' % routeId )
        #self.lrsCrs = lrsCrs
        self.layer = layer
        self.routeId = routeId
        self.errors = [] # list of LrsError
        
        # geometry parts of all lines as QgsPolyline (=QVector<QgsPoint>)
        self.polylines = []

        # list of LrsRoutePart
        self.parts = []

        self.points = [] # list of LrsPoint

    def addLine( self, geo ):
        # add all geometry parts

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
                    nodes[ ph ] = { 'point': polyline[i], 'lines': 1 }
                else:
                    nodes[ ph ]['lines'] += 1 

        for node in nodes.values():
            if node['lines'] > 2:
                geo = QgsGeometry()
                geo.fromPoint( node['point'] )
                self.errors.append( LrsError( LrsError.FORK, geo ) )    

        ###### join polylines to parts
        while len( self.polylines ) > 0:
            polyline = self.polylines.pop(0)
            while True: # connect parts
                connected = False
                for i in range(len( self.polylines )):
                    polyline2 = self.polylines[i]

                    # dont connect in forks (we don't know which is better)
                    fork = False
                    for j in [0, -1]:
                        ph = pointHash( polyline2[j] )
                        if nodes[ph]['lines'] > 2:
                            fork = True
                            break
                    if fork: 
                        #debug ('skip fork' )
                        continue

                    if polyline[-1] == polyline2[0]: # --1-->  --2-->
                        del polyline2[0]
                        polyline.extend(polyline2)
                        connected = True
                    elif polyline[-1] == polyline2[-1]: # --1--> <--2--
                        polyline2.reverse()
                        del polyline2[0]
                        polyline.extend(polyline2)
                        connected = True
                    elif polyline[0] == polyline2[-1]: # --2--> --1-->
                        del polyline[0]
                        polyline2.extend(polyline)
                        polyline = polyline2
                        connected = True
                    elif polyline[0] == polyline2[0]: # <--2-- --1-->
                        polyline2.reverse()
                        del polyline[0]
                        polyline2.extend(polyline)
                        polyline = polyline2
                        connected = True

                    if connected: 
                        #print '%s part connected' % i
                        del self.polylines[i]
                        break

                if not connected: # no more parts can be connected
                    break

            self.parts.append( LrsRoutePart( polyline) )

    def addPoint( self, point ):
       self.points.append ( point )

    def getErrors(self):
        return self.errors 
