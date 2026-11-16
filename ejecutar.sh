#!/usr/bin/env bash
# Corre el ciclo completo: descarga de CrossChex, análisis y reporte en localhost.
# Para programarlo todos los días a las 06:00 con cron (crontab -e):
#   0 6 * * * DISPLAY=:0 /ruta/a/control-fichajes/ejecutar.sh
cd "$(dirname "$0")" && exec python3 control_fichajes.py todo
