import bcrypt
from fastapi import APIRouter, Body, HTTPException

from ..auth_dep import crear_token
from ..db import get_cursor

router = APIRouter()


@router.post("/login")
def login(body: dict = Body(...)):
    usuario = body.get("usuario")
    password = body.get("password")
    if not isinstance(usuario, str) or not isinstance(password, str):
        raise HTTPException(status_code=400, detail={"error": "Se requiere usuario y password"})

    with get_cursor() as cur:
        cur.execute(
            """SELECT id, usuario, password_hash, nombre_completo, rol, activo
               FROM usuarios WHERE usuario = %s""",
            (usuario,),
        )
        fila = cur.fetchone()

    coincide = bcrypt.checkpw(password.encode(), fila["password_hash"].encode()) if fila else False
    if not fila or not fila["activo"] or not coincide:
        raise HTTPException(status_code=401, detail={"error": "Usuario o contraseña incorrectos"})

    with get_cursor() as cur:
        cur.execute("UPDATE usuarios SET ultimo_acceso = now() WHERE id = %s", (fila["id"],))

    return {
        "token": crear_token(fila),
        "id": fila["id"],
        "usuario": fila["usuario"],
        "nombreCompleto": fila["nombre_completo"],
        "rol": fila["rol"],
    }
