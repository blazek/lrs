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
from part import *
from error import *
from point import *
from milestone import *

# LrsRoute keeps list of LrsLine 

class LrsRoute:

    def __init__(self, layer, routeId, threshold, mapUnitsPerMeasureUnit):
        #debug ('init route %s' % routeId )
        self.layer = layer
        self.routeId = routeId # if None, keeps all lines and points without routeId
        self.threshold = threshold
        self.mapUnitsPerMeasureUnit = mapUnitsPerMeasureUnit
        self.lines = [] # LrsLine list, may be empty 
        self.points = [] # LrsPoint list, may be empty

        self.parts = [] # LrsRoutePart list
        self.milestones = [] # LrsMilestone list 
        self.errors = [] # LrsError list of route errors
        # cached all errors, route itself and parts
        self.allErrors_ = [] 

    def addLine( self, line ):
        self.lines.append( line )

    # returns: { removedErrorChecksums:[], updatedErrors:[], addedErrors[] }
    def calibrate(self):

        self.parts = []
        self.milestones = []
        self.errors = []
        self.allErrors_ = []

        if self.routeId == None: # special case 
            for line in self.lines:
                if not line.geo: continue
                origin = LrsOrigin( QGis.Line, line.fid )
                self.errors.append( LrsError( LrsError.NO_ROUTE_ID, line.geo, origins = [ origin ] ) )  

            for point in self.points:
                if not point.geo: continue
                origin = LrsOrigin( QGis.Point, point.fid )
                self.errors.append( LrsError( LrsError.NO_ROUTE_ID, point.geo, origins = [ origin ] ) )  

                # in addition it may be without measure
                if point.measure == None:
                    origin = LrsOrigin( QGis.Point, point.fid )
                    self.errors.append( LrsError( LrsError.NO_MEASURE, point.geo, origins = [ origin ] ) )

        elif len( self.lines ) == 0: # no lines -> orphan points
            for point in self.points:
                if not point.geo: continue
                origin = LrsOrigin( QGis.Point, point.fid )
                self.errors.append( LrsError( LrsError.ORPHAN, point.geo, routeId = self.routeId, measure = point.measure, origins = [ origin ] ) )

                # in addition it may be without measure
                if point.measure == None:
                    origin = LrsOrigin( QGis.Point, point.fid )
                    self.errors.append( LrsError( LrsError.NO_MEASURE, point.geo, routeId = self.routeId, origins = [ origin ] ) )

        else:
            self.buildParts()
            self.createMilestones()
            self.attachMilestones()
            self.calibrateParts()
            self.checkPartOverlaps()

    def calibrateAndGetUpdates(self):
        oldErrorChecksums = list( e.getChecksum() for e in self.getErrors() )
        oldQualityChecksums = list( e.getChecksum() for e in self.getQualityFeatures() )

        self.calibrate()

        newErrors = self.getErrors() 
        newErrorChecksums = list( e.getChecksum() for e in newErrors )
        addedErrors = []
        updatedErrors = []
        removedErrorChecksums = []
        for checksum in oldErrorChecksums:
            if not checksum in newErrorChecksums:
                #debug ( 'removed error' )
                removedErrorChecksums.append( checksum )
        for error in newErrors:
            if error.getChecksum() in oldErrorChecksums:
                #debug ( 'updated error' )
                updatedErrors.append ( error )
            else:
                #debug ( 'added error' )
                addedErrors.append ( error )

        # simple remove and add for quality
        newQualityFeatures = self.getQualityFeatures() 
        newQualityChecksums = list ( f.getChecksum() for f in newQualityFeatures )
        addedQualityFeatures = []
        removedQualityChecksums = []
        for checksum in oldQualityChecksums:
            if not checksum in newQualityChecksums:
                removedQualityChecksums.append( checksum )
        for feature in newQualityFeatures:
            if not feature.getChecksum() in oldQualityChecksums:
                addedQualityFeatures.append( feature )

        return { 'removedErrorChecksums': removedErrorChecksums,
                 'updatedErrors': updatedErrors,
                 'addedErrors': addedErrors,
                 'removedQualityChecksums': removedQualityChecksums,
                 'addedQualityFeatures': addedQualityFeatures }
 
    # create LrsRoutePart from eometryParts
    def buildParts(self):
        self.parts = []
        polylines = [] # list of { polyline:, fid:, geoPart:, nGeoParts: }
        for line in self.lines:
            if not line.geo: continue
            # QGis::singleType and flatType are not in bindings (2.0)
            polys = None # list of QgsPolyline
            if line.geo.wkbType() in [ QGis.WKBLineString, QGis.WKBLineString25D]:
                #polylines.append( line.geo.asPolyline() )
                polys = [ line.geo.asPolyline() ]
            else: # multiline
                #polylines.extend ( line.geo.asMultiPolyline() )
                polys = line.geo.asMultiPolyline()

            for i in range(len(polys)):
                polylines.append( { 
                    'polyline': polys[i],
                    'fid': line.fid,
                    'geoPart': i,
                    'nGeoParts': len(polys),
                })

        ##### check for duplicates
        duplicates = set()
        for i in range(len(polylines)-1):
            for j in range(i+1,len(polylines)):
                if polylinesIdentical( polylines[i]['polyline'], polylines[j]['polyline'] ):
                    #debug( 'identical polylines %d and %d' % (i, j) )
                    duplicates.add(j)
        # make reverse ordered unique list of duplicates and delete
        duplicates = list( duplicates )
        duplicates.sort(reverse=True)
        for d in duplicates: # delete going down (sorted reverse)
            geo = QgsGeometry.fromPolyline( polylines[d]['polyline'] )
            origin = LrsOrigin( QGis.Line, polylines[d]['fid'], polylines[d]['geoPart'], polylines[d]['nGeoParts'] )
            self.errors.append( LrsError( LrsError.DUPLICATE_LINE, geo, routeId = self.routeId, origins = [ origin ] ) )
            del  polylines[d]
             
        ###### find forks
        nodes = {} 
        for poly in polylines:
            polyline = poly['polyline']
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
                # origins sould not be necessary
                self.errors.append( LrsError( LrsError.FORK, geo, routeId = self.routeId ) )    

        ###### join polylines to parts
        while len( polylines ) > 0:
            #polyline = polylines.pop(0)
            poly = polylines.pop(0)
            polyline = poly['polyline']
            origin = LrsOrigin( QGis.Line, poly['fid'], poly['geoPart'], poly['nGeoParts'] )
            origins = [ origin ]
            while True: # connect parts
                connected = False
                for i in range(len( polylines )):
                    #polyline2 = polylines[i]
                    poly2 = polylines[i]
                    polyline2 = poly2['polyline']

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
                        origin = LrsOrigin( QGis.Line, polylines[i]['fid'], polylines[i]['geoPart'], polylines[i]['nGeoParts'] )
                        origins.append( origin )
                        del polylines[i]
                        break

                if not connected: # no more parts can be connected
                    break

            self.parts.append( LrsRoutePart( polyline, self.routeId, origins) )

    def addPoint( self, point ):
       self.points.append ( point )

    def removePoint( self, fid ):
        for i in range ( len(self.points) ): 
            if self.points[i].fid == fid:
                del self.points[i]
                return

    def removeLine( self, fid ):
        for i in range ( len(self.lines) ): 
            if self.lines[i].fid == fid:
                del self.lines[i]
                return

    def createMilestones(self):
        self.milestones = []

        # check duplicates
        # TODO: maybe allow duplicates? Could be end/start of discontinuous segments
        nodes = {} 
        for point in self.points:
            if not point.geo: continue

            if point.measure == None:
                origin = LrsOrigin( QGis.Point, point.fid )
                self.errors.append( LrsError( LrsError.NO_MEASURE, point.geo, routeId = self.routeId, origins = [ origin ] ) )
                continue

            pts = []
            if point.geo.wkbType() in [ QGis.WKBPoint, QGis.WKBPoint25D]:
                pts = [ point.geo.asPoint() ]
            else: # multi (makes little sense)
                pts = point.geo.asMultiPoint()

            pnts = [] # list of { point:, geoPart: }
            for i in range(len(pts)):
                pnts.append( { 'point': pts[i], 'geoPart': i, 'nGeoParts': len(pts) } )

            for p in pnts:
                pnt = p['point']
                ph = pointHash( pnt )

                origin = LrsOrigin( QGis.Point, point.fid, p['geoPart'], p['nGeoParts'] )
        
                if not nodes.has_key( ph ):
                    nodes[ ph ] = { 
                        'pnt': pnt, 
                        'npoints': 1, 
                        'measures': [ point.measure ], 
                        #'fids': [ point.fid ],
                        #'geoPart': [ p['geoPart'] ],
                        'origins': [ origin ] 
                    }
                else:
                    nodes[ ph ]['npoints'] += 1 
                    nodes[ ph ]['measures'].append( point.measure )
                    #nodes[ ph ]['fids'].append( point.fid )
                    #nodes[ ph ]['geoPart'].append( ['geoPart'] )
                    nodes[ ph ]['origins'].append( origin )

        for node in nodes.values():
            print "npoints = %s" % node['npoints']
            if node['npoints'] > 1:
                geo = QgsGeometry.fromPoint( node['pnt'] )
                self.errors.append( LrsError( LrsError.DUPLICATE_POINT, geo, routeId = self.routeId, measure = node['measures'], origins = node['origins'] ) )    
    
            measure = node['measures'][0] # first if duplicates, for now
            self.milestones.append ( LrsMilestone( node['origins'][0].fid, node['origins'][0].geoPart, node['origins'][0].nGeoParts, node['pnt'], measure ) )

    # calculate measures along parts
    def attachMilestones(self):
        if not self.routeId: return 

        sqrThreshold = self.threshold * self.threshold
        for milestone in self.milestones:
            pointGeo = QgsGeometry.fromPoint( milestone.pnt )

            nearSqDist = sys.float_info.max
            nearPartIdx = None
            nearSegment = None
            nearNearestPnt = None 
            for i in range( len(self.parts) ):
                part = self.parts[i]
                partGeo = QgsGeometry.fromPolyline( part.polyline )

                ( sqDist, nearestPnt, afterVertex ) = partGeo.closestSegmentWithContext( milestone.pnt )
                segment = afterVertex-1
                #debug ('sqDist %s x %s' % (sqDist, sqrThreshold) )
                if sqDist <= sqrThreshold and sqDist < nearSqDist:
                    nearSqDist = sqDist
                    nearPartIdx = i
                    nearSegment = segment
                    nearNearestPnt = nearestPnt

            #debug ('nearest partIdx = %s segment = %s sqDist = %s' % ( nearPartIdx, nearSegment, nearSqDist) )
            if nearNearestPnt: # found part in threshold
                milestone.partIdx = nearPartIdx
                nearPart = self.parts[nearPartIdx]
                milestone.partMeasure = measureAlongPolyline( nearPart.polyline, nearSegment, nearNearestPnt )

                nearPart.milestones.append( milestone )
            else:   
                origin = LrsOrigin( QGis.Point, milestone.fid, milestone.geoPart, milestone.nGeoParts )
                self.errors.append( LrsError( LrsError.OUTSIDE_THRESHOLD, pointGeo, routeId = self.routeId, measure = milestone.measure, origins = [ origin ] ) )    
                 
    def calibrateParts(self):
        for part in self.parts:
            part.calibrate()

    def checkPartOverlaps(self):
        records = []
        overlaps = set()
        recordParts = {}
        for part in self.parts:
            for record in part.getRecords():
                records.append( record )
                recordParts[record] = part
        for record in records:
            for record2 in records:
                if record2 is record: continue
                if record.measureOverlaps( record2 ):
                    overlaps.add( record )

        #debug("overlaps: %s" % overlaps )
        for record in overlaps:
            part = recordParts[record]
            geo = part.getRecordGeometry(record)
            self.errors.append( LrsError( LrsError.DUPLICATE_REFERENCING, geo, routeId = self.routeId, measure = [ record.milestoneFrom, record.milestoneTo ] ) )
            part.removeRecord(record)

    def getErrors(self):
        if not self.allErrors_:
            self.allErrors_ = list ( self.errors )
            for part in self.parts:
                self.allErrors_.extend( part.getErrors() )
        return self.allErrors_
        
    def getSegments(self):
        segments = []
        for part in self.parts:
            segments.extend( part.getSegments() )
        return segments

    def getQualityFeatures(self):
        features = [] 
        fields = LrsQualityFields()
        for segment in self.getSegments():
            m_len = self.mapUnitsPerMeasureUnit * (segment.record.milestoneTo - segment.record.milestoneFrom)
            length = segment.geo.length()
            err_abs = m_len - length
            err_rel = err_abs / length if length > 0 else 0
            feature = LrsQualityFeature()
            feature.setGeometry( segment.geo )
            feature.setAttribute( 'route', '%s' % segment.routeId )
            feature.setAttribute( 'm_from', segment.record.milestoneFrom )
            feature.setAttribute( 'm_to', segment.record.milestoneTo )
            feature.setAttribute( 'm_len', m_len )
            feature.setAttribute( 'len', length )
            feature.setAttribute( 'err_abs', err_abs )
            feature.setAttribute( 'err_rel', err_rel )
            feature.setAttribute( 'err_perc', err_rel * 100 )
            features.append( feature )

        return features
