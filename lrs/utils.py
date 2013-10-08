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
import math
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *

# print debug message
def debug(msg):
    print "LRS: %s" % msg

# test if two QgsPolyline are identical including reverse order
# return False - not identical
#        True - identical
def polylinesIdentical( polyline1, polyline2 ):
    if polyline1 == polyline2: 
        return True
    
    tmp = []
    tmp.extend(polyline2)
    tmp.reverse()
    return polyline1 == tmp

# return hash of QgsPoint (may be used as key in dictionary)
def pointHash( point ):
    return "%s-%s" % ( point.x().__hash__(), point.y().__hash__() )

def pointsDistance( p1, p2 ):
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    return math.sqrt( dx*dx + dy*dy)

def segmentLength( polyline, segment ):
    p1 = polyline[segment]
    p2 = polyline[segment+1]
    return pointsDistance( p1, p2 )

# calculate distance along line to pnt
def measureAlongPolyline( polyline, segment, pnt ):
    measure = 0.0
    for i in range(segment):
        measure += segmentLength( polyline, i )
    
    measure += pointsDistance( polyline[segment], pnt )
    return measure
