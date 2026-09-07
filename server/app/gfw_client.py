"""Cliente mínimo de la 4Wings Report API de Global Fishing Watch, corriendo
en el mismo proceso (sin subproceso) para poder alimentar los modelos
entrenados con datos frescos, con resolución DIARIA por embarcación.

Ver scripts/sync_lambayeque.py y scripts/detectar_irregularidades.py para las
versiones CLI equivalentes (documentan las mismas limitaciones del dataset
público de GFW)."""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET_PRESENCIA = "public-global-presence:latest"
DATASET_ESFUERZO = "public-global-fishing-effort:latest"


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
