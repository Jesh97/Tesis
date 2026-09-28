from fastapi import APIRouter, Depends, Query

from ..auth_dep import requiere_rol
from ..db import ejecutar_sp, get_cursor

router = APIRouter()

_solo_admin = requiere_rol("administrador")


# Quién confirmó/descartó cada incidente, creó/eliminó cada zona o
# aprobó/rechazó cada sugerencia -- ver sp_auditoria_registrar en
# db/procedures.sql. Solo administrador: es información sobre el desempeño
# de los propios analistas, no algo que un analista deba poder consultar
# sobre sus pares.
@router.get("", dependencies=[Depends(_solo_admin)])
def listar(limite: int = Query(default=100, gt=0, le=500)):
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_auditoria_listar(%s)", (limite,))
        return cur.fetchall()
