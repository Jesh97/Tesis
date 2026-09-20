from fastapi import APIRouter, Body, HTTPException
from starlette import status

from ..db import ejecutar_sp, get_cursor
from ..gfw import consultar_gfw_con_cache
from .incidentes import _vincular_o_crear_embarcacion

router = APIRouter()

# Bbox de todo el litoral peruano (a diferencia de LAMBAYEQUE_BBOX que usa el
# resto de la app): acá se busca la embarcación que la IA nombró en
# cualquier parte de la costa, no solo Lambayeque, porque un artículo puede
# describir un hecho en Paita, Paracas, la frontera con Chile, etc.
PERU_BBOX = {
    "type": "Polygon",
    "coordinates": [[
        [-84.0, -19.0], [-68.0, -19.0], [-68.0, -2.5], [-84.0, -2.5], [-84.0, -19.0],
    ]],
}

# Misma ventana ya verificada con datos reales que usa el resto de la app
# (ver RANGO_POR_DEFECTO en MonitoringPage.tsx) -- GFW tiene meses de rezago,
# así que una ventana "relativa a hoy" casi siempre viene vacía.
_RESOLVER_DESDE = "2023-06-01"
_RESOLVER_HASTA = "2023-09-01"


def _resolver_embarcacion_por_nombre(nombre: str) -> dict | None:
    """Busca en GFW (todo el litoral peruano) la embarcación que la IA
    nombró en el artículo, para vincularla al aprobar en vez de dejar el
    incidente en "Desconocido". No es un match garantizado: GFW puede no
    tener a esa embarcación en esta ventana, o el nombre puede venir con
    variaciones -- si no se encuentra, el incidente queda sin embarcación
    vinculada, igual que antes (nunca se inventa una identidad)."""
    try:
        barcos = consultar_gfw_con_cache(_RESOLVER_DESDE, _RESOLVER_HASTA, "peru-nacional", PERU_BBOX)
    except Exception as err:
        print(f"[sugerencias/aprobar] no se pudo consultar GFW para resolver embarcación: {err}")
        return None
    nombre_min = nombre.lower()
    return next((b for b in barcos if nombre_min in (b.get("nombre") or "").lower()), None)


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

    # Intenta vincular la embarcación real en vez de dejar el incidente en
    # "Desconocido": primero por nombre contra GFW (da un mmsi verificado);
    # si eso no encuentra nada, por la matrícula que haya reportado el
    # artículo directamente (identidad igual de válida que el mmsi -- ver
    # chk_embarcacion_tiene_identidad en schema.sql -- pero sin verificar
    # contra una fuente externa, a diferencia del match de GFW).
    embarcacion_id = None
    nombre_detectado = sugerencia.get("embarcacion_detectada")
    matricula_detectada = sugerencia.get("matricula_detectada")
    mmsi = None
    bandera = None
    gfw_vessel_type = None
    nombre_final = nombre_detectado

    if nombre_detectado:
        encontrado = _resolver_embarcacion_por_nombre(nombre_detectado)
        if encontrado:
            mmsi = encontrado.get("mmsi")
            bandera = encontrado.get("flag")
            gfw_vessel_type = encontrado.get("vesselType")
            nombre_final = encontrado.get("nombre") or nombre_detectado

    if mmsi or matricula_detectada:
        with get_cursor() as cur:
            embarcacion_id = _vincular_o_crear_embarcacion(
                cur, mmsi, nombre_final, bandera, gfw_vessel_type, matricula_detectada
            )

    with get_cursor() as cur:
        ejecutar_sp(
            cur,
            "SELECT * FROM sp_incidentes_registrar_desde_sugerencia(%s, %s, %s, %s, %s, %s)",
            (
                tipo_infraccion_id,
                sugerencia.get("resumen") or sugerencia.get("titular"),
                sugerencia.get("gravedad_sugerida") or "medio",
                embarcacion_id,
                sugerencia.get("fecha_publicacion"),
                nombre_detectado,
            ),
        )
        incidente = cur.fetchone()

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_sugerencias_aprobar_vincular(%s, %s)", (sugerencia_id, incidente["id"]))

    return {"incidente": incidente}
