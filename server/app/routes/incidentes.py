from fastapi import APIRouter, Body, HTTPException, Query
from psycopg2 import errors as pg_errors

from ..db import get_cursor

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
    condiciones = []
    parametros: list = []

    if desde:
        condiciones.append("i.fecha_deteccion >= %s")
        parametros.append(desde)
    if hasta:
        condiciones.append("i.fecha_deteccion < (%s::date + interval '1 day')")
        parametros.append(hasta)
    if tipo:
        if tipo not in TIPOS_EMBARCACION_VALIDOS:
            raise HTTPException(status_code=400, detail={"error": f'"tipo" inválido: {tipo}'})
        condiciones.append("e.tipo = %s")
        parametros.append(tipo)
    if gravedad:
        if gravedad not in GRAVEDADES_VALIDAS:
            raise HTTPException(status_code=400, detail={"error": f'"gravedad" inválida: {gravedad}'})
        condiciones.append("i.gravedad = %s")
        parametros.append(gravedad)

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    with get_cursor() as cur:
        cur.execute(
            f"""SELECT
                 i.codigo,
                 e.nombre AS vessel,
                 e.mmsi,
                 e.matricula,
                 i.descripcion AS infraction,
                 i.fecha_deteccion,
                 i.gravedad AS severity,
                 i.estado,
                 i.latitud,
                 i.longitud
               FROM incidentes i
               LEFT JOIN embarcaciones e ON e.id = i.embarcacion_id
               {where}
               ORDER BY i.fecha_deteccion DESC""",
            parametros,
        )
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
        cur.execute(
            """SELECT DISTINCT e.mmsi
               FROM incidentes i
               JOIN embarcaciones e ON e.id = i.embarcacion_id
               WHERE e.mmsi IS NOT NULL AND i.estado = 'confirmado'"""
        )
        rows = cur.fetchall()
    return [r["mmsi"] for r in rows]


# Botón "Descartar" en la fila de un incidente (IncidentsTable).
@router.post("/{codigo}/descartar", status_code=204)
def descartar(codigo: str):
    with get_cursor() as cur:
        cur.execute("UPDATE incidentes SET estado = 'descartado' WHERE codigo = %s", (codigo,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail={"error": f'No existe el incidente "{codigo}"'})


# Catálogo para el formulario de "Reportar incidencia" (sidebar).
@router.get("/tipos-infraccion")
def tipos_infraccion():
    with get_cursor() as cur:
        cur.execute("SELECT id, nombre, gravedad_sugerida FROM tipos_infraccion ORDER BY nombre")
        return cur.fetchall()


def _vincular_o_crear_embarcacion(cur, mmsi: str | None, vessel_name: str | None) -> str | None:
    if not mmsi:
        return None
    mmsi_str = str(mmsi)[:9]
    cur.execute("SELECT id FROM embarcaciones WHERE mmsi = %s", (mmsi_str,))
    fila = cur.fetchone()
    if fila:
        return fila["id"]
    try:
        cur.execute(
            "INSERT INTO embarcaciones (nombre, mmsi) VALUES (%s, %s) RETURNING id",
            (vessel_name or "Desconocido", mmsi_str),
        )
        return cur.fetchone()["id"]
    except pg_errors.UniqueViolation:
        return None  # carrera con otra inserción concurrente del mismo mmsi: se sigue sin vincular


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

    if not isinstance(descripcion, str) or not descripcion.strip():
        raise HTTPException(status_code=400, detail={"error": 'Falta "descripcion"'})

    with get_cursor() as cur:
        if tipo_infraccion_id_manual:
            cur.execute(
                "SELECT id, gravedad_sugerida FROM tipos_infraccion WHERE id = %s",
                (tipo_infraccion_id_manual,),
            )
            tipo = cur.fetchone()
            if not tipo:
                raise HTTPException(status_code=400, detail={"error": '"tipoInfraccionId" no existe en el catálogo'})
            if gravedad_manual is not None and gravedad_manual not in GRAVEDADES_VALIDAS:
                raise HTTPException(status_code=400, detail={"error": f'"gravedad" inválida: {gravedad_manual}'})
            gravedad = gravedad_manual or tipo["gravedad_sugerida"]
        elif tipo_alerta in NOMBRE_TIPO_INFRACCION_POR_ALERTA:
            nombre_tipo = NOMBRE_TIPO_INFRACCION_POR_ALERTA[tipo_alerta]
            cur.execute("SELECT id, gravedad_sugerida FROM tipos_infraccion WHERE nombre = %s", (nombre_tipo,))
            tipo = cur.fetchone()
            if not tipo:
                raise HTTPException(status_code=500, detail={"error": f'No existe el tipo de infracción "{nombre_tipo}" en el catálogo'})
            gravedad = tipo["gravedad_sugerida"]
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": 'Se requiere "tipoInfraccionId" (reporte manual) o un "tipoAlerta" válido (alerta del mapa)'},
            )

        embarcacion_id = _vincular_o_crear_embarcacion(cur, mmsi, vessel_name)

        cur.execute(
            """INSERT INTO incidentes (embarcacion_id, tipo_infraccion_id, descripcion, gravedad, estado, latitud, longitud, fecha_deteccion)
               VALUES (%s, %s, %s, %s, 'sospechoso', %s, %s, COALESCE(%s::timestamptz, now()))
               RETURNING id, codigo""",
            (embarcacion_id, tipo["id"], descripcion.strip(), gravedad, lat, lon, fecha),
        )
        incidente = cur.fetchone()

    return {"incidente": incidente}
