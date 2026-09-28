import json

from fastapi import APIRouter, Body, Depends, HTTPException
from starlette import status

from ..auth_dep import requiere_rol
from ..db import ejecutar_sp, get_cursor

router = APIRouter()

# Crear/eliminar una zona crítica cambia qué se vigila en todo el sistema (y
# eliminar una además deja huérfanos los incidentes que la referencian) --
# a diferencia de confirmar/descartar un incidente, esto no es el trabajo
# del día a día de un analista. listar() se deja sin restricción de rol:
# cualquier sesión válida necesita ver las zonas para monitorear el mapa.
# Se usa como Depends() (no solo en `dependencies=`) porque además de
# bloquear a quien no sea administrador, entrega el usuario para que
# sp_zonas_crear/eliminar dejen registro de quién hizo el cambio (ver
# auditoria en db/schema.sql).
_solo_admin = requiere_rol("administrador")


def _construir_poligono(coordenadas: list[dict]) -> dict:
    anillo = [[c["lon"], c["lat"]] for c in coordenadas]
    if anillo[0] != anillo[-1]:
        anillo.append(anillo[0])  # GeoJSON exige que el anillo se cierre en el mismo punto
    return {"type": "Polygon", "coordinates": [anillo]}


@router.get("")
def listar():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_zonas_listar()")
        return cur.fetchall()


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(body: dict = Body(...), usuario: dict = Depends(_solo_admin)):
    nombre = body.get("nombre")
    region = body.get("region")
    es_critica = body.get("esCritica")
    coordenadas = body.get("coordenadas")

    if not isinstance(nombre, str) or not nombre.strip():
        raise HTTPException(status_code=400, detail={"error": 'Falta "nombre"'})
    if not isinstance(region, str) or not region.strip():
        raise HTTPException(status_code=400, detail={"error": 'Falta "region"'})
    if (
        not isinstance(coordenadas, list)
        or len(coordenadas) < 3
        or not all(isinstance(c, dict) and isinstance(c.get("lat"), (int, float)) and isinstance(c.get("lon"), (int, float)) for c in coordenadas)
    ):
        raise HTTPException(
            status_code=400,
            detail={"error": "Se requieren al menos 3 coordenadas {lat, lon} para formar un polígono"},
        )

    poligono = _construir_poligono(coordenadas)

    with get_cursor() as cur:
        ejecutar_sp(
            cur,
            "SELECT * FROM sp_zonas_crear(%s, %s, %s, %s, %s)",
            (nombre.strip(), region.strip(), bool(es_critica), json.dumps(poligono), usuario["sub"]),
        )
        return cur.fetchone()


@router.delete("/{zona_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(zona_id: str, usuario: dict = Depends(_solo_admin)):
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_zonas_eliminar(%s, %s)", (zona_id, usuario["sub"]))
