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
