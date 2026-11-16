# Seguridad

## Reportar una vulnerabilidad

Usá el reporte privado de GitHub (pestaña **Security → Report a vulnerability**) o escribime por
[LinkedIn](https://www.linkedin.com/in/lautarorodriguezl). Por favor, no publiques el problema hasta que
esté resuelto. Respondo en 72 horas.

## Cómo se protegen los datos

La herramienta maneja fichajes del personal y credenciales de CrossChex, así que todo está pensado para
que nada salga de la computadora donde corre.

| Riesgo | Control |
|---|---|
| Credenciales en el repositorio | `config.json`, `data/`, `reportes/`, `logs/` y `demo/` están en `.gitignore`. El CI falla si alguno aparece versionado. |
| Credenciales interceptadas | La API de CrossChex se consulta solo por HTTPS, con la verificación de certificados de Python. |
| Otra computadora de la red ve el reporte | El servidor escucha solo en `127.0.0.1` y se cierra solo a los 120 minutos. |
| DNS rebinding (una web externa que lee `localhost` desde el navegador) | El servidor rechaza con 403 todo pedido cuyo `Host` no sea `localhost` o `127.0.0.1` en su puerto. |
| Inyección de código (XSS) con datos de CrossChex | Todo dato se escapa antes de mostrarse. Además, el reporte tiene una CSP que solo deja correr su propio script, identificado por hash. |
| Fuga de datos desde el reporte | La CSP bloquea conexiones, imágenes y formularios hacia afuera (`default-src 'none'`). Sin CDNs, fuentes ni analítica externas: la tipografía va incrustada. |
| Clickjacking y sniffing | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. |
| Listado de archivos | El servidor no lista carpetas: solo entrega los archivos del reporte. |
| Dependencias vulnerables | No hay: usa solo la biblioteca estándar de Python. |
| Cadena de suministro en CI | Actions fijadas por SHA, permisos de solo lectura y sin credenciales persistidas. Dependabot las actualiza. |

Las marcas de "revisada" del reporte se guardan en el navegador (`localStorage`) de esa computadora.
