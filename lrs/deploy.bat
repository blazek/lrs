rem Emplacement des fichiers sources
set PLUGIN_SOURCE=%~dp0

rem Paramétrage de l'environnement d'exécution pour QGIS 3.10
@echo off
set OSGEO4W_ROOT=C:\Program Files\QGIS 3.10
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"
call "%OSGEO4W_ROOT%\bin\qt5_env.bat"
call "%OSGEO4W_ROOT%\bin\py3_env.bat"
@echo on

rem Compilation des interfaces QTDesigner pour QGIS 3.10
Call "C:\Program Files\QGIS 3.10\apps\Python37\Scripts\pyuic5.bat" ui\ui_lrsdockwidget.ui --from-imports -o ui\ui_lrsdockwidget.py

rem Compilation des ressources
rem -- Call "C:\Program Files\QGIS 3.10\apps\Python37\Scripts\pyrcc5.bat" -o resources_rc.py resources.qrc

rem Déploiement du plugin pour QGIS 3.10
set PLUGIN_DIR=C:\Users\%USERNAME%\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\lrs
rem xcopy /S /Y %PLUGIN_SOURCE%\*.* %PLUGIN_DIR%

xcopy /S /Y %PLUGIN_SOURCE%*.py %PLUGIN_DIR%\
xcopy /S /Y %PLUGIN_SOURCE%\i18n\*.qm %PLUGIN_DIR%\i18n\
xcopy /S /Y %PLUGIN_SOURCE%\help\*.* %PLUGIN_DIR%\help\

exit /B
