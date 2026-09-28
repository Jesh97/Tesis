"""Sesión basada en un token firmado (JWT), sin estado en el servidor: el
login emite el token y cada ruta protegida lo valida con la misma clave.
No requiere tabla de sesiones ni Redis -- suficiente para el alcance actual
del sistema."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError(
        'Falta "SESSION_SECRET" en el entorno (ver server/.env.example): sin ella cualquiera '
        "podría firmar tokens de sesión válidos con una clave por defecto conocida."
    )

ALGORITMO = "HS256"
DURACION_SESION = timedelta(hours=12)


def crear_token(usuario: dict) -> str:
    payload = {
        "sub": usuario["id"],
        "usuario": usuario["usuario"],
        "rol": usuario["rol"],
        "exp": datetime.now(timezone.utc) + DURACION_SESION,
    }
    return jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITMO)


def usuario_actual(authorization: str | None = Header(default=None)) -> dict:
    """Dependencia de FastAPI: exige `Authorization: Bearer <token>` válido.
    Se aplica a todos los routers excepto /api/auth (login) y /health."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "No autenticado"})
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"error": "Sesión inválida o expirada"})


def requiere_rol(*roles_permitidos: str):
    """Dependencia de FastAPI para acciones de configuración (crear/eliminar
    zonas, por ahora) que no cualquier sesión válida debería poder hacer --
    a diferencia de confirmar/descartar un incidente o aprobar una
    sugerencia, que son el trabajo normal de cualquier analista. Exige
    primero una sesión válida (usuario_actual) y además que el rol del token
    esté en roles_permitidos (ver rol_usuario en db/schema.sql)."""

    def _verificar(usuario: dict = Depends(usuario_actual)) -> dict:
        if usuario["rol"] not in roles_permitidos:
            raise HTTPException(status_code=403, detail={"error": "No tienes permiso para realizar esta acción"})
        return usuario

    return _verificar
