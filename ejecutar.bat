@echo off
REM Corre el ciclo completo: descarga de CrossChex, analisis y reporte en localhost.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 control_fichajes.py todo) || (python control_fichajes.py todo)
