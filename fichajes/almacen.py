"""Almacenamiento local: guarda lo descargado en la carpeta data/ del proyecto.

- data/crudo/AAAA-MM-DD_HHMMSS.json  -> respuesta tal cual vino (auditoría)
- data/fichajes.csv                  -> base consolidada, sin duplicados
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

CAMPOS = ["legajo", "nombre", "fecha_hora", "tipo", "dispositivo"]


class Almacen:
    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta)
        self.crudo = self.carpeta / "crudo"
        self.crudo.mkdir(parents=True, exist_ok=True)
        self.base = self.carpeta / "fichajes.csv"

    def guardar_crudo(self, registros: list[dict], origen: str) -> Path:
        sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        ruta = self.crudo / f"{sello}_{origen}.json"
        ruta.write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
        return ruta

    def leer(self) -> list[dict]:
        if not self.base.exists():
            return []
        with self.base.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def agregar(self, nuevos: list[dict]) -> int:
        """Suma registros a la base consolidada. Devuelve cuántos eran nuevos."""
        existentes = self.leer()
        vistos = {(r["legajo"], r["fecha_hora"]) for r in existentes}
        agregados = 0
        for r in nuevos:
            clave = (r["legajo"], r["fecha_hora"])
            if not r["legajo"] or not r["fecha_hora"] or clave in vistos:
                continue
            vistos.add(clave)
            existentes.append({c: r.get(c, "") for c in CAMPOS})
            agregados += 1
        existentes.sort(key=lambda r: (r["fecha_hora"], r["legajo"]))
        tmp = self.base.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows(existentes)
        tmp.replace(self.base)
        return agregados


def importar_csv(ruta: Path, columnas: dict) -> list[dict]:
    """Lee un CSV exportado desde CrossChex Standard (u otro sistema).

    'columnas' mapea el nombre interno al encabezado del archivo, por ejemplo:
      {"legajo": "No.", "nombre": "Nombre", "fecha_hora": "Fecha/Hora",
       "tipo": "Estado", "dispositivo": "Dispositivo"}
    Si fecha y hora vienen en columnas separadas, usar "fecha" y "hora" en vez de "fecha_hora".
    """
    texto = Path(ruta).read_bytes()
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            contenido = texto.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    muestra = contenido[:2048]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.DictReader(contenido.splitlines(), dialect=dialecto))
    salida = []
    for fila in filas:
        def col(nombre):
            encabezado = columnas.get(nombre)
            return (fila.get(encabezado) or "").strip() if encabezado else ""

        if columnas.get("fecha_hora"):
            fecha_hora = col("fecha_hora")
        else:
            fecha_hora = f"{col('fecha')} {col('hora')}".strip()
        salida.append(
            {
                "legajo": col("legajo"),
                "nombre": col("nombre"),
                "fecha_hora": fecha_hora,
                "tipo": col("tipo"),
                "dispositivo": col("dispositivo"),
            }
        )
    return salida
