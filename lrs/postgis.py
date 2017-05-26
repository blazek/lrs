# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LrsDockWidget
                                 A QGIS plugin
 Linear reference system builder and editor
                             -------------------
        begin                : 2017-5-20
        copyright            : (C) 2017 by Radim Blažek
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

from .utils import *

# Export lrs to Postgis - planned to be removed
class ExportPostgis(QObject):
    def __init__(self, iface, lrs, progressBar):
        # debug( "ExportPostgis.__init__")
        self.iface = iface
        self.lrs = lrs  # Lrs object
        self.progressBar = progressBar

    def export(self, connectionName, outputSchema, outputTable):
        conn = self.openPostgisConnection(connectionName)
        # debug('conn: %s' % conn )
        if not conn: return

        try:
            tables = [r[0] for r in self.postgisSelect(conn,
                                                       "SELECT table_name FROM information_schema.tables where table_schema = '%s'" % outputSchema)]
            # debug('tables: %s' % tables)

            if outputTable in tables:
                answer = QMessageBox.question(self, 'Table exists',
                                              "Table '%s' already exists in schema '%s'. Overwrite?" % (
                                                  outputTable, outputSchema), QMessageBox.Yes | QMessageBox.Abort)
                if answer == QMessageBox.Abort:
                    return
                else:
                    sql = "drop table %s.%s" % (outputSchema, outputTable)
                    self.postgisExecute(conn, sql)

            routeField = self.lrs.routeField
            routeFieldName = routeField.name().replace(" ", "_")
            routeFieldStr = "%s " % routeFieldName
            if routeField.type() == QVariant.String:
                routeFieldStr += "varchar(%s)" % routeField.length()
            elif routeField.type() == QVariant.Int:
                routeFieldStr += "int"
            elif routeField.type() == QVariant.Double:
                routeFieldStr += "double precision"
            else:
                routeFieldStr += "varchar(20)"

            sql = "create table %s.%s ( %s, m_from double precision, m_to double precision)" % (
                outputSchema, outputTable, routeFieldStr)
            self.postgisExecute(conn, sql)

            srid = -1
            authid = self.lrs.crs.authid()
            if authid.lower().startswith('epsg:'):
                srid = authid.split(':')[1]
            sql = "select AddGeometryColumn('%s', '%s', 'geom', %s, 'LINESTRINGM', 3)" % (
                outputSchema, outputTable, srid)
            self.postgisExecute(conn, sql)

            for part in self.lrs.getParts():
                if not part.records: continue
                wkt = part.getWktWithMeasures()
                if not wkt: continue

                if routeField.type() == QVariant.Int or routeField.type() == QVariant.Double:
                    routeVal = part.routeId
                else:
                    routeVal = "'%s'" % part.routeId

                sql = "insert into %s.%s ( %s, m_from, m_to, geom) values ( %s, %s, %s, ST_GeometryFromText('%s', %s))" % (
                    outputSchema, outputTable, routeFieldName, routeVal, part.milestoneMeasureFrom(),
                    part.milestoneMeasureTo(), wkt, srid)
                self.postgisExecute(conn, sql)

            conn.commit()
            conn.close()

        except Exception as e:
            conn.close()
            QMessageBox.critical(None, 'Error', '%s' % e)
            return

        QMessageBox.information(None, 'Information', 'Exported successfully')

    @staticmethod
    def getPostgisConnection(connectionName):
        settings = QSettings()
        key = '/PostgreSQL/connections'

        settings.beginGroup(u'/%s/%s' % (key, connectionName))

        if not settings.contains('database'): return None

        connection = {'name': connectionName}

        settingsList = ['service', 'host', 'port', 'database', 'username', 'password']
        service, host, port, database, username, password = map(lambda x: settings.value(x, '', type=str), settingsList)

        sslmode = settings.value("sslmode", QgsDataSourceURI.SSLprefer, type=int)

        uri = QgsDataSourceURI()
        if service:
            uri.setConnection(service, database, username, password, sslmode)
        else:
            uri.setConnection(host, port, database, username, password, sslmode)

        connection['uri'] = uri

        return connection

    @staticmethod
    def getPostgisConnections():
        settings = QSettings()
        connections = []
        key = '/PostgreSQL/connections'
        settings.beginGroup(key);
        for connectionName in settings.childGroups():
            connection = ExportPostgis.getPostgisConnection(connectionName)
            if connection:
                connections.append(connection)
        return connections

    # open connection asking credentials in cycle
    @staticmethod
    def openPostgisConnection(connectionName):
        connection = ExportPostgis.getPostgisConnection(connectionName)
        if not connection:  # should not happen
            QMessageBox.critical(None, 'Error', 'Connection not defined')
            return

        uri = connection['uri']

        username = uri.username()
        password = uri.password()
        while True:
            uri.setUsername(username)
            uri.setPassword(password)

            # debug('connection: %s' % uri.connectionInfo() )
            try:
                conn = psycopg2.connect(uri.connectionInfo().encode('utf-8'))
                # debug('connected ok' )
                return conn
            except Exception as e:
                # QMessageBox.critical( self, 'Error', 'Cannot connect: %s' % e )
                err = '%s' % e
                (ok, username, password) = QgsCredentials.instance().get(uri.connectionInfo(), username, password, err)
                # Put the credentials back (for yourself and the provider), as QGIS removes it when you "get" it
                if ok:
                    QgsCredentials.instance().put(uri.connectionInfo(), username, password)
                else:
                    return None

    def postgisExecute(self, conn, sql):
        # debug('sql: %s' % sql )
        cur = conn.cursor()
        cur.execute(sql)


    def postgisSelect(self, conn, sql):
        # debug('sql: %s' % sql )
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchall()