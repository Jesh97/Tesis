from fastapi import APIRouter, HTTPException, Query

from ..gfw import consultar_gfw_con_cache

router = APIRouter()

# El dataset público de esfuerzo pesquero de GFW tiene varios meses de
# rezago: "hoy - 7 días" casi siempre devuelve 0 resultados, así que este
# rango solo evita eso. NO garantiza mostrar una embarcación en rojo (con
# incidente confirmado): los 28 incidentes de cargar_incidentes_csv.py son de
# la flota china de pesca a distancia detectada en TODA la costa peruana
# (Callao, Chimbote, Paita...), ninguno específicamente dentro de la
# jurisdicción de Lambayeque a la que ahora se acotó el bbox por defecto (ver
# LAMBAYEQUE_BBOX en scripts/sync_lambayeque.py) — se puede sobrescribir con
# ?desde=&hasta= en la query.
DEMO_DESDE = "2023-05-06"
DEMO_HASTA = "2023-05-13"


@router.get("/gfw/lambayeque")
def gfw_lambayeque(desde: str = Query(default=DEMO_DESDE), hasta: str = Query(default=DEMO_HASTA)):
    try:
        barcos = consultar_gfw_con_cache(desde, hasta, "lambayeque")
    except Exception as err:
        raise HTTPException(status_code=502, detail={"error": str(err)}) from err
    return {"desde": desde, "hasta": hasta, "total": len(barcos), "barcos": barcos}


def _mapear_tipo(vessel_type: str | None) -> str:
    return "pesca_industrial" if (vessel_type or "").upper() == "FISHING" else "otro"


# Botón "Buscar en GFW" del formulario "Reportar Incidencia" (sidebar y
# AlertCard): a partir del mmsi o el nombre que el analista ya escribió a
# mano, busca la embarcación en el mismo dataset de GFW que alimenta el mapa
# para traer su posición y datos adicionales (bandera, tipo) sin que el
# analista tenga que ubicarla manualmente.
@router.get("/buscar")
def buscar(mmsi: str | None = Query(default=None), nombre: str | None = Query(default=None)):
    mmsi = (mmsi or "").strip()
    nombre = (nombre or "").strip()
    if not mmsi and not nombre:
        raise HTTPException(status_code=400, detail={"error": 'Se requiere "mmsi" o "nombre"'})

    try:
        barcos = consultar_gfw_con_cache(DEMO_DESDE, DEMO_HASTA, "lambayeque")
    except Exception as err:
        raise HTTPException(status_code=502, detail={"error": str(err)}) from err

    encontrado = None
    if mmsi:
        encontrado = next((b for b in barcos if b.get("mmsi") == mmsi), None)
    if not encontrado and nombre:
        nombre_min = nombre.lower()
        encontrado = next((b for b in barcos if nombre_min in (b.get("nombre") or "").lower()), None)

    if not encontrado:
        return {"encontrado": False}

    return {
        "encontrado": True,
        "barco": {
            "nombre": encontrado.get("nombre"),
            "mmsi": encontrado.get("mmsi"),
            "flag": encontrado.get("flag"),
            "vesselType": encontrado.get("vesselType"),
            "tipo": _mapear_tipo(encontrado.get("vesselType")),
            "lat": encontrado.get("lat"),
            "lon": encontrado.get("lon"),
        },
    }
