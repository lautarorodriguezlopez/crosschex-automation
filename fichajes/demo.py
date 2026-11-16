"""Genera fichajes ficticios con anomalías plantadas, para probar sin conectarse a CrossChex."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

EMPLEADOS = {
    "101": ("Ana Pérez", {"lun": ["09:00", "17:00"], "mar": ["09:00", "17:00"], "mie": ["09:00", "17:00"],
                          "jue": ["09:00", "17:00"], "vie": ["09:00", "17:00"]}),
    "102": ("Bruno Díaz", {"mar": ["11:00", "19:00"], "mie": ["11:00", "19:00"], "jue": ["11:00", "19:00"],
                           "vie": ["11:00", "19:00"], "sab": ["11:00", "19:00"]}),
    "103": ("Carla Gómez", {"jue": ["20:00", "02:00"], "vie": ["20:00", "03:00"], "sab": ["20:00", "03:00"],
                            "dom": ["19:00", "01:00"]}),
    "104": ("Diego Romero", {"lun": ["07:00", "15:00"], "mar": ["07:00", "15:00"], "mie": ["07:00", "15:00"],
                             "jue": ["07:00", "15:00"], "vie": ["07:00", "15:00"], "sab": ["07:00", "12:00"]}),
    "105": ("Elena Suárez", {"mie": ["18:00", "00:00"], "jue": ["18:00", "00:00"], "vie": ["18:00", "01:00"],
                             "sab": ["18:00", "01:00"], "dom": ["12:00", "18:00"]}),
    "106": ("Federico Ruiz", {"lun": ["12:00", "20:00"], "mar": ["12:00", "20:00"], "mie": ["12:00", "20:00"],
                              "jue": ["12:00", "20:00"], "vie": ["12:00", "20:00"]}),
    "107": ("Gabriela Sosa", {"vie": ["19:00", "03:00"], "sab": ["19:00", "03:00"], "dom": ["19:00", "00:00"]}),
    "108": ("Hernán López", {"lun": ["08:00", "16:00"], "mar": ["08:00", "16:00"], "mie": ["08:00", "16:00"],
                             "jue": ["08:00", "16:00"], "vie": ["08:00", "16:00"]}),
}
DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
DISPOSITIVOS = ["Reloj Salón", "Reloj Cocina", "Reloj Eventos"]


def _hhmm(s):
    h, m = s.split(":")
    return timedelta(hours=int(h), minutes=int(m))


def generar(hasta: date, dias: int = 21, semilla: int = 7):
    rnd = random.Random(semilla)
    registros = []
    desde = hasta - timedelta(days=dias - 1)
    d = desde
    while d <= hasta:
        for legajo, (nombre, turnos) in EMPLEADOS.items():
            franja = turnos.get(DIAS[d.weekday()])
            base = datetime.combine(d, datetime.min.time())
            disp = rnd.choice(DISPOSITIVOS)
            if not franja:
                if rnd.random() < 0.02:  # fichaje en franco
                    e = base + timedelta(hours=10, minutes=rnd.randint(0, 30))
                    registros += [(legajo, nombre, e, disp), (legajo, nombre, e + timedelta(hours=4), disp)]
                continue
            inicio, fin = base + _hhmm(franja[0]), base + _hhmm(franja[1])
            if fin <= inicio:
                fin += timedelta(days=1)
            r = rnd.random()
            if r < 0.03:  # ausencia
                continue
            entrada = inicio + timedelta(minutes=rnd.randint(-12, 6))
            salida = fin + timedelta(minutes=rnd.randint(-4, 15))
            if r < 0.09:
                entrada = inicio + timedelta(minutes=rnd.randint(18, 55))  # tarde
            elif r < 0.13:
                salida = fin - timedelta(minutes=rnd.randint(25, 90))  # salida anticipada
            elif r < 0.16:
                salida = fin + timedelta(hours=rnd.randint(4, 6))  # jornada excesiva
            marcas = [entrada]
            # pausa de almuerzo / cena en turnos largos
            if (fin - inicio) >= timedelta(hours=7) and rnd.random() < 0.6:
                p = entrada + timedelta(hours=4, minutes=rnd.randint(0, 30))
                duracion = rnd.randint(25, 45) if rnd.random() > 0.08 else rnd.randint(100, 150)
                marcas += [p, p + timedelta(minutes=duracion)]
            marcas.append(salida)
            if rnd.random() < 0.05:  # se olvidó de fichar la salida
                marcas.pop()
            if rnd.random() < 0.04:  # doble fichaje
                marcas.insert(1, marcas[0] + timedelta(seconds=rnd.randint(20, 100)))
            for m in marcas:
                registros.append((legajo, nombre, m, disp))
        d += timedelta(days=1)

    return [
        {
            "legajo": leg,
            "nombre": nom,
            "fecha_hora": dt.strftime("%Y-%m-%dT%H:%M:%S-03:00"),
            "tipo": "0",
            "dispositivo": disp,
        }
        for leg, nom, dt, disp in sorted(registros, key=lambda x: x[2])
    ]


def config_demo() -> dict:
    return {
        "zona_horaria": "-03:00",
        "horarios": {
            "empleados": {leg: {"nombre": n, "turnos": t} for leg, (n, t) in EMPLEADOS.items()}
        },
    }
