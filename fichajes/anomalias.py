"""Reglas de detección de anomalías en fichajes.

Cada fichaje se asigna a una "jornada": la fecha calendario corrida por la hora de corte
(con corte 05:00, un fichaje a las 02:30 del martes pertenece a la jornada del lunes).
Así los turnos nocturnos que cruzan la medianoche quedan en una sola jornada.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]

TIPOS = {
    "duplicado": ("Fichaje duplicado", "baja"),
    "impar": ("Falta entrada o salida", "alta"),
    "ausencia": ("Ausencia sin fichajes", "alta"),
    "tarde": ("Llegada tarde", "media"),
    "salida_anticipada": ("Salida anticipada", "media"),
    "jornada_larga": ("Jornada excesiva", "media"),
    "jornada_corta": ("Jornada muy corta", "baja"),
    "pausa_larga": ("Pausa larga", "baja"),
    "franco": ("Fichó en día franco", "baja"),
}

FORMATOS_POR_DEFECTO = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
]


def _zona(offset: str) -> timezone:
    signo = -1 if offset.startswith("-") else 1
    h, m = offset.lstrip("+-").split(":")
    return timezone(signo * timedelta(hours=int(h), minutes=int(m)))


def parsear_fecha(texto: str, zona: timezone, formatos: list[str]) -> datetime | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        dt = None
        for fmt in formatos:
            try:
                dt = datetime.strptime(texto, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(zona).replace(tzinfo=None)
    return dt


def _hhmm(texto: str) -> timedelta:
    h, m = texto.split(":")
    return timedelta(hours=int(h), minutes=int(m))


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _horas(td: timedelta) -> float:
    return round(td.total_seconds() / 3600, 2)


class Analizador:
    def __init__(self, config: dict):
        reglas = config.get("reglas", {})
        self.zona = _zona(config.get("zona_horaria", "-03:00"))
        self.formatos = config.get("formatos_fecha") or FORMATOS_POR_DEFECTO
        self.corte = _hhmm(reglas.get("hora_corte_jornada", "05:00"))
        self.min_duplicado = reglas.get("minutos_duplicado", 3)
        self.tolerancia = reglas.get("tolerancia_minutos", 10)
        self.max_horas = reglas.get("jornada_maxima_horas", 12)
        self.min_horas = reglas.get("jornada_minima_horas", 2)
        self.max_pausa = reglas.get("pausa_maxima_minutos", 90)
        self.feriados = set(config.get("feriados", []))
        hor = config.get("horarios", {})
        self.horario_defecto = hor.get("por_defecto")
        self.empleados = {str(k): v for k, v in (hor.get("empleados") or {}).items()}
        self.no_parseados: list[dict] = []

    # ---- utilidades ------------------------------------------------------
    def jornada_de(self, dt: datetime) -> date:
        return (dt - self.corte).date()

    def turno(self, legajo: str, jornada: date):
        """Devuelve (inicio, fin) programados como datetimes, o None si es franco/sin horario."""
        emp = self.empleados.get(legajo)
        turnos = (emp or {}).get("turnos") if emp else None
        if turnos is None:
            turnos = (self.horario_defecto or {}).get("turnos") if self.horario_defecto else None
        if turnos is None:
            return "sin_horario"
        franja = turnos.get(DIAS[jornada.weekday()])
        if not franja:
            return None
        base = datetime.combine(jornada, datetime.min.time())
        inicio = base + _hhmm(franja[0])
        fin = base + _hhmm(franja[1])
        if fin <= inicio:  # turno que cruza la medianoche
            fin += timedelta(days=1)
        return inicio, fin

    # ---- análisis --------------------------------------------------------
    def analizar(self, registros: list[dict], desde: date | None = None, hasta: date | None = None):
        grupos: dict[tuple[str, date], list[datetime]] = defaultdict(list)
        nombres: dict[str, str] = {}
        for r in registros:
            dt = parsear_fecha(r.get("fecha_hora", ""), self.zona, self.formatos)
            if dt is None:
                self.no_parseados.append(r)
                continue
            legajo = str(r.get("legajo", "")).strip()
            if r.get("nombre"):
                nombres[legajo] = r["nombre"]
            j = self.jornada_de(dt)
            if desde and j < desde or hasta and j > hasta:
                continue
            grupos[(legajo, j)].append(dt)
        for legajo, emp in self.empleados.items():
            if emp.get("nombre") and legajo not in nombres:
                nombres[legajo] = emp["nombre"]

        anomalias: list[dict] = []
        dias: list[dict] = []

        def anotar(legajo, jornada, tipo, detalle, marcas):
            titulo, severidad = TIPOS[tipo]
            anomalias.append(
                {
                    "legajo": legajo,
                    "nombre": nombres.get(legajo, ""),
                    "jornada": jornada.isoformat(),
                    "tipo": tipo,
                    "titulo": titulo,
                    "severidad": severidad,
                    "detalle": detalle,
                    "fichajes": [_fmt(m) for m in marcas],
                }
            )

        for (legajo, jornada), marcas in sorted(grupos.items()):
            # el mismo instante exacto llegado dos veces (p. ej. por API y por CSV) no es un
            # doble fichaje real: se cuenta una sola vez
            marcas = sorted(set(marcas))
            # 1) duplicados: dos fichajes muy seguidos -> se descarta el segundo
            limpias = [marcas[0]]
            for m in marcas[1:]:
                if m - limpias[-1] < timedelta(minutes=self.min_duplicado):
                    anotar(legajo, jornada, "duplicado",
                           f"Dos fichajes con menos de {self.min_duplicado} min de diferencia "
                           f"({_fmt(limpias[-1])} y {_fmt(m)}).", marcas)
                    continue
                limpias.append(m)

            horas_trab = None
            par = len(limpias) % 2 == 0
            if not par:
                anotar(legajo, jornada, "impar",
                       f"{len(limpias)} fichaje(s): número impar, falta una entrada o una salida.",
                       limpias)
            else:
                trabajado = sum(
                    (limpias[i + 1] - limpias[i] for i in range(0, len(limpias), 2)), timedelta()
                )
                horas_trab = _horas(trabajado)
                if horas_trab > self.max_horas:
                    anotar(legajo, jornada, "jornada_larga",
                           f"{horas_trab} h trabajadas (máximo configurado: {self.max_horas} h).",
                           limpias)
                elif horas_trab < self.min_horas:
                    anotar(legajo, jornada, "jornada_corta",
                           f"{horas_trab} h trabajadas (mínimo configurado: {self.min_horas} h).",
                           limpias)
                for i in range(1, len(limpias) - 1, 2):
                    pausa = limpias[i + 1] - limpias[i]
                    if pausa > timedelta(minutes=self.max_pausa):
                        anotar(legajo, jornada, "pausa_larga",
                               f"Pausa de {int(pausa.total_seconds() // 60)} min entre "
                               f"{_fmt(limpias[i])} y {_fmt(limpias[i + 1])}.", limpias)

            turno = self.turno(legajo, jornada)
            programado = ""
            if turno is None:
                if jornada.isoformat() not in self.feriados:
                    anotar(legajo, jornada, "franco",
                           "Hay fichajes en un día que no tiene turno asignado.", limpias)
                programado = "franco"
            elif turno != "sin_horario":
                inicio, fin = turno
                programado = f"{_fmt(inicio)}–{_fmt(fin)}"
                retraso = limpias[0] - inicio
                if retraso > timedelta(minutes=self.tolerancia):
                    anotar(legajo, jornada, "tarde",
                           f"Entró {_fmt(limpias[0])}, turno a las {_fmt(inicio)} "
                           f"({int(retraso.total_seconds() // 60)} min tarde).", limpias)
                if par:
                    adelanto = fin - limpias[-1]
                    if adelanto > timedelta(minutes=self.tolerancia):
                        anotar(legajo, jornada, "salida_anticipada",
                               f"Salió {_fmt(limpias[-1])}, turno hasta las {_fmt(fin)} "
                               f"({int(adelanto.total_seconds() // 60)} min antes).", limpias)

            dias.append(
                {
                    "legajo": legajo,
                    "nombre": nombres.get(legajo, ""),
                    "jornada": jornada.isoformat(),
                    "fichajes": [_fmt(m) for m in limpias],
                    "horas": horas_trab,
                    "programado": programado,
                }
            )

        # 2) ausencias: días con turno asignado y sin ningún fichaje
        if grupos or (desde and hasta):
            todas = [j for (_, j) in grupos]
            ini = desde or min(todas)
            fin = hasta or max(todas)
            presentes = set(grupos)
            for legajo in self.empleados:
                d = ini
                while d <= fin:
                    if (legajo, d) not in presentes and d.isoformat() not in self.feriados:
                        t = self.turno(legajo, d)
                        if t not in (None, "sin_horario"):
                            anotar(legajo, d, "ausencia",
                                   f"Tenía turno {_fmt(t[0])}–{_fmt(t[1])} y no registró fichajes.",
                                   [])
                    d += timedelta(days=1)

        orden = {"alta": 0, "media": 1, "baja": 2}
        anomalias.sort(key=lambda a: (orden[a["severidad"]], a["legajo"]))
        anomalias.sort(key=lambda a: a["jornada"], reverse=True)  # estable: dentro del día, por severidad
        dias.sort(key=lambda d: (d["jornada"], d["legajo"]), reverse=True)
        return {"anomalias": anomalias, "dias": dias, "nombres": nombres}
