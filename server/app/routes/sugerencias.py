from fastapi import APIRouter, Body, HTTPException
from starlette import status

from ..db import ejecutar_sp, get_cursor

router = APIRouter()


# Cola de Validación IA: sugerencias pendientes de revisión por un analista.
@router.get("")
def listar():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_sugerencias_listar_pendientes()")
        return cur.fetchall()


@router.post("/{sugerencia_id}/rechazar", status_code=status.HTTP_204_NO_CONTENT)
def rechazar(sugerencia_id: str):
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_sugerencias_rechazar(%s)", (sugerencia_id,))


# Promueve la sugerencia a un incidente real (mismo flujo que "Registrar
# Incidente" desde una alerta de monitoreo). Si la IA no determinó un tipo
# de infracción, el analista debe indicarlo en el body.
@router.post("/{sugerencia_id}/aprobar")
def aprobar(sugerencia_id: str, body: dict = Body(default={})):
    tipo_infraccion_id_override = body.get("tipo_infraccion_id")

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_sugerencias_obtener_pendiente(%s)", (sugerencia_id,))
        sugerencia = cur.fetchone()

    if not sugerencia:
        raise HTTPException(status_code=404, detail={"error": "Sugerencia no encontrada o ya procesada"})

    tipo_infraccion_id = tipo_infraccion_id_override or sugerencia.get("tipo_infraccion_id")
    if not tipo_infraccion_id:
        raise HTTPException(status_code=400, detail={"error": "Debe indicarse tipo_infraccion_id: la IA no pudo determinarlo"})

    with get_cursor() as cur:
        ejecutar_sp(
            cur,
            "SELECT * FROM sp_incidentes_registrar_desde_sugerencia(%s, %s, %s)",
            (
                tipo_infraccion_id,
                sugerencia.get("resumen") or sugerencia.get("titular"),
                sugerencia.get("gravedad_sugerida") or "medio",
            ),
        )
        incidente = cur.fetchone()

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_sugerencias_aprobar_vincular(%s, %s)", (sugerencia_id, incidente["id"]))

    return {"incidente": incidente}
