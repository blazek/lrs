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

# Chain of connected geometries

class LrsRoutePart:

    def __init__(self, polyline, routeId):
        #debug ('init route part' )
        self.polyline = polyline
        self.routeId = routeId
        self.milestones = [] # LrsMilestone list, all input milestones
        self.table = [] # sorted reference table 
        self.errors = [] # LrsError list

    def calibrate(self):
        polylineGeo = QgsGeometry.fromPolyline( self.polyline ) 

        if len ( self.milestones ) < 2:
            self.errors.append( LrsError( LrsError.NOT_ENOUGH_MILESTONES, polylineGeo, routeId = self.routeId ))
            return

        # create list of milestones sorted by partMeasure
        milestones = list ( self.milestones )
        # sort by partMeasure and measure
        milestones.sort ( key=lambda milestone: ( milestone.partMeasure, milestone.measure) )

        # check direction
        up = down = 0
        for i in range( len(milestones)-1 ):
            if milestones[i].measure == milestones[i+1].measure:
                # Could also be reported as error, but should not harm
                pass
            elif milestones[i].measure < milestones[i+1].measure:
                up += 1
            else:
                down += 1

        if up == down:
            self.errors.append( LrsError( LrsError.DIRECTION_GUESS, polylineGeo, routeId = self.routeId ))
            return
        elif down > up: # revert
            self.polyline.reverse()
            milestones.reverse()
            # recalc partMeasures
            length = geo.length()
            for milestone in milestones:
                milestone.partMeasure = length - milestone.partMeasure

        # remove milestones in wrong direction, to do it well is not trivial because
        # sequence of milestones in correct order may appear in wrong place, e.g.7,8,3,4
        # 1) find longest sequence in correct order
        # 2) delete wrong milestones before and after
        longestSeq = set()
        seq = set()
        for i in range(len(milestones)-1):
            if milestones[i].measure < milestones[i+1].measure:
                seq.add ( milestones[i] )
                seq.add ( milestones[i+1] )
                if len( seq ) > len(longestSeq):
                    longestSeq = seq
            else:
                # previous sequence interrupted
                seq = set()
         
        while True:
            done = True
            for i in range(len(milestones)-1):
                m1 = milestones[i]
                m2 = milestones[i+1]
                if m1 in longestSeq and m2 in longestSeq:
                    # both already in sequence
                    continue

                if not ( m1 in longestSeq or m2 in longestSeq ):
                    # not around sequence
                    continue

                if m1.measure < m2.measure: # correct order, add to sequence
                    if m1 in longestSeq:
                        longestSeq.add ( m2 )
                    else:
                        longestSeq.add ( m1 )
                else: # wrong order, delete
                    idx = i if m2 in longestSeq else i+1
                    m = milestones[idx]
                    geo = QgsGeometry.fromPoint( m.pnt )
                    self.errors.append( LrsError( LrsError.WRONG_MEASURE, geo, routeId = self.routeId, measure = m.measure ))
                    del  milestones[idx]
                done = False
                break

            if done: break
                            

    def getErrors(self):
        return self.errors

