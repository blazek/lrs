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
import sys
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *

from utils import *
from part import LrsRoutePart
from error import LrsError
from point import *

# LrsRoute keeps list of LrsLine 

class LrsRoute:

    def __init__(self, layer, routeId, threshold):
        debug ('init route %s' % routeId )
        self.layer = layer
        self.routeId = routeId
        self.threshold = threshold
        
        self.lines = [] # LrsLine list
        self.points = [] # LrsPoint list

        self.parts = [] # LrsRoutePart list
        self.milestones = [] # LrsMilestone list 
        self.errors = [] # LrsError list

    def addLine( self, line ):
        self.lines.append( line )

    def calibrate(self):
        self.errors = []
        self.buildParts()
        self.createMilestones()
        self.attachMilestones()
 
    # create LrsRoutePart from eometryParts
    def buildParts(self):
        self.parts = []
        polylines = []
        for line in self.lines:
            # QGis::singleType and flatType are not in bindings (2.0)
            if line.geo.wkbType() in [ QGis.WKBLineString, QGis.WKBLineString25D]:
                polylines.append( line.geo.asPolyline() )
            else: # multiline
                polylines.extend ( line.geo.asMultiPolyline() )

        ##### check for duplicates
        duplicates = set()
        for i in range(len(polylines)-1):
            for j in range(i+1,len(polylines)):
                if polylinesIdentical( polylines[i], polylines[j] ):
                    debug( 'identical polylines %d and %d' % (i, j) )
                    duplicates.add(j)
        # make reverse ordered unique list of duplicates and delete
        duplicates = list( duplicates )
        duplicates.sort(reverse=True)
        for d in duplicates: # delete going down (sorted reverse)
            geo = QgsGeometry.fromPolyline( polylines[d] )
            self.errors.append( LrsError( LrsError.DUPLICATE_LINE, geo, routeId = self.routeId ) )
            del  polylines[d]
             
        ###### find forks
        nodes = {} 
        for polyline in polylines:
            for i in [0,-1]:    
                ph = pointHash( polyline[i] )
                if not nodes.has_key( ph ):
                    nodes[ ph ] = { 'pnt': polyline[i], 'nlines': 1 }
                else:
                    nodes[ ph ]['nlines'] += 1 

        for node in nodes.values():
            #debug( "nlines = %s" % node['nlines'] )
            if node['nlines'] > 2:
                geo = QgsGeometry.fromPoint( node['pnt'] )
                self.errors.append( LrsError( LrsError.FORK, geo, routeId = self.routeId ) )    

        ###### join polylines to parts
        while len( polylines ) > 0:
            polyline = polylines.pop(0)
            while True: # connect parts
                connected = False
                for i in range(len( polylines )):
                    polyline2 = polylines[i]

                    # dont connect in forks (we don't know which is better)
                    fork = False
                    for j in [0, -1]:
                        ph = pointHash( polyline2[j] )
                        if nodes[ph]['nlines'] > 2:
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
                        del polylines[i]
                        break

                if not connected: # no more parts can be connected
                    break

            self.parts.append( LrsRoutePart( polyline) )

    def addPoint( self, point ):
       self.points.append ( point )

    def createMilestones(self):
        self.milestones = []

        # check duplicates
        # TODO: maybe allow duplicates? Could be end/start of discontinuous segments
        nodes = {} 
        for point in self.points:
            if point.geo.wkbType() in [ QGis.WKBPoint, QGis.WKBPoint25D]:
                pnts = [ point.geo.asPoint() ]
            else: # multi (makes little sense)
                pnts = point.geo.asMultiPoint()

            for pnt in pnts:
                ph = pointHash( pnt )
                if not nodes.has_key( ph ):
                    nodes[ ph ] = { 'pnt': pnt, 'npoints': 1, 'measures': [ point.measure ] }
                else:
                    nodes[ ph ]['npoints'] += 1 
                    nodes[ ph ]['measures'].append( point.measure )

        for node in nodes.values():
            print "npoints = %s" % node['npoints']
            if node['npoints'] > 1:
                geo = QgsGeometry.fromPoint( node['pnt'] )
                self.errors.append( LrsError( LrsError.DUPLICATE_POINT, geo, routeId = self.routeId, measure = node['measures'] ) )    
    
            measure = node['measures'][0] # first if duplicates, for now
            self.milestones.append ( LrsMilestone( node['pnt'], measure ) )

    # calculate measures along parts
    def attachMilestones(self):
        sqrThreshold = self.threshold * self.threshold
        for milestone in self.milestones:
            pointGeo = QgsGeometry.fromPoint( milestone.pnt )

            nearSqrDist = sys.float_info.max
            nearPartIdx = None
            nearSegment = None
            nearNearestPnt = None 
            for i in range( len(self.parts) ):
                part = self.parts[i]
                partGeo = QgsGeometry.fromPolyline( part.polyline )

                ( sqrDist, nearestPnt, afterVertex ) = partGeo.closestSegmentWithContext( milestone.pnt )
                segment = afterVertex-1
                #debug ('sqrDist %s x %s' % (sqrDist, sqrThreshold) )
                if sqrDist <= sqrThreshold and sqrDist < nearSqrDist:
                    nearSqrDist = sqrDist
                    nearPartIdx = i
                    nearSegment = segment
                    nearNearestPnt = nearestPnt

            debug ('nearest partIdx = %s segment = %s sqrDist = %s' % ( nearPartIdx, nearSegment, nearSqrDist) )
            if nearNearestPnt: # found part in threshold
                milestone.partIdx = nearPartIdx
                nearPart = self.parts[nearPartIdx]
                milestone.partMeasure = measureAlongPolyline( nearPart.polyline, nearSegment, nearNearestPnt )

                # debug
                geo = QgsGeometry.fromPoint( nearNearestPnt )
                self.errors.append( LrsError( LrsError.FORK, geo, routeId = 111, measure = milestone.partMeasure  ) )
                 

    def getErrors(self):
        return self.errors 

