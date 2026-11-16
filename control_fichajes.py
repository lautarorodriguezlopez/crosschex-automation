#!/usr/bin/env python3
"""Control de fichajes: descarga de CrossChex -> carpeta local -> anomalías -> reporte en localhost.

Uso rápido:
  python control_fichajes.py demo                 # prueba con datos ficticios, sin credenciales
  python control_fichajes.py todo                 # lo que corre la tarea programada
  python control_fichajes.py descargar --dias 7   # solo bajar fichajes de la API
  python control_fichajes.py importar export.csv  # cargar un CSV exportado de CrossChex Standard
  python control_fichajes.py analizar --dias 31   # solo regenerar el reporte
  python control_fichajes.py servir               # solo abrir el último reporte
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Se necesita Python 3.10 o más nuevo.")

# En la consola de Windows (cp1252) un carácter raro no debe cortar la tarea programada
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from fichajes import almacen, anomalias, demo, reporte, servidor
from fichajes.crosschex import CrossChexClient, CrossChexError, normalizar_api

RAIZ = Path(__file__).resolve().parent

POR_DEFECTO = {
    "crosschex": {"base_url": "https://api.us.crosschexcloud.com/", "api_key": "", "api_secret": ""},
    "zona_horaria": "-03:00",
    "dias_descarga": 3,
    "dias_analisis": 31,
    "incluir_hoy": False,
    "carpeta_datos": "data",
    "carpeta_reportes": "reportes",
    "servidor": {"puerto": 8765, "minutos_abierto": 120, "abrir_navegador": True},
    "reglas": {
        "hora_corte_jornada": "05:00",
        "minutos_duplicado": 3,
        "tolerancia_minutos": 10,
        "jornada_maxima_horas": 12,
        "jornada_minima_horas": 2,
        "pausa_maxima_minutos": 90,
    },
    "feriados": [],
    "horarios": {"por_defecto": None, "empleados": {}},
    "columnas_csv": {
        "legajo": "No.", "nombre": "Nombre", "fecha_hora": "Fecha/Hora",
        "tipo": "Estado", "dispositivo": "Dispositivo",
    },
}


def _fusionar(base: dict, extra: dict) -> dict:
    salida = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            salida[k] = _fusionar(base[k], v)
        else:
            salida[k] = v
    return salida


def cargar_config(ruta: Path) -> dict:
    if not ruta.exists():
        return dict(POR_DEFECTO)
    with ruta.open(encoding="utf-8") as f:
        return _fusionar(POR_DEFECTO, json.load(f))


def configurar_log(carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[
            logging.FileHandler(carpeta / "ejecuciones.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ---- pasos -----------------------------------------------------------------
def paso_descargar(cfg: dict, alm: almacen.Almacen, dias: int, desde: str | None, hasta: str | None) -> int:
    zona = anomalias._zona(cfg["zona_horaria"])
    fin = datetime.fromisoformat(hasta).replace(tzinfo=zona) if hasta else datetime.now(zona)
    ini = datetime.fromisoformat(desde).replace(tzinfo=zona) if desde else fin - timedelta(days=dias)
    cx = cfg["crosschex"]
    cliente = CrossChexClient(cx["base_url"], cx["api_key"], cx["api_secret"])
    logging.info("Descargando fichajes de CrossChex entre %s y %s…", ini.isoformat(), fin.isoformat())
    crudos = cliente.registros(ini, fin)
    alm.guardar_crudo(crudos, "api")
    nuevos = alm.agregar([normalizar_api(r) for r in crudos])
    logging.info("Recibidos %d fichajes; %d nuevos guardados en %s", len(crudos), nuevos, alm.base)
    return nuevos


def paso_analizar(cfg: dict, alm: almacen.Almacen, dias: int, fuente: str) -> Path:
    analizador = anomalias.Analizador(cfg)
    zona = analizador.zona
    ahora = datetime.now(zona).replace(tzinfo=None)
    hasta = analizador.jornada_de(ahora)
    if not cfg.get("incluir_hoy"):
        hasta -= timedelta(days=1)  # la jornada en curso todavía no terminó
    desde = hasta - timedelta(days=dias - 1)
    resultado = analizador.analizar(alm.leer(), desde, hasta)
    periodo = f"Jornadas del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
    ruta = reporte.generar(resultado, RAIZ / cfg["carpeta_reportes"], periodo, fuente,
                           len(analizador.no_parseados), (desde.isoformat(), hasta.isoformat()),
                           cfg["reglas"]["hora_corte_jornada"])
    altas = sum(1 for a in resultado["anomalias"] if a["severidad"] == "alta")
    logging.info("Reporte: %s · %d anomalías (%d de severidad alta)", ruta.name,
                 len(resultado["anomalias"]), altas)
    if analizador.no_parseados:
        logging.warning("%d fichajes con fecha ilegible; revisá 'formatos_fecha' en config.json",
                        len(analizador.no_parseados))
    return ruta


def paso_servir(cfg: dict, carpeta: Path, abrir: bool = True) -> None:
    s = cfg["servidor"]
    servidor.servir(carpeta, s["puerto"], s["minutos_abierto"], abrir and s["abrir_navegador"])


# ---- CLI -------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Control de fichajes con CrossChex")
    p.add_argument("--config", default=str(RAIZ / "config.json"))
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("descargar", help="Bajar fichajes de CrossChex Cloud")
    d.add_argument("--dias", type=int)
    d.add_argument("--desde", help="AAAA-MM-DD")
    d.add_argument("--hasta", help="AAAA-MM-DD")

    i = sub.add_parser("importar", help="Cargar un CSV exportado de CrossChex")
    i.add_argument("archivo")

    a = sub.add_parser("analizar", help="Detectar anomalías y generar el reporte")
    a.add_argument("--dias", type=int)

    sub.add_parser("servir", help="Abrir el último reporte en localhost")

    for nombre in ("todo", "demo"):
        t = sub.add_parser(nombre)
        t.add_argument("--sin-servidor", action="store_true", help="Solo generar el reporte")
        t.add_argument("--no-abrir", action="store_true", help="No abrir el navegador")

    args = p.parse_args(argv)
    cfg = cargar_config(Path(args.config))
    configurar_log(RAIZ / "logs")

    if args.cmd == "demo":
        cfg = _fusionar(cfg, demo.config_demo())
        cfg["carpeta_datos"], cfg["carpeta_reportes"] = "demo/data", "demo/reportes"
        alm = almacen.Almacen(RAIZ / cfg["carpeta_datos"])
        hoy = datetime.now(anomalias._zona(cfg["zona_horaria"])).date()
        registros = demo.generar(hoy - timedelta(days=1), dias=28)
        alm.guardar_crudo(registros, "demo")
        alm.agregar(registros)
        paso_analizar(cfg, alm, 28, "datos de demostración")
        if not args.sin_servidor:
            paso_servir(cfg, RAIZ / cfg["carpeta_reportes"], not args.no_abrir)
        return 0

    alm = almacen.Almacen(RAIZ / cfg["carpeta_datos"])
    try:
        if args.cmd == "descargar":
            paso_descargar(cfg, alm, args.dias or cfg["dias_descarga"], args.desde, args.hasta)
        elif args.cmd == "importar":
            filas = almacen.importar_csv(Path(args.archivo), cfg["columnas_csv"])
            alm.guardar_crudo(filas, "csv")
            n = alm.agregar(filas)
            logging.info("Importados %d fichajes nuevos desde %s", n, args.archivo)
        elif args.cmd == "analizar":
            paso_analizar(cfg, alm, args.dias or cfg["dias_analisis"], "base local")
            paso_servir(cfg, RAIZ / cfg["carpeta_reportes"])
        elif args.cmd == "servir":
            paso_servir(cfg, RAIZ / cfg["carpeta_reportes"])
        elif args.cmd == "todo":
            try:
                paso_descargar(cfg, alm, cfg["dias_descarga"], None, None)
                fuente = "CrossChex Cloud"
            except CrossChexError as e:
                logging.error("No se pudo descargar (%s). Analizo con lo que ya hay guardado.", e)
                fuente = "base local (la descarga falló, ver logs)"
            paso_analizar(cfg, alm, cfg["dias_analisis"], fuente)
            if not args.sin_servidor:
                paso_servir(cfg, RAIZ / cfg["carpeta_reportes"], not args.no_abrir)
    except CrossChexError as e:
        logging.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
