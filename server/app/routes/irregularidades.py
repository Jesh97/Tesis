from fastapi import APIRouter, HTTPException, Query

from ..db import get_cursor
from ..gfw import consultar_actividad_con_cache, consultar_gfw_con_cache, consultar_probabilidad_zona_protegida_con_cache

router = APIRouter()

DEMO_DESDE = "2023-01-01"
DEMO_HASTA = "2023-01-08"

# apagon_ais/demora_puerto se calculan sobre huecos/rachas de varios días:
# una semana no alcanza para que el percentil de la flota tenga sentido, así
# que esta ruta usa por defecto un rango de un mes (también sobreescribible
# con ?desde=&hasta=).
ACTIVIDAD_DEMO_DESDE = "2023-01-01"
ACTIVIDAD_DEMO_HASTA = "2023-02-01"


def zonas_criticas() -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, nombre, region, poligono FROM zonas
               WHERE es_critica AND poligono IS NOT NULL"""
        )
        return cur.fetchall()


# Patrón "zona_protegida": cualquier embarcación que el 4Wings Report de GFW
# reporte dentro del polígono de una zona marcada como crítica (geofencing
# directo -- la fuente de verdad). Además se le suma "probabilidadModelo": la
# salida del clasificador entrenado en scripts/entrenar_patrones.py, calculada
# solo con features indirectas (posición, vecinos, horas de pesca). Es una
# señal redundante, no un reemplazo -- ver gfw.consultar_probabilidad_zona_protegida_con_cache.
@router.get("/zona-protegida")
def zona_protegida(desde: str = Query(default=DEMO_DESDE), hasta: str = Query(default=DEMO_HASTA)):
    try:
        zonas = zonas_criticas()
        resultados = []
        for zona in zonas:
            try:
                barcos = consultar_gfw_con_cache(desde, hasta, f"zona:{zona['id']}", zona["poligono"])
                try:
                    probabilidades = consultar_probabilidad_zona_protegida_con_cache(desde, hasta, f"zona:{zona['id']}", zona["poligono"])
                except Exception as err:
                    print(f"[irregularidades/zona-protegida] modelo no disponible para zona {zona['id']}: {err}")
                    probabilidades = {}
                for barco in barcos:
                    barco["probabilidadModelo"] = probabilidades.get(barco.get("mmsi"))
                resultados.append({"zonaId": zona["id"], "zonaNombre": zona["nombre"], "region": zona["region"], "barcos": barcos, "error": None})
            except Exception as err:
                resultados.append({"zonaId": zona["id"], "zonaNombre": zona["nombre"], "region": zona["region"], "barcos": [], "error": str(err)})
        return {"desde": desde, "hasta": hasta, "zonas": resultados}
    except Exception as err:
        raise HTTPException(status_code=500, detail={"error": str(err)}) from err


# Patrones "apagon_ais" y "demora_puerto": calculados con los detectores
# entrenados en scripts/entrenar_patrones.py (datos/modelos_patrones_v9.joblib),
# alimentados con features reconstruidas desde presencia AIS + esfuerzo
# pesquero diario de GFW dentro de las zonas críticas (ver app/features.py
# para el detalle de qué se pudo y no se pudo reconstruir fielmente).
@router.get("/actividad")
def actividad(desde: str = Query(default=ACTIVIDAD_DEMO_DESDE), hasta: str = Query(default=ACTIVIDAD_DEMO_HASTA)):
    try:
        zonas = zonas_criticas()
        resultados = []
        for zona in zonas:
            try:
                barcos = consultar_actividad_con_cache(desde, hasta, f"zona:{zona['id']}", zona["poligono"])
                resultados.append({"zonaId": zona["id"], "zonaNombre": zona["nombre"], "region": zona["region"], "barcos": barcos, "error": None})
            except Exception as err:
                resultados.append({"zonaId": zona["id"], "zonaNombre": zona["nombre"], "region": zona["region"], "barcos": [], "error": str(err)})
        return {"desde": desde, "hasta": hasta, "zonas": resultados}
    except Exception as err:
        raise HTTPException(status_code=500, detail={"error": str(err)}) from err
