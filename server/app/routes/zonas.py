import json

from fastapi import APIRouter, Body, HTTPException
from psycopg2 import errors as pg_errors
from starlette import status

from ..db import get_cursor

router = APIRouter()


def _construir_poligono(coordenadas: list[dict]) -> dict:
    anillo = [[c["lon"], c["lat"]] for c in coordenadas]
    if anillo[0] != anillo[-1]:
        anillo.append(anillo[0])  # GeoJSON exige que el anillo se cierre en el mismo punto
    return {"type": "Polygon", "coordinates": [anillo]}


@router.get("")
def listar():
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, nombre, region, es_critica, poligono, creado_en
               FROM zonas ORDER BY creado_en DESC"""
        )
        return cur.fetchall()


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(body: dict = Body(...)):
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

    try:
        with get_cursor() as cur:
            cur.execute(
                """INSERT INTO zonas (nombre, region, es_critica, poligono)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, nombre, region, es_critica, poligono, creado_en""",
                (nombre.strip(), region.strip(), bool(es_critica), json.dumps(poligono)),
            )
            return cur.fetchone()
    except pg_errors.UniqueViolation as err:
        raise HTTPException(status_code=409, detail={"error": "Ya existe una zona con ese nombre y región"}) from err


@router.delete("/{zona_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(zona_id: str):
    with get_cursor() as cur:
        cur.execute("DELETE FROM zonas WHERE id = %s", (zona_id,))
