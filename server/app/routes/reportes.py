from fastapi import APIRouter

from ..db import ejecutar_sp, get_cursor

router = APIRouter()


# Alimenta el Dashboard de Reportes (antes usaba data/mockReports.ts en el
# frontend). Las 4 vistas ya existen en db/schema.sql; las funciones de
# db/procedures.sql solo las envuelven para que "reportes" también pase por
# procedimientos almacenados en vez de leer las vistas directamente.
@router.get("/resumen")
def resumen():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_reportes_resumen()")
        return cur.fetchone()


@router.get("/incidentes-por-mes")
def incidentes_por_mes():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_reportes_incidentes_por_mes()")
        return cur.fetchall()


@router.get("/tipos-infraccion")
def tipos_infraccion():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_reportes_tipos_infraccion()")
        return cur.fetchall()


@router.get("/zonas-top")
def zonas_top():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_reportes_zonas_top()")
        return cur.fetchall()
