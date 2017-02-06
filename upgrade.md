## LRS Plugin Upgrade 2017

### Foreword

The LRS Plugin was originally written in 2013 when QGIS internal geometry data structure was limited to x,y coordinates and it was not supporting so called measure (M) coordinate, which is common way to store linear reference data directly in geometry without additional tables. That is why current implementation (2/2017) of the plugin does not support such layers as input and output. It can only write directly to PostGIS. The QGIS geometry classes were refactored in the mean time, which makes it possible to use QGIS layers with measure both for input and output.
 
The current implementation is strongly targeted to maintenance and error detection of data based on routes and milestones, which was the most important feature for plugin funder, [Provincia Autonoma di Trento - Dipartimento infrastrutture e mobilità](http://www.provincia.tn.it/). There are however other users, who do not need calibration at all or who need to use different method for the calibration, based on attribute data describing segment measures.
 
The main idea of plugin upgrade is to separate tools for calibration and tools for usage. Standard QGIS layers will be used as an intermediate format. Calibrated data will be created as a memory layer, which may be exported by standard 'Save as' tool as Shapefile or PostGIS or any other format supporting measure which is supported by QGIS. The same applies to input for other tools. Any layer with measure supported by QGIS will be available as input for events generation, localization or event measure calculation.

Last but not least, the plugin has to be upgraded to the comming QGIS 3, which is using new Qt and Python version and which has different QGIS API. The upgraded plugin will be available for QGIS 3. QGIS 2.x versions will not be supported.

### Terminology
* LRS layer - layer with measures (with M coordinates)
* Milestone - point with route and measure attributes

### Description of tools and UI widgets

1. **Tools for use of an existing LRS layer.**
    * Common widgets - for tools 1.i.-1.iii.
        * Input widgets (common)
            * LRS layer (combo box)
            * LRS layer route field (combo box)     
    1. Locate an event (zoom) - localize single event in the map
        * Input widgets
            * Route (combo box)
            * Measure (float)
            * Highlight (check box)
            * Zoom buffer (float)
        * Actions
            * Center (button)
            * Zoom (button)
    2. Create events (create new layer) - generates output layer (points or lines) from input LRS layer and events table
        * Input widgets
            * Event table (combo box)
            * Event route field (combo box)
            * Event start measure field (combo box)
            * Event end measure field (combo box)
        * Output widgets 
            * Output layer name (text)
            * Output error field (text) - optional field where errors are written if an event cannot be created
    3. Calculate measures create/update table
        * Input widgets
            * Layer with points (combo box)
            * Max distance (float)
        * Output widgets
            * Output layer name (text)
            * Output route field (float)
            * Output measure field (float)
2. **Tools for creation/calibration of a new LRS layer.**
    * Common widgets - for all calibration types
        * Input widgets
            * Calibration type (combo box or radio button) - selection from the following 3 types 2.i.-2.iii.
            * Lines layer (combo box)
        * Output widgets
            * Output layer (text) - output LRS memory layer
        * Result widgets
            * Errors (table)
                * Actions
                    Zoom (button)
                    Create error layers (button)
                    Create quality layers (button)
            * Statistics (text) - calibration summary
    1. Calibrate from lines + milestones
        * Input widgets
            * Lines route field (combo box)
            * Point layer (combo box)
            * Points route field (combo box)
            * Points measure field (combo box)          
            * Points measure unit (combo box)
            * Routes inclusion exclusion (combo box, text, dialog)
            * Max point distance (float)
            * Parallels mode (combo)
            * Extrapolate (checkbox)        
    2. Generate from lines with start / (end) attributes
        * Input widgets
            * Event start measure field (combo box)
            * Event end measure field (combo box)              
    3. Generate from simple lines assuming that start is 0 and geometry length corresponds to real length
            