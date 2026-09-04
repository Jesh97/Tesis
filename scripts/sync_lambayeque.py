"""
Consulta el esfuerzo pesquero de Global Fishing Watch frente a la costa de
Lambayeque. Dos modos:

  - Por defecto: guarda (upsert) los resultados en Postgres
    (embarcaciones + esfuerzo_pesquero_gfw). Requiere DATABASE_URL.
  - Con --json: solo imprime los barcos como JSON en stdout y NO toca la
    base de datos — útil mientras no haya Postgres configurado. Es el modo
    que usa server/src/routes/embarcaciones.ts para servirle datos en vivo
    al mapa de Monitoreo del frontend.

Uso:
    python scripts/sync_lambayeque.py
    python scripts/sync_lambayeque.py --desde 2023-01-01 --hasta 2023-01-08
    python scripts/sync_lambayeque.py --json --desde 2023-01-01 --hasta 2023-01-08

Variables de entorno (se leen de server/.env):
    GFW_API_TOKEN   token de Global Fishing Watch (siempre requerido)
    DATABASE_URL    cadena de conexión de Postgres (solo si no se usa --json)
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / "server" / ".env"
load_dotenv(ENV_FILE)

API_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET = "public-global-fishing-effort:latest"

# Cobertura aproximada del mar frente a Lambayeque — coincide con el
# polígono de "jurisdicción marítima" dibujado en MapView.tsx del frontend.
LAMBAYEQUE_BBOX = [-81.6, -7.15, -79.75, -6.3]  # lon_min, lat_min, lon_max, lat_max


def construir_geojson_bbox(bbox: list[float]) -> dict:
    lon_min, lat_min, lon_max, lat_max = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon_min, lat_min],
            [lon_max, lat_min],
            [lon_max, lat_max],
            [lon_min, lat_max],
            [lon_min, lat_min],
        ]],
    }


def obtener_barcos_lambayeque(token: str, desde: str, hasta: str) -> list[dict]:
    params = {
        # HIGH = celdas de ~0.01° (~1 km). LOW (~0.1°, ~11 km) agrupa demasiados
        # barcos en muy pocas coordenadas y se ve como una rejilla irreal en el mapa.
        "spatial-resolution": "HIGH",
        "temporal-resolution": "ENTIRE",
        "group-by": "VESSEL_ID",
        "datasets[0]": DATASET,
        "date-range": f"{desde},{hasta}",
        "format": "JSON",
    }
    body = {"geojson": construir_geojson_bbox(LAMBAYEQUE_BBOX)}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(API_URL, headers=headers, params=params, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    barcos = []
    for entry in data.get("entries", []):
        for _dataset_key, registros in entry.items():
            # GFW devuelve null (no una lista vacía) cuando no hay datos
            # para ese dataset en el rango pedido.
            barcos.extend(registros or [])
    return barcos


def vacio_a_none(valor):
    return valor if valor not in (None, "") else None


def upsert_embarcacion(cur, barco: dict) -> str | None:
    vessel_id = vacio_a_none(barco.get("vesselId"))
    if not vessel_id:
        return None

    tipo = "pesca_industrial" if (barco.get("vesselType") or "").upper() == "FISHING" else "otro"
    cur.execute(
        """
        INSERT INTO embarcaciones (nombre, mmsi, imo, gfw_vessel_id, bandera, tipo, gfw_vessel_type, gfw_gear_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (gfw_vessel_id) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            ultima_transmision_ais = now()
        RETURNING id
        """,
        (
            barco.get("shipName") or "Desconocido",
            vacio_a_none(barco.get("mmsi")),
            vacio_a_none(barco.get("imo")),
            vessel_id,
            vacio_a_none(barco.get("flag")),
            tipo,
            (barco.get("vesselType") or "").lower() or None,
            (barco.get("geartype") or "").lower() or None,
        ),
    )
    return cur.fetchone()[0]


def upsert_esfuerzo(cur, barco: dict, embarcacion_id: str | None) -> None:
    rango_desde, rango_hasta = barco["date"].split(",")
    cur.execute(
        """
        INSERT INTO esfuerzo_pesquero_gfw
            (embarcacion_id, gfw_vessel_id, mmsi, imo, callsign, ship_name, flag, vessel_type, geartype, dataset,
             rango_desde, rango_hasta, entry_timestamp, exit_timestamp, primera_transmision_ais,
             ultima_transmision_ais, horas, latitud, longitud, payload_raw)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (gfw_vessel_id, entry_timestamp, exit_timestamp, latitud, longitud)
        DO UPDATE SET horas = EXCLUDED.horas
        """,
        (
            embarcacion_id,
            vacio_a_none(barco.get("vesselId")),
            vacio_a_none(barco.get("mmsi")),
            vacio_a_none(barco.get("imo")),
            vacio_a_none(barco.get("callsign")),
            barco.get("shipName"),
            vacio_a_none(barco.get("flag")),
            barco.get("vesselType"),
            barco.get("geartype"),
            barco.get("dataset"),
            rango_desde,
            rango_hasta,
            barco.get("entryTimestamp"),
            barco.get("exitTimestamp"),
            vacio_a_none(barco.get("firstTransmissionDate")),
            vacio_a_none(barco.get("lastTransmissionDate")),
            barco.get("hours"),
            barco.get("lat"),
            barco.get("lon"),
            json.dumps(barco, ensure_ascii=False),
        ),
    )


def a_json(barco: dict) -> dict:
    """Forma que espera el frontend (ver LambayequeVessel en useLambayequeVessels.ts)."""
    return {
        "embarcacionId": None,
        "nombre": barco.get("shipName") or "Desconocido",
        "mmsi": vacio_a_none(barco.get("mmsi")),
        "flag": vacio_a_none(barco.get("flag")),
        "vesselType": vacio_a_none(barco.get("vesselType")),
        "lat": barco.get("lat"),
        "lon": barco.get("lon"),
        "horas": barco.get("hours", 0),
    }


def main():
    hoy = date.today()
    hace_una_semana = hoy - timedelta(days=7)

    parser = argparse.ArgumentParser(description="Consulta embarcaciones GFW frente a Lambayeque")
    parser.add_argument("--desde", default=hace_una_semana.isoformat())
    parser.add_argument("--hasta", default=hoy.isoformat())
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime los barcos como JSON en stdout y no guarda nada en la base de datos",
    )
    args = parser.parse_args()

    # Los mensajes informativos van a stderr en modo --json, para que stdout
    # quede como JSON puro (así lo puede parsear el backend Node).
    log = (lambda msg: print(msg, file=sys.stderr)) if args.json else print

    token = os.getenv("GFW_API_TOKEN")
    if not token:
        raise SystemExit(f"Falta GFW_API_TOKEN en {ENV_FILE}")

    log(f"Consultando GFW frente a Lambayeque ({args.desde} a {args.hasta})...")
    barcos = obtener_barcos_lambayeque(token, args.desde, args.hasta)
    log(f"Barcos detectados: {len(barcos)}")

    if not barcos:
        log(
            "Sin resultados para ese rango. El dataset público de GFW "
            "(public-global-fishing-effort) suele tener varios meses de rezago "
            "respecto a hoy: prueba con un rango más antiguo, por ejemplo:\n"
            "  --desde 2023-01-01 --hasta 2023-01-08"
        )

    if args.json:
        print(json.dumps([a_json(b) for b in barcos], ensure_ascii=False))
        return

    if not barcos:
        return

    import psycopg2  # importado aquí para no exigirlo en modo --json

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit(f"Falta DATABASE_URL en {ENV_FILE}")

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for barco in barcos:
                    embarcacion_id = upsert_embarcacion(cur, barco)
                    upsert_esfuerzo(cur, barco, embarcacion_id)
        print(f"Sincronizados {len(barcos)} registros en Postgres.")
    finally:
        conn.close()

    for b in barcos:
        print(
            f"- {b.get('shipName') or '(sin nombre)':<25} "
            f"MMSI={b.get('mmsi', ''):<10} "
            f"Bandera={b.get('flag', ''):<4} "
            f"Tipo={b.get('vesselType', ''):<10} "
            f"Horas={b.get('hours', 0):.2f}  "
            f"Pos=({b.get('lat')}, {b.get('lon')})"
        )


if __name__ == "__main__":
    main()
