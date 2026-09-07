"""
Calcula 2 de los 4 patrones de irregularidad usando SOLO datos de Global
Fishing Watch a los que este token sí tiene acceso (4Wings Report, dataset
"public-global-presence" -- presencia AIS cruda, no solo horas de pesca --,
en resolución DAILY). No requiere la Events API (bloqueada por permisos) ni
el dataset de SISESAT con el que se entrenó el modelo original.

  1. apagon_ais:    la embarcación deja de tener registros de presencia en la
                     zona monitoreada por varios días seguidos.
  2. demora_puerto:  la embarcación pasa varios días seguidos lejos (más de
                     PUERTO_RADIO_NM) de cualquier puerto peruano conocido.

LIMITACIÓN HONESTA: ambos son proxies, no equivalentes exactos a los eventos
oficiales de GFW:
  - "sin presencia en la zona" puede significar AIS apagado O que la
    embarcación simplemente navegó fuera del polígono monitoreado -- con un
    dataset acotado a una zona no se puede distinguir uno del otro.
  - "lejos de puerto" no confirma que no atracó en un puerto NO listado en
    PUERTOS_PERU (la lista es aproximada y no exhaustiva).
El patrón "transbordo" se excluye deliberadamente: requeriría saber si un
encuentro estaba autorizado, dato que vive en el registro pesquero peruano
(PRODUCE/SISESAT), no en GFW.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / "server" / ".env"
load_dotenv(ENV_FILE)

API_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET = "public-global-presence:latest"

# Coordenadas aproximadas de los puertos pesqueros peruanos más relevantes
# (mismos nombres que las columnas puerto_mas_cercano_* del dataset de
# entrenamiento). Solo para estimar distancia; no son datos oficiales del
# registro portuario.
PUERTOS_PERU = [
    ("BAYOVAR", -5.83, -81.11),
    ("CALLAO", -12.05, -77.15),
    ("CHANCAY", -11.57, -77.27),
    ("CHIMBOTE", -9.09, -78.60),
    ("HUACHO", -11.11, -77.62),
    ("HUARMEY", -10.07, -78.15),
    ("ILO", -17.65, -71.34),
    ("MATARANI", -17.00, -72.10),
    ("PISCO", -13.71, -76.20),
    ("PUERTO CHICAMA", -7.70, -79.44),
    ("SAN JUAN DE MARCONA", -15.35, -75.16),
    ("SAN NICOLAS", -15.27, -75.24),
    ("TALARA", -4.58, -81.27),
]

DEMORA_PUERTO_NM = 5.0  # radio alrededor de un puerto para considerar "en puerto"
# Una embarcación de paso (p.ej. un carguero cruzando mar abierto) puede
# aparecer 1-2 días y no volver -- eso no es un "apagón", es que nunca fue
# habitual de la zona. Solo se evalúan huecos/rachas en embarcaciones con
# presencia mínima suficiente para considerarlas "regulares" de la zona.
MIN_DIAS_PRESENCIA = 5
# La pesca artesanal/industrial peruana tiene vedas y pausas por clima: no
# pescar varios días seguidos es NORMAL, no sospechoso. Un umbral fijo (p.ej.
# "4 días sin señal") marcaba casi toda la flota. En vez de eso, se compara
# cada embarcación contra el resto de la flota consultada en ese mismo rango
# de fechas (percentil 90) -- igual que hacía el modelo original entrenado
# con SISESAT, que binarizaba por percentil de la propia población de train.
PERCENTIL_ANOMALIA = 0.90


def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    r_nm = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r_nm * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distancia_puerto_mas_cercano_nm(lat, lon):
    return min(haversine_nm(lat, lon, plat, plon) for _nombre, plat, plon in PUERTOS_PERU)


def obtener_presencia_diaria(token: str, desde: str, hasta: str, geojson: dict) -> list[dict]:
    params = {
        "spatial-resolution": "HIGH",
        "temporal-resolution": "DAILY",
        "group-by": "VESSEL_ID",
        "datasets[0]": DATASET,
        "date-range": f"{desde},{hasta}",
        "format": "JSON",
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(API_URL, headers=headers, params=params, json={"geojson": geojson}, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    registros = []
    for entry in data.get("entries", []):
        for _dataset_key, filas in entry.items():
            registros.extend(filas or [])
    return registros


def colapsar_por_dia(registros: list[dict]) -> list[dict]:
    """Con spatial-resolution=HIGH, GFW devuelve una fila por CELDA visitada ese
    día, no una fila por día -- un barco activo en varias celdas aparece
    repetido varias veces el mismo día. Se colapsa a una fila por (mmsi, date)
    quedándose con la celda de más horas (posición representativa del día) y
    sumando las horas totales."""
    por_dia: dict[tuple[str, str], dict] = {}
    for r in registros:
        mmsi = r.get("mmsi")
        if not mmsi:
            continue
        clave = (mmsi, r["date"])
        horas = r.get("hours") or 0
        actual = por_dia.get(clave)
        if actual is None or horas > actual.get("_horas_celda", 0):
            fila = dict(r)
            fila["_horas_celda"] = horas
            fila["_horas_totales_dia"] = (actual["_horas_totales_dia"] if actual else 0) + horas
            por_dia[clave] = fila
        else:
            actual["_horas_totales_dia"] += horas
    return list(por_dia.values())


def agrupar_por_embarcacion(registros: list[dict]) -> dict[str, list[dict]]:
    # Un carguero o tanquero de paso por mar abierto puede aparecer solo 1-2
    # días y no volver -- eso no es un apagón de AIS, nunca fue habitual de la
    # zona. Los patrones de esta app son sobre pesca, así que se descarta todo
    # lo que GFW no clasifique como FISHING.
    registros = [r for r in registros if r.get("vesselType") == "FISHING"]
    registros = colapsar_por_dia(registros)
    por_mmsi = defaultdict(list)
    for r in registros:
        por_mmsi[r["mmsi"]].append(r)
    for filas in por_mmsi.values():
        filas.sort(key=lambda r: r["date"])
    return por_mmsi


def mayor_hueco_dias(fechas: list[date]) -> int:
    if len(fechas) < 2:
        return 0
    return max((b - a).days for a, b in zip(fechas, fechas[1:]))


def racha_maxima_lejos_de_puerto(filas: list[dict]) -> int:
    racha = 0
    maxima = 0
    for fila in filas:
        dist = distancia_puerto_mas_cercano_nm(fila["lat"], fila["lon"])
        if dist > DEMORA_PUERTO_NM:
            racha += 1
            maxima = max(maxima, racha)
        else:
            racha = 0
    return maxima


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0
    ordenados = sorted(valores)
    idx = min(len(ordenados) - 1, int(round(p * (len(ordenados) - 1))))
    return ordenados[idx]


def analizar(desde: str, hasta: str, geojson: dict) -> list[dict]:
    token = os.getenv("GFW_API_TOKEN")
    if not token:
        raise SystemExit(f"Falta GFW_API_TOKEN en {ENV_FILE}")

    registros = obtener_presencia_diaria(token, desde, hasta, geojson)
    por_mmsi = agrupar_por_embarcacion(registros)

    # Solo se evalúan embarcaciones con presencia mínima ("regulares" de la
    # zona); de esas se calculan los umbrales relativos a la propia flota.
    candidatos = {mmsi: filas for mmsi, filas in por_mmsi.items() if len(filas) >= MIN_DIAS_PRESENCIA}

    metricas: dict[str, tuple[int, int]] = {}
    for mmsi, filas in candidatos.items():
        fechas = [datetime.strptime(f["date"], "%Y-%m-%d").date() for f in filas]
        metricas[mmsi] = (mayor_hueco_dias(fechas), racha_maxima_lejos_de_puerto(filas))

    if not metricas:
        return []

    umbral_hueco = percentil([h for h, _ in metricas.values()], PERCENTIL_ANOMALIA)
    umbral_racha = percentil([r for _, r in metricas.values()], PERCENTIL_ANOMALIA)

    resultados = []
    for mmsi, (hueco, racha_puerto) in metricas.items():
        apagon = hueco > umbral_hueco and hueco > 0
        demora = racha_puerto > umbral_racha and racha_puerto > 0
        if not apagon and not demora:
            continue

        ultima = candidatos[mmsi][-1]
        resultados.append({
            "mmsi": mmsi,
            "nombre": ultima.get("shipName") or "Desconocido",
            "flag": ultima.get("flag"),
            "lat": ultima["lat"],
            "lon": ultima["lon"],
            "apagonAis": {"detectado": apagon, "diasSinSenal": hueco, "umbralFlota": umbral_hueco} if apagon else None,
            "demoraPuerto": (
                {"detectado": demora, "diasLejosDePuerto": racha_puerto, "umbralFlota": umbral_racha}
                if demora
                else None
            ),
        })
    return resultados


def main():
    hoy = date.today()
    hace_una_semana = hoy - timedelta(days=7)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--desde", default=hace_una_semana.isoformat())
    parser.add_argument("--hasta", default=hoy.isoformat())
    parser.add_argument("--geojson", required=True, help="Polígono GeoJSON (string JSON) de la zona a analizar")
    args = parser.parse_args()

    geojson = json.loads(args.geojson)
    resultados = analizar(args.desde, args.hasta, geojson)
    print(json.dumps(resultados, ensure_ascii=False))


if __name__ == "__main__":
    main()
