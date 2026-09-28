"""Límite general de solicitudes por identidad, para complementar el bloqueo
específico de intentos fallidos que ya tiene /api/auth/login (ver
routes/auth.py): ese cubre "no adivines la contraseña"; este cubre "no
satures la API una vez adentro" -- documentado como riesgo aceptado en
SECURITY.md hasta agregar esto.

En memoria del proceso, mismo enfoque y misma limitación que el bloqueo de
login: no se comparte entre instancias si el sistema alguna vez corre en
varias a la vez detrás de un balanceador."""
import threading
import time

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .auth_dep import ALGORITMO, SESSION_SECRET

# 120 solicitudes/minuto por identidad: de sobra para el uso normal de la UI
# (la página de Reportes, por ejemplo, dispara 4 fetches en paralelo al
# cargar) pero acota un script o un cliente mal comportado.
LIMITE_SOLICITUDES = 120
VENTANA_SEGUNDOS = 60.0

# /health lo consulta cualquier chequeo de salud (uptime monitor, el propio
# balanceador) con una frecuencia que no depende de un usuario real.
_RUTAS_SIN_LIMITE = {"/health"}

_contadores: dict[str, tuple[float, int]] = {}
_lock = threading.Lock()


def _identidad(request: Request) -> str:
    """Por usuario si el token es válido (misma cuota sin importar desde qué
    IP entre), si no por IP -- igual que el bloqueo de login en auth.py."""
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        try:
            payload = jwt.decode(authorization.removeprefix("Bearer ").strip(), SESSION_SECRET, algorithms=[ALGORITMO])
            return f"usuario:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    ip = request.client.host if request.client else "desconocida"
    return f"ip:{ip}"


def _excede_el_limite(clave: str) -> bool:
    """Ventana fija (no deslizante): más barato en memoria que guardar cada
    timestamp, a costa de permitir hasta 2x el límite justo en el borde de
    dos ventanas consecutivas -- aceptable para esto, que busca frenar abuso
    sostenido, no contar solicitudes con precisión."""
    ahora = time.time()
    with _lock:
        inicio_ventana, cantidad = _contadores.get(clave, (ahora, 0))
        if ahora - inicio_ventana >= VENTANA_SEGUNDOS:
            inicio_ventana, cantidad = ahora, 0
        cantidad += 1
        _contadores[clave] = (inicio_ventana, cantidad)
        return cantidad > LIMITE_SOLICITUDES


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _RUTAS_SIN_LIMITE:
            return await call_next(request)
        if _excede_el_limite(_identidad(request)):
            return JSONResponse(status_code=429, content={"error": "Demasiadas solicitudes. Intenta de nuevo en un minuto."})
        return await call_next(request)
