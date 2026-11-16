@echo off
REM Crea una tarea programada de Windows que corre ejecutar.bat todos los dias a la hora indicada.
REM Uso: programar_tarea_windows.bat 06:00
set HORA=%1
if "%HORA%"=="" set HORA=06:00
schtasks /Create /F /SC DAILY /ST %HORA% /TN "Control de fichajes" /TR "\"%~dp0ejecutar.bat\""
echo.
echo Listo. Para probarla ahora:   schtasks /Run /TN "Control de fichajes"
echo Para borrarla:                schtasks /Delete /TN "Control de fichajes" /F
pause
