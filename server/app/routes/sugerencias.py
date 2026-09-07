from fastapi import APIRouter, Body, HTTPException
from starlette import status

from ..db import get_cursor

router = APIRouter()


# Cola de Validación IA: sugerencias pendientes de revisión por un analista.
@router.get("")
def listar():
    with get_cursor() as cur:
        cur.execute(
            """SELECT s.*, f.url, f.dominio, ti.nombre AS tipo_infraccion_nombre, ti.color_indicador
               FROM incidentes_sugeridos_ia s
               JOIN fuentes_noticias f ON f.id = s.fuente_id
               LEFT JOIN tipos_infraccion ti ON ti.id = s.tipo_infraccion_id
               WHERE s.estado = 'pendiente'
               ORDER BY s.creado_en DESC"""
        )
        return cur.fetchall()


@router.post("/{sugerencia_id}/rechazar", status_code=status.HTTP_204_NO_CONTENT)
def rechazar(sugerencia_id: str):
    with get_cursor() as cur:
        cur.execute("UPDATE incidentes_sugeridos_ia SET estado = 'rechazado' WHERE id = %s", (sugerencia_id,))


# Promueve la sugerencia a un incidente real (mismo flujo que "Registrar
# Incidente" desde una alerta de monitoreo). Si la IA no determinó un tipo
# de infracción, el analista debe indicarlo en el body.
@router.post("/{sugerencia_id}/aprobar")
def aprobar(sugerencia_id: str, body: dict = Body(default={})):
    tipo_infraccion_id_override = body.get("tipo_infraccion_id")

    with get_cursor() as cur:
        cur.execute(
            """SELECT s.*, ti.gravedad_sugerida
               FROM incidentes_sugeridos_ia s
               LEFT JOIN tipos_infraccion ti ON ti.id = s.tipo_infraccion_id
               WHERE s.id = %s AND s.estado = 'pendiente'""",
            (sugerencia_id,),
        )
        sugerencia = cur.fetchone()

    if not sugerencia:
        raise HTTPException(status_code=404, detail={"error": "Sugerencia no encontrada o ya procesada"})

    tipo_infraccion_id = tipo_infraccion_id_override or sugerencia.get("tipo_infraccion_id")
    if not tipo_infraccion_id:
        raise HTTPException(status_code=400, detail={"error": "Debe indicarse tipo_infraccion_id: la IA no pudo determinarlo"})

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO incidentes (tipo_infraccion_id, descripcion, gravedad, estado, fecha_deteccion)
               VALUES (%s, %s, %s, 'sospechoso', now())
               RETURNING id, codigo""",
            (
                tipo_infraccion_id,
                sugerencia.get("resumen") or sugerencia.get("titular"),
                sugerencia.get("gravedad_sugerida") or "medio",
            ),
        )
        incidente = cur.fetchone()

    with get_cursor() as cur:
        cur.execute(
            "UPDATE incidentes_sugeridos_ia SET estado = 'aprobado', incidente_id = %s WHERE id = %s",
            (incidente["id"], sugerencia_id),
        )

    return {"incidente": incidente}
