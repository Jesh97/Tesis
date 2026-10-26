"""Cliente mínimo de la 4Wings Report API de Global Fishing Watch, corriendo
en el mismo proceso (sin subproceso) para poder alimentar los modelos
entrenados con datos frescos, con resolución DIARIA por embarcación.

Ver scripts/sync_lambayeque.py para la versión CLI equivalente (documenta las
mismas limitaciones del dataset público de GFW)."""
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET_PRESENCIA = "public-global-presence:latest"
DATASET_ESFUERZO = "public-global-fishing-effort:latest"

# Events API (a diferencia de 4Wings): visitas a puerto reales, no una
# aproximación por distancia a costa. Contradice el supuesto documentado en
# features.py ("Events API sin acceso") -- se verificó en vivo que el token
# actual sí tiene acceso (probado 2026-09-26 contra public-global-port-visits,
# -encounters, -loitering y -fishing-events, las 4 devuelven 200).
EVENTS_API_URL = "https://gateway.api.globalfishingwatch.org/v3/events"
DATASET_VISITAS_PUERTO = "public-global-port-visits-events:latest"

# Reutiliza la conexión TCP/TLS entre llamadas (este cliente corre en el
# mismo proceso del servidor durante toda su vida) en vez de que cada
# requests.get/post abra una conexión nueva.
_session = requests.Session()

# GFW permite UN solo reporte de 4Wings a la vez por token (mensaje literal
# del 429: "Your application token is not currently enabled to perform more
# than one concurrent report", verificado 2026-10-24). Las precargas de
# fondo (irregularidades, tendencias, histórico) corren en hilos paralelos
# del mismo proceso, así que se serializan acá: cada consulta espera su
# turno en vez de recibir un 429 inmediato.
lock_reporte_4wings = threading.Lock()


def obtener_ultima_visita_puerto(vessel_id: str) -> dict | None:
    """Última visita a puerto (real, de la Events API) para un vessel_id DE
    GFW (no el mmsi -- son identificadores distintos). None si esta
    embarcación no tiene ninguna visita a puerto registrada en el dataset
    público."""
    token = os.getenv("GFW_API_TOKEN")
    if not token:
        raise RuntimeError("Falta GFW_API_TOKEN")

    params = {
        "datasets[0]": DATASET_VISITAS_PUERTO,
        "vessels[0]": vessel_id,
        # Rango amplio a propósito: no se sabe de antemano cuándo fue la
        # última visita, y "sort" + "limit=1" hacen que el costo real de la
        # consulta no dependa del ancho del rango.
        "start-date": "2012-01-01",
        "end-date": datetime.now(timezone.utc).date().isoformat(),
        "sort": "-start",
        "limit": 1,
        "offset": 0,
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = _session.get(EVENTS_API_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    entradas = resp.json().get("entries", [])
    if not entradas:
        return None

    visita = entradas[0].get("port_visit") or {}
    ancla = visita.get("endAnchorage") or visita.get("startAnchorage") or {}
    return {
        "puerto": ancla.get("name"),
        # lat/lon del ancla (no necesariamente uno de los 13 puertos
        # oficiales de PUERTOS_PERU -- GFW reconoce anclas mucho más finas,
        # ver UMBRAL_ZONA_NO_AUTORIZADA_NM en features.py): permite calcular
        # qué tan lejos quedó del puerto oficial más cercano.
        "lat": ancla.get("lat"),
        "lon": ancla.get("lon"),
        "fin": entradas[0].get("end"),
        "duracion_horas": visita.get("durationHrs"),
    }


def _consultar(
    dataset: str,
    desde: str,
    hasta: str,
    geojson: dict,
    resolucion: dict | None = None,
    timeout: int = 60,
    reintentos_429: int = 0,
) -> list[dict]:
    token = os.getenv("GFW_API_TOKEN")
    if not token:
        raise RuntimeError("Falta GFW_API_TOKEN")

    params = {
        **(resolucion or {"spatial-resolution": "HIGH", "temporal-resolution": "DAILY"}),
        "group-by": "VESSEL_ID",
        "datasets[0]": dataset,
        "date-range": f"{desde},{hasta}",
        "format": "JSON",
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for intento in range(reintentos_429 + 1):
        with lock_reporte_4wings:
            resp = _session.post(API_URL, headers=headers, params=params, json={"geojson": geojson}, timeout=timeout)
        if resp.status_code != 429 or intento == reintentos_429:
            break
        time.sleep(_ESPERA_429_SEGUNDOS * (intento + 1))
    resp.raise_for_status()
    data = resp.json()

    registros = []
    for entry in data.get("entries", []):
        for _clave, filas in entry.items():
            registros.extend(filas or [])
    return registros


def obtener_presencia_diaria(desde: str, hasta: str, geojson: dict) -> list[dict]:
    """Presencia AIS cruda por día (dataset public-global-presence)."""
    return _consultar(DATASET_PRESENCIA, desde, hasta, geojson)


def obtener_esfuerzo_diario(desde: str, hasta: str, geojson: dict) -> list[dict]:
    """Horas de pesca aparente por día (dataset public-global-fishing-effort)."""
    return _consultar(DATASET_ESFUERZO, desde, hasta, geojson)


# Vista "Tendencias" (comportamiento mes a mes): un año entero de una sola vez
# con resolución MENSUAL. Las respuestas son bastante más pesadas que las
# diarias de arriba (un año completo del bbox de Lambayeque), de ahí el
# timeout más largo.
#
# Aunque lock_reporte_4wings serializa las consultas de este proceso, GFW igual
# puede responder 429 si OTRO proceso usa el mismo token a la vez (p.ej. dos
# servidores de desarrollo levantados, o scripts/sync_lambayeque.py), así
# que estas consultas se reintentan con espera creciente.
_TIMEOUT_MENSUAL = 180
_REINTENTOS_429_MENSUAL = 4
_ESPERA_429_SEGUNDOS = 10


def obtener_presencia_mensual(desde: str, hasta: str, geojson: dict) -> list[dict]:
    """Presencia AIS por embarcación y mes, agregada sobre todo el polígono
    (spatial-aggregation): sin celdas, una fila por barco/mes. Verificado en
    vivo (2026-10-24) que da los mismos totales que la versión por celdas
    pero con una respuesta ~10x más chica (~2MB vs ~21MB por año)."""
    resolucion = {"spatial-aggregation": "true", "temporal-resolution": "MONTHLY"}
    return _consultar(DATASET_PRESENCIA, desde, hasta, geojson, resolucion, _TIMEOUT_MENSUAL, _REINTENTOS_429_MENSUAL)


def obtener_esfuerzo_mensual(desde: str, hasta: str, geojson: dict) -> list[dict]:
    """Horas de pesca aparente por embarcación, mes y celda de ~0.1° (LOW):
    las celdas alimentan el mapa de calor mensual, no hace falta la
    resolución de ~1km (HIGH) del mapa de monitoreo para eso."""
    resolucion = {"spatial-resolution": "LOW", "temporal-resolution": "MONTHLY"}
    return _consultar(DATASET_ESFUERZO, desde, hasta, geojson, resolucion, _TIMEOUT_MENSUAL, _REINTENTOS_429_MENSUAL)


def obtener_presencia_mes(desde: str, hasta: str, geojson: dict) -> list[dict]:
    """Presencia AIS de TODAS las embarcaciones (no solo pesqueras) en el
    rango, por celda HIGH (~1km) y sin desglose temporal -- alimenta la vista
    "Histórico". Para un mes del bbox de Lambayeque son ~18MB y ~37k filas
    (verificado 2026-10-24), de ahí que se agrupe por barco antes de cachear."""
    resolucion = {"spatial-resolution": "HIGH", "temporal-resolution": "ENTIRE"}
    return _consultar(DATASET_PRESENCIA, desde, hasta, geojson, resolucion, _TIMEOUT_MENSUAL, _REINTENTOS_429_MENSUAL)


def obtener_esfuerzo_mes(desde: str, hasta: str, geojson: dict) -> list[dict]:
    """Igual que obtener_presencia_mes pero con el dataset de pesca aparente."""
    resolucion = {"spatial-resolution": "HIGH", "temporal-resolution": "ENTIRE"}
    return _consultar(DATASET_ESFUERZO, desde, hasta, geojson, resolucion, _TIMEOUT_MENSUAL, _REINTENTOS_429_MENSUAL)
