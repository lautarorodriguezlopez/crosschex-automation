# Control de fichajes (CrossChex)

Este proyecto baja los fichajes de **CrossChex** y los guarda en una carpeta local. Después detecta anomalías y abre un reporte HTML en `http://localhost:8765`. Una tarea programada lo corre solo todos los días.

Solo necesita **Python 3.10 o más nuevo**: usa la biblioteca estándar y no hay que instalar nada con pip.

```
CrossChex Cloud (API) ─┐
                       ├─► data/fichajes.csv ─► reglas de anomalías ─► reportes/index.html ─► localhost:8765
Export CSV (Standard) ─┘     data/crudo/*.json (copia de cada descarga, para auditoría)
```

## 1. Probalo sin credenciales

```bash
python control_fichajes.py demo
```

Genera 4 semanas de fichajes ficticios de un local gastronómico, con turnos nocturnos y anomalías ya cargadas, y abre el reporte en el navegador.

## 2. Conectalo a CrossChex

**CrossChex Cloud (con API).**
1. Pedile a Anviz que active el *developer mode* de la cuenta. Sin eso no aparecen las claves de API.
2. Copiá `config.example.json` como `config.json` y completá `api_key`, `api_secret` y `base_url`. La `base_url` depende de la región de la cuenta, por ejemplo `https://api.us.crosschexcloud.com/` o `https://api.ap.crosschexcloud.com/`.
3. Corré `python control_fichajes.py descargar --dias 7` para probar la conexión.

**CrossChex Standard (programa de escritorio, sin API).**
1. En CrossChex, exportá los registros de asistencia a CSV.
2. En `config.json`, ajustá `columnas_csv` para que coincida con los encabezados de tu exportación.
3. Corré `python control_fichajes.py importar ruta/al/export.csv`.

## 3. Cargá los turnos

Las reglas de llegada tarde, salida anticipada, ausencias y días francos solo funcionan con los turnos cargados. Los turnos van en `horarios.empleados` de `config.json`, usando como clave el **legajo (workno)** de CrossChex:

```json
"205": { "nombre": "Carla", "turnos": { "vie": ["20:00", "03:00"], "sab": ["20:00", "03:00"] } }
```

- Días: `lun mar mie jue vie sab dom`. Un día que no figura es franco.
- Un turno que termina después de la medianoche, como `20:00–03:00`, se toma bien.
- `horarios.por_defecto` aplica un mismo esquema de turnos a quienes no tengan uno propio.
- `feriados` es una lista de fechas `AAAA-MM-DD` donde no se marcan ausencias.

Sin turnos cargados igual se detectan las anomalías que no dependen del horario.

## 4. Programalo

- **Windows:** ejecutá `programar_tarea_windows.bat 06:00`. Crea la tarea "Control de fichajes", que corre `ejecutar.bat` todos los días.
- **Linux o Mac:** agregá a `crontab -e` la línea `0 6 * * * /ruta/control-fichajes/ejecutar.sh`.

Conviene programarlo **después de la hora de corte** (05:00 por defecto) para que el turno noche anterior ya esté cerrado. Cada corrida baja los últimos 3 días: así recupera lo que falte si la PC estuvo apagada, y los duplicados se descartan solos. El servidor queda abierto 120 minutos y después se cierra. Todo queda registrado en `logs/ejecuciones.log`.

## Anomalías que detecta

| Regla | Severidad | Necesita turnos | Configurable en `reglas` |
|---|---|---|---|
| Falta entrada o salida (número impar de fichajes) | alta | no | — |
| Ausencia: tenía turno y no fichó | alta | sí | — |
| Llegada tarde | media | sí | `tolerancia_minutos` |
| Salida anticipada | media | sí | `tolerancia_minutos` |
| Jornada excesiva | media | no | `jornada_maxima_horas` |
| Fichaje duplicado (dos marcas seguidas) | baja | no | `minutos_duplicado` |
| Jornada muy corta | baja | no | `jornada_minima_horas` |
| Pausa larga entre pares de fichajes | baja | no | `pausa_maxima_minutos` |
| Fichó en día franco | baja | sí | — |

La **jornada** se define con `hora_corte_jornada`: con 05:00, un fichaje a las 02:30 del sábado cuenta como parte de la jornada del viernes.

## El reporte

Está pensado como una bandeja de revisión por excepción, como las de los sistemas de control horario profesionales: solo se mira lo que falló, de lo más grave a lo menos grave.

- **Indicadores:** porcentaje de jornadas sin anomalías, cantidad por severidad, personal y horas trabajadas.
- **Anomalías por jornada:** barras apiladas por severidad. Tocar una barra filtra la bandeja por ese día.
- **Por tipo:** ranking de tipos de anomalía. Tocar uno filtra la bandeja.
- **Mapa de asistencia:** empleados por días, con la peor severidad de cada jornada. Sirve para ver patrones, como alguien que llega tarde todos los viernes.
- **Bandeja de revisión:** filtros por severidad, empleado y texto. Cada anomalía se puede marcar como "revisada"; la marca queda guardada en ese navegador.
- **Detalle de la jornada:** al tocar una fila o una celda se abre un panel con la línea de tiempo del turno programado contra el tiempo trabajado. El fichaje sin par aparece en rojo.

La severidad siempre se muestra con ícono y texto, no solo con color. El reporte tiene modo claro y oscuro (botón arriba a la derecha) y se adapta al celular. Usa la tipografía Inter, incrustada en el archivo para que funcione sin internet; su licencia SIL OFL está en `fichajes/assets/`.

## Comandos

```
python control_fichajes.py todo        # descargar + analizar + abrir reporte (lo que corre la tarea)
python control_fichajes.py descargar   # --dias N | --desde AAAA-MM-DD --hasta AAAA-MM-DD
python control_fichajes.py importar archivo.csv
python control_fichajes.py analizar    # --dias N
python control_fichajes.py servir
python control_fichajes.py demo
```

`todo` y `demo` aceptan `--sin-servidor` (solo genera el HTML) y `--no-abrir`.

## Privacidad

`config.json`, `data/`, `reportes/` y `logs/` están en `.gitignore`. Las credenciales y los fichajes del personal no salen de la computadora, y el servidor escucha solo en `127.0.0.1`.
