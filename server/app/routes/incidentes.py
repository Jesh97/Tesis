from fastapi import APIRouter, Body, HTTPException, Query

from ..db import ejecutar_sp, get_cursor

router = APIRouter()

# Alerta del mapa (MonitoringPage) -> tipo de infracción del catálogo. No hay
# un tipo "demora en puerto" exacto en tipos_infraccion, así que se usa el más
# cercano semánticamente (actividad sospechosa prolongada en alta mar).
NOMBRE_TIPO_INFRACCION_POR_ALERTA = {
    "zona_protegida": "Pesca en Zona Prohibida",
    "apagon_ais": "Pérdida de Señal AIS",
    "demora_puerto": "Encuentro Sospechoso en Alta Mar",
}


TIPOS_EMBARCACION_VALIDOS = {"pesca_artesanal", "pesca_industrial", "carga", "otro"}
GRAVEDADES_VALIDAS = {"alto", "medio", "bajo"}


@router.get("")
def listar(
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    gravedad: str | None = Query(default=None),
):
    # Validación de forma (no toca la BD): igual que antes, se hace en Python
    # para devolver el mismo mensaje de error de siempre antes de llamar a la
    # función almacenada, que ya recibe el tipo/gravedad tipados y validados.
    if tipo is not None and tipo not in TIPOS_EMBARCACION_VALIDOS:
        raise HTTPException(status_code=400, detail={"error": f'"tipo" inválido: {tipo}'})
    if gravedad is not None and gravedad not in GRAVEDADES_VALIDAS:
        raise HTTPException(status_code=400, detail={"error": f'"gravedad" inválida: {gravedad}'})

    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_incidentes_listar(%s, %s, %s, %s)", (desde, hasta, tipo, gravedad))
        rows = cur.fetchall()

    return [
        {
            "id": r["codigo"],
            "vessel": r["vessel"] or "Desconocido",
            "vesselCode": f"MMSI: {r['mmsi']}" if r["mmsi"] else (f"MAT: {r['matricula']}" if r["matricula"] else "Sin identificar"),
            "infraction": r["infraction"],
            "dateTime": r["fecha_deteccion"],
            "severity": r["severity"],
            "estado": r["estado"],
            "lat": r["latitud"],
            "lon": r["longitud"],
        }
        for r in rows
    ]


# Lista liviana de mmsi con incidente confirmado, para pintarlos de rojo en el mapa.
@router.get("/mmsi-con-incidente")
def mmsi_con_incidente():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_incidentes_mmsi_con_incidente()")
        rows = cur.fetchall()
    return [r["mmsi"] for r in rows]


# Lista liviana de mmsi con un incidente activo (no descartado), para dejar de
# mostrar/permitir registrar de nuevo una alerta de monitoreo (MonitoringPage)
# que ya fue reportada, incluso después de recargar el mapa.
@router.get("/mmsi-reportados")
def mmsi_reportados():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_incidentes_mmsi_reportados()")
        rows = cur.fetchall()
    return [r["mmsi"] for r in rows]


# Botón "Descartar" en la fila de un incidente (IncidentsTable).
@router.post("/{codigo}/descartar", status_code=204)
def descartar(codigo: str):
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_incidentes_descartar(%s)", (codigo,))


# Botón "Confirmar" en la fila de un incidente (IncidentsTable): el analista
# verificó la infracción y pasa el incidente de "sospechoso" a "confirmado"
# (recién ahí se resalta la embarcación en rojo en el mapa, ver
# mmsi_con_incidente arriba).
@router.post("/{codigo}/confirmar", status_code=204)
def confirmar(codigo: str):
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT sp_incidentes_confirmar(%s)", (codigo,))


# Catálogo para el formulario de "Reportar incidencia" (sidebar).
@router.get("/tipos-infraccion")
def tipos_infraccion():
    with get_cursor() as cur:
        ejecutar_sp(cur, "SELECT * FROM sp_tipos_infraccion_listar()")
        return cur.fetchall()


def _vincular_o_crear_embarcacion(
    cur,
    mmsi: str | None,
    vessel_name: str | None,
    bandera: str | None = None,
    gfw_vessel_type: str | None = None,
) -> str | None:
    ejecutar_sp(
        cur,
        "SELECT sp_embarcaciones_vincular_o_crear(%s, %s, %s, %s) AS id",
        (mmsi, vessel_name, bandera, gfw_vessel_type),
    )
    return cur.fetchone()["id"]


# "Registrar incidente" desde una alerta de monitoreo (AlertCard en el mapa,
# tipoAlerta fijo) o reporte manual desde el sidebar (tipoInfraccionId elegido
# a mano del catálogo -- para cuando el analista se entera por otra vía:
# llamada, denuncia, inspección).
@router.post("", status_code=201)
def registrar(body: dict = Body(...)):
    tipo_alerta = body.get("tipoAlerta")
    tipo_infraccion_id_manual = body.get("tipoInfraccionId")
    descripcion = body.get("descripcion")
    lat = body.get("lat")
    lon = body.get("lon")
    mmsi = body.get("mmsi")
    vessel_name = body.get("vessel")
    gravedad_manual = body.get("gravedad")
    fecha = body.get("fecha")  # ISO date opcional; None -> now()
    bandera = body.get("bandera")  # opcional: viene de "Buscar en GFW" en el formulario
    gfw_vessel_type = body.get("vesselType")

    if not isinstance(descripcion, str) or not descripcion.strip():
        raise HTTPException(status_code=400, detail={"error": 'Falta "descripcion"'})

    if not mmsi and not (isinstance(vessel_name, str) and vessel_name.strip()):
        raise HTTPException(status_code=400, detail={"error": 'Se requiere "mmsi" o "vessel"'})

    with get_cursor() as cur:
        if tipo_infraccion_id_manual:
            ejecutar_sp(cur, "SELECT * FROM sp_tipos_infraccion_obtener(%s)", (tipo_infraccion_id_manual,))
            tipo = cur.fetchone()
            if not tipo:
                raise HTTPException(status_code=400, detail={"error": '"tipoInfraccionId" no existe en el catálogo'})
            if gravedad_manual is not None and gravedad_manual not in GRAVEDADES_VALIDAS:
                raise HTTPException(status_code=400, detail={"error": f'"gravedad" inválida: {gravedad_manual}'})
            gravedad = gravedad_manual or tipo["gravedad_sugerida"]
        elif tipo_alerta in NOMBRE_TIPO_INFRACCION_POR_ALERTA:
            nombre_tipo = NOMBRE_TIPO_INFRACCION_POR_ALERTA[tipo_alerta]
            ejecutar_sp(cur, "SELECT * FROM sp_tipos_infraccion_obtener_por_nombre(%s)", (nombre_tipo,))
            tipo = cur.fetchone()
            if not tipo:
                raise HTTPException(status_code=500, detail={"error": f'No existe el tipo de infracción "{nombre_tipo}" en el catálogo'})
            gravedad = tipo["gravedad_sugerida"]
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": 'Se requiere "tipoInfraccionId" (reporte manual) o un "tipoAlerta" válido (alerta del mapa)'},
            )

        embarcacion_id = _vincular_o_crear_embarcacion(cur, mmsi, vessel_name, bandera, gfw_vessel_type)

        # La deduplicación (evitar duplicar el mismo problema -- p. ej. una
        # alerta de "Encuentro Sospechoso en Alta Mar" que sigue apareciendo
        # tras recargar el mapa) vive dentro de sp_incidentes_registrar.
        ejecutar_sp(
            cur,
            "SELECT * FROM sp_incidentes_registrar(%s, %s, %s, %s, %s, %s, %s)",
            (embarcacion_id, tipo["id"], descripcion.strip(), gravedad, lat, lon, fecha),
        )
        incidente = cur.fetchone()

    return {"incidente": incidente}
