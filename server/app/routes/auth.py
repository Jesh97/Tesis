import bcrypt
from fastapi import APIRouter, Body, HTTPException

from ..auth_dep import crear_token
from ..db import ejecutar_sp, get_cursor

router = APIRouter()


@router.post("/login")
def login(body: dict = Body(...)):
    usuario = body.get("usuario")
    password = body.get("password")
    if not isinstance(usuario, str) or not isinstance(password, str):
        raise HTTPException(status_code=400, detail={"error": "Se requiere usuario y password"})

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_usuarios_buscar_para_login(%s)", (usuario,))
        fila = cur.fetchone()

    coincide = bcrypt.checkpw(password.encode(), fila["password_hash"].encode()) if fila else False
    if not fila or not fila["activo"] or not coincide:
        raise HTTPException(status_code=401, detail={"error": "Usuario o contraseña incorrectos"})

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_usuarios_marcar_acceso(%s)", (fila["id"],))

    return {
        "token": crear_token(fila),
        "id": fila["id"],
        "usuario": fila["usuario"],
        "nombreCompleto": fila["nombre_completo"],
        "rol": fila["rol"],
    }
