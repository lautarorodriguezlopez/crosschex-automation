"""Servidor local para ver el reporte en http://localhost:PUERTO"""

from __future__ import annotations

import functools
import http.server
import socket
import threading
import urllib.request
import webbrowser
from pathlib import Path


class _Silencioso(http.server.SimpleHTTPRequestHandler):
    """Sirve solo los reportes, solo a esta computadora y con headers de seguridad."""

    def log_message(self, *args):
        pass

    def _host_valido(self) -> bool:
        # Contra DNS rebinding: una web maliciosa podría hacer que su dominio apunte a
        # 127.0.0.1 y leer el reporte desde el navegador. Solo se aceptan pedidos dirigidos
        # a localhost o 127.0.0.1 en el puerto de este servidor.
        puerto = self.server.server_address[1]
        return (self.headers.get("Host") or "").lower() in {f"localhost:{puerto}", f"127.0.0.1:{puerto}"}

    def do_GET(self):
        if not self._host_valido():
            self.send_error(403, "Host no permitido")
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._host_valido():
            self.send_error(403, "Host no permitido")
            return
        super().do_HEAD()

    def list_directory(self, path):
        # Sin listado de carpetas: solo se sirven los archivos del reporte.
        self.send_error(404, "No encontrado")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()


def _puerto_ocupado(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def _es_nuestro(puerto: int) -> bool:
    """¿El que ocupa el puerto es un servidor de una corrida anterior de esta herramienta?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/", timeout=2) as r:
            return b"<title>Control de fichajes</title>" in r.read(4096)
    except OSError:
        return False


def servir(carpeta: Path, puerto: int = 8765, minutos: int = 0, abrir: bool = True) -> None:
    """Sirve la carpeta de reportes solo en esta computadora (127.0.0.1).

    minutos = 0 -> queda abierto hasta Ctrl+C. Si ya hay un servidor de una corrida
    anterior en ese puerto, solo abre el navegador (el index.html ya está actualizado).
    """
    for _ in range(10):
        if not _puerto_ocupado(puerto):
            break
        if _es_nuestro(puerto):
            url = f"http://localhost:{puerto}/"
            print(f"Ya hay un servidor en {url}; abro el navegador.")
            if abrir:
                webbrowser.open(url)
            return
        puerto += 1  # otro programa usa el puerto: pruebo el siguiente
    url = f"http://localhost:{puerto}/"
    handler = functools.partial(_Silencioso, directory=str(carpeta))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), handler)
    if minutos:
        threading.Timer(minutos * 60, httpd.shutdown).start()
    print(f"Reporte disponible en {url}" + (f" durante {minutos} min" if minutos else " (Ctrl+C para cerrar)"))
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
