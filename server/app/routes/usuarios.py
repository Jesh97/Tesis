import re
import uuid

import bcrypt
from fastapi import APIRouter, Body, Depends, HTTPException, status

from ..auth_dep import requiere_rol
from ..db import ejecutar_sp, get_cursor

router = APIRouter()

# Alta de cuentas: solo administrador, y solo de menor rango (el rol
# "administrador" no se puede asignar por acá -- sp_usuarios_crear también
# lo rechaza). Se usa como Depends() para que la auditoría registre quién
# creó cada cuenta.
_solo_admin = requiere_rol("administrador")

ROLES_ASIGNABLES = ("supervisor", "analista")
LONGITUD_MINIMA_PASSWORD = 8
# Mismo formato que pide el login: "inicial.apellido" (minúsculas, dígitos, . _ -).
_PATRON_USUARIO = re.compile(r"^[a-z0-9._-]{3,60}$")


@router.get("", dependencies=[Depends(_solo_admin)])
def listar():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_usuarios_listar()")
        return cur.fetchall()


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(body: dict = Body(...), admin: dict = Depends(_solo_admin)):
    usuario = body.get("usuario")
    nombre_completo = body.get("nombreCompleto")
    password = body.get("password")
    rol = body.get("rol")

    if not isinstance(usuario, str) or not _PATRON_USUARIO.match(usuario.strip().lower()):
        raise HTTPException(
            status_code=400,
            detail={"error": "Usuario inválido: usa de 3 a 60 caracteres (letras minúsculas, números, punto, guion)"},
        )
    if not isinstance(nombre_completo, str) or not nombre_completo.strip():
        raise HTTPException(status_code=400, detail={"error": 'Falta "nombreCompleto"'})
    if len(nombre_completo.strip()) > 150:
        raise HTTPException(status_code=400, detail={"error": "El nombre completo no puede superar 150 caracteres"})
    _validar_password(password)
    if rol not in ROLES_ASIGNABLES:
        raise HTTPException(status_code=400, detail={"error": "El rol debe ser supervisor o analista"})

    with get_cursor() as cur:
        ejecutar_sp(
            cur,
            "SELECT * FROM sp_usuarios_crear(%s, %s, %s, %s, %s)",
            (usuario.strip().lower(), _hashear(password), nombre_completo.strip(), rol, admin["sub"]),
        )
        return cur.fetchone()


# Restablece la contraseña de un supervisor/analista (p.ej. si la olvidó).
# sp_usuarios_cambiar_password rechaza a otros administradores.
@router.post("/{usuario_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(usuario_id: uuid.UUID, body: dict = Body(...), admin: dict = Depends(_solo_admin)):
    password = body.get("password")
    _validar_password(password)
    with get_cursor() as cur:
        ejecutar_sp(
            cur,
            "SELECT sp_usuarios_cambiar_password(%s, %s, %s)",
            (str(usuario_id), _hashear(password), admin["sub"]),
        )


# Deshabilitar en vez de borrar: la auditoría sigue apuntando al usuario
# (ver auditoria en db/schema.sql). El login ya rechaza cuentas con activo=false.
@router.post("/{usuario_id}/estado", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_estado(usuario_id: uuid.UUID, body: dict = Body(...), admin: dict = Depends(_solo_admin)):
    activo = body.get("activo")
    if not isinstance(activo, bool):
        raise HTTPException(status_code=400, detail={"error": 'Falta "activo" (true/false)'})
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_usuarios_cambiar_estado(%s, %s, %s)", (str(usuario_id), activo, admin["sub"]))


def _validar_password(password) -> None:
    if not isinstance(password, str) or len(password) < LONGITUD_MINIMA_PASSWORD:
        raise HTTPException(
            status_code=400,
            detail={"error": f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres"},
        )


def _hashear(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
