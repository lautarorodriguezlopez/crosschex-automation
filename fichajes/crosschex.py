"""Cliente mínimo de la API de CrossChex Cloud (Anviz).

Usa solo la biblioteca estándar. Dos llamadas:
  1. authorize.token / token       -> obtiene un JWT
  2. attendance.record / getrecord -> trae los fichajes paginados (máx. 1000 por página)
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


class CrossChexError(RuntimeError):
    pass


def _header(name_space: str, name_action: str) -> dict:
    return {
        "nameSpace": name_space,
        "nameAction": name_action,
        "version": "1.0",
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


class CrossChexClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str, timeout: int = 30):
        if not api_key or not api_secret:
            raise CrossChexError(
                "Faltan api_key / api_secret en config.json (sección 'crosschex')."
            )
        if not base_url.lower().startswith("https://"):
            # Las credenciales y los fichajes viajan en este pedido: nunca por HTTP plano.
            raise CrossChexError("La base_url de CrossChex tiene que empezar con https://")
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self._token: str | None = None

    # ---- bajo nivel -------------------------------------------------------
    def _post(self, body: dict, intentos: int = 3) -> dict:
        data = json.dumps(body).encode("utf-8")
        ultimo_error = None
        for intento in range(1, intentos + 1):
            req = urllib.request.Request(
                self.base_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    respuesta = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                cuerpo = e.read().decode("utf-8", "replace")[:300]
                if 400 <= e.code < 500:  # credenciales o pedido inválido: reintentar no sirve
                    raise CrossChexError(f"CrossChex respondió HTTP {e.code}: {cuerpo}") from e
                ultimo_error = f"HTTP {e.code}: {cuerpo}"
                time.sleep(2 * intento)
                continue
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                ultimo_error = e
                time.sleep(2 * intento)
                continue
            error = respuesta.get("error") or {}
            if error:
                raise CrossChexError(f"CrossChex devolvió un error: {error}")
            return respuesta
        raise CrossChexError(f"No se pudo conectar con CrossChex: {ultimo_error}")

    # ---- alto nivel -------------------------------------------------------
    def token(self) -> str:
        if self._token:
            return self._token
        body = {
            "header": _header("authorize.token", "token"),
            "payload": {"api_key": self.api_key, "api_secret": self.api_secret},
        }
        resp = self._post(body)
        payload = (resp.get("payload") or resp.get("data", {}).get("payload") or {})
        tok = payload.get("token")
        if not tok:
            raise CrossChexError(f"La respuesta no trajo token: {resp}")
        self._token = tok
        return tok

    def registros(self, desde: datetime, hasta: datetime, por_pagina: int = 1000) -> list[dict]:
        """Devuelve todos los fichajes entre 'desde' y 'hasta' (datetimes con zona horaria)."""
        todos: list[dict] = []
        pagina = 1
        while True:
            body = {
                "header": _header("attendance.record", "getrecord"),
                "authorize": {"type": "token", "token": self.token()},
                "payload": {
                    "begin_time": desde.isoformat(timespec="seconds"),
                    "end_time": hasta.isoformat(timespec="seconds"),
                    "order": "asc",
                    "page": pagina,
                    "per_page": por_pagina,
                },
            }
            resp = self._post(body)
            payload = (resp.get("payload") or resp.get("data", {}).get("payload") or {})
            lista = payload.get("list") or []
            todos.extend(lista)
            total_paginas = int(payload.get("pageCount") or 1)
            if pagina >= total_paginas or not lista:
                break
            pagina += 1
        return todos


def normalizar_api(registro: dict) -> dict:
    """Convierte un registro de la API al formato interno."""
    emp = registro.get("employee") or {}
    dev = registro.get("device") or {}
    nombre = " ".join(
        p for p in [emp.get("first_name", ""), emp.get("last_name", "")] if p
    ).strip()
    return {
        "legajo": str(emp.get("workno", "")).strip(),
        "nombre": nombre,
        "fecha_hora": registro.get("checktime", ""),
        "tipo": str(registro.get("checktype", "")),
        "dispositivo": dev.get("name") or dev.get("serial_number") or "",
    }
