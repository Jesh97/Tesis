import threading
import time

import bcrypt
from fastapi import APIRouter, Body, HTTPException, Request

from ..auth_dep import crear_token
from ..db import ejecutar_sp, get_cursor

router = APIRouter()

# Hash "señuelo" contra el que se compara cuando el usuario no existe, para
# que bcrypt.checkpw corra siempre (mismo costo computacional) sin importar
# si el usuario es real -- si se lo salta cuando fila es None (como estaba
# antes), un usuario inexistente responde notablemente más rápido que uno
# real, y ese tiempo de respuesta permite enumerar usuarios válidos sin
# siquiera acertar la contraseña.
_HASH_SEÑUELO = bcrypt.hashpw(b"sin-usuario-tiempo-constante", bcrypt.gensalt()).decode()

# Bloqueo simple por (ip, usuario) tras varios intentos fallidos seguidos.
# En memoria del proceso (no Redis ni tabla en BD): alcanza para el alcance
# actual del sistema (un solo proceso Uvicorn) -- ver SECURITY.md para esta
# limitación y qué haría falta para varias instancias.
_INTENTOS_MAXIMOS = 5
_VENTANA_BLOQUEO_SEGUNDOS = 15 * 60
_intentos_fallidos: dict[str, list[float]] = {}
_intentos_lock = threading.Lock()


def _intentos_vigentes(clave: str, ahora: float) -> list[float]:
    return [t for t in _intentos_fallidos.get(clave, []) if t > ahora - _VENTANA_BLOQUEO_SEGUNDOS]


def _limite_excedido(clave: str) -> bool:
    ahora = time.time()
    with _intentos_lock:
        vigentes = _intentos_vigentes(clave, ahora)
        _intentos_fallidos[clave] = vigentes
        return len(vigentes) >= _INTENTOS_MAXIMOS


def _registrar_intento_fallido(clave: str) -> None:
    ahora = time.time()
    with _intentos_lock:
        _intentos_fallidos[clave] = _intentos_vigentes(clave, ahora) + [ahora]


def _limpiar_intentos(clave: str) -> None:
    with _intentos_lock:
        _intentos_fallidos.pop(clave, None)


@router.post("/login")
def login(request: Request, body: dict = Body(...)):
    usuario = body.get("usuario")
    password = body.get("password")
    if not isinstance(usuario, str) or not isinstance(password, str):
        raise HTTPException(status_code=400, detail={"error": "Se requiere usuario y password"})

    ip = request.client.host if request.client else "desconocida"
    clave_bloqueo = f"{ip}|{usuario.strip().lower()}"
    if _limite_excedido(clave_bloqueo):
        minutos = _VENTANA_BLOQUEO_SEGUNDOS // 60
        raise HTTPException(
            status_code=429,
            detail={"error": f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutos} minutos."},
        )

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_usuarios_buscar_para_login(%s)", (usuario,))
        fila = cur.fetchone()

    hash_a_comparar = fila["password_hash"] if fila else _HASH_SEÑUELO
    coincide = bcrypt.checkpw(password.encode(), hash_a_comparar.encode())
    if not fila or not fila["activo"] or not coincide:
        _registrar_intento_fallido(clave_bloqueo)
        raise HTTPException(status_code=401, detail={"error": "Usuario o contraseña incorrectos"})

    _limpiar_intentos(clave_bloqueo)

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_usuarios_marcar_acceso(%s)", (fila["id"],))

    return {
        "token": crear_token(fila),
        "id": fila["id"],
        "usuario": fila["usuario"],
        "nombreCompleto": fila["nombre_completo"],
        "rol": fila["rol"],
    }
