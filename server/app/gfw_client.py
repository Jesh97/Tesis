"""Cliente mínimo de la 4Wings Report API de Global Fishing Watch, corriendo
en el mismo proceso (sin subproceso) para poder alimentar los modelos
entrenados con datos frescos, con resolución DIARIA por embarcación.

Ver scripts/sync_lambayeque.py para la versión CLI equivalente (documenta las
mismas limitaciones del dataset público de GFW)."""
import os
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
    resp = requests.get(EVENTS_API_URL, headers=headers, params=params, timeout=30)
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


def _consultar(dataset: str, desde: str, hasta: str, geojson: dict) -> list[dict]:
    token = os.getenv("GFW_API_TOKEN")
    if not token:
        raise RuntimeError("Falta GFW_API_TOKEN")

    params = {
        "spatial-resolution": "HIGH",
        "temporal-resolution": "DAILY",
        "group-by": "VESSEL_ID",
        "datasets[0]": dataset,
        "date-range": f"{desde},{hasta}",
        "format": "JSON",
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(API_URL, headers=headers, params=params, json={"geojson": geojson}, timeout=60)
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
