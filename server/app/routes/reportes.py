from fastapi import APIRouter

from ..db import get_cursor

router = APIRouter()


# Alimenta el Dashboard de Reportes (antes usaba data/mockReports.ts en el
# frontend). Las 4 vistas ya existen en db/schema.sql -- esta ruta solo las expone.
@router.get("/resumen")
def resumen():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM vw_reportes_resumen")
        return cur.fetchone()


@router.get("/incidentes-por-mes")
def incidentes_por_mes():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM vw_incidentes_por_mes")
        return cur.fetchall()


@router.get("/tipos-infraccion")
def tipos_infraccion():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM vw_tipos_infraccion_resumen")
        return cur.fetchall()


@router.get("/zonas-top")
def zonas_top():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM vw_zonas_top")
        return cur.fetchall()
