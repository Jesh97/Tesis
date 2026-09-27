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

# Cobertura por defecto cuando no se pasa --geojson: la jurisdicción marítima
# de la región Lambayeque completa (no solo el puerto de Pimentel puntual, ni
# todo el Perú) -- objetivo general de la tesis. Cubre la costa de Lambayeque
# (aprox. límite con Piura al norte hasta límite con La Libertad al sur) más
# mar adentro, porque las embarcaciones con incidentes confirmados (ver
# cargar_incidentes_csv.py) operan en alta mar/EEZ, no solo en la bahía.
# Aproximado a partir de la extensión geográfica de la región -- no es el
# límite oficial de jurisdicción de la Capitanía de Puerto (DICAPI).
#
# lon_min = -84.5 (no -83.5) a propósito: verificado con
# features._distancia_costa_nm que la esquina más lejana del bbox con
# -83.5 solo llegaba a ~165mn de costa -- nunca alcanzaba el límite real de
# las 200mn de la ZEE, así que el detector "cruce_frontera_zee"
# (server/app/features.py) y el resaltado del mapa (MapView.tsx) nunca
# podían dispararse con datos reales por más flota de altura que hubiera.
# Con -84.5 el borde oeste del bbox queda entre ~203 y ~218mn de costa según
# la latitud -- justo dentro de la franja de +-20mn alrededor de las 200mn
# que usan ambos detectores.
LAMBAYEQUE_BBOX = [-84.5, -7.2, -79.6, -6.0]  # lon_min, lat_min, lon_max, lat_max


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


def obtener_barcos_en_zona(token: str, desde: str, hasta: str, geojson: dict) -> list[dict]:
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
    body = {"geojson": geojson}
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


def agrupar_por_embarcacion(barcos: list[dict]) -> list[dict]:
    """GFW devuelve una fila por (embarcación, celda) visitada en el rango
    -- con resolución ENTIRE eso significa que un mismo barco que pescó en
    varios puntos durante los 3 meses del rango por defecto aparece repetido
    varias veces (mismo mmsi, distinta posición). Antes de esto el mapa lo
    dibujaba así: N puntos por barco en vez de uno. Acá se agrupa por
    identidad real (vesselId, o mmsi si no hay vesselId) sumando las horas de
    todas sus celdas, y se deja la posición de la celda donde más pescó (su
    caladero principal) como posición representativa -- no la primera fila
    ni un promedio, que podría caer en un punto donde el barco nunca estuvo."""
    grupos: dict[str, list[dict]] = {}
    for barco in barcos:
        clave = vacio_a_none(barco.get("vesselId")) or vacio_a_none(barco.get("mmsi")) or f"sin-id:{barco.get('shipName')}:{barco.get('flag')}"
        grupos.setdefault(clave, []).append(barco)

    agrupados = []
    for filas in grupos.values():
        principal = max(filas, key=lambda f: f.get("hours") or 0)
        agrupados.append({**principal, "hours": sum(f.get("hours") or 0 for f in filas)})
    return agrupados


def a_json(barco: dict) -> dict:
    """Forma que espera el frontend (ver LambayequeVessel en useLambayequeVessels.ts)."""
    return {
        "embarcacionId": None,
        "vesselId": vacio_a_none(barco.get("vesselId")),
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

    parser = argparse.ArgumentParser(description="Consulta embarcaciones GFW en la jurisdicción marítima de Lambayeque (o en un polígono arbitrario)")
    parser.add_argument("--desde", default=hace_una_semana.isoformat())
    parser.add_argument("--hasta", default=hoy.isoformat())
    parser.add_argument(
        "--geojson",
        default=None,
        help="Polígono GeoJSON (string JSON) a consultar; por defecto usa el bbox de la jurisdicción de Lambayeque",
    )
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

    geojson = json.loads(args.geojson) if args.geojson else construir_geojson_bbox(LAMBAYEQUE_BBOX)

    log(f"Consultando GFW ({args.desde} a {args.hasta})...")
    barcos = obtener_barcos_en_zona(token, args.desde, args.hasta, geojson)
    barcos_agrupados = agrupar_por_embarcacion(barcos)
    log(f"Filas de GFW: {len(barcos)}  ·  Embarcaciones distintas: {len(barcos_agrupados)}")

    if not barcos:
        log(
            "Sin resultados para ese rango. El dataset público de GFW "
            "(public-global-fishing-effort) suele tener varios meses de rezago "
            "respecto a hoy: prueba con un rango más antiguo, por ejemplo:\n"
            "  --desde 2023-01-01 --hasta 2023-01-08"
        )

    if args.json:
        # Agrupado (una posición por embarcación, no una por celda/día) --
        # el modo de sincronización a la base de datos, más abajo, sí guarda
        # cada fila cruda de GFW porque ahí la granularidad completa importa
        # para el análisis histórico.
        print(json.dumps([a_json(b) for b in barcos_agrupados], ensure_ascii=False))
        return

    if not barcos:
        return

    import psycopg2  # importado aquí para no exigirlo en modo --json

    # Este modo (sin --json) es una sincronización manual, no la invocación en
    # vivo que usa la API (esa siempre pasa --json y nunca llega a este punto,
    # ver server/app/gfw.py). Por eso usa el rol dueño de las tablas
    # (DATABASE_URL_ADMIN, ver db/roles.sql) y no el rol restringido de runtime:
    # los upserts de abajo no pasan por db/procedures.sql.
    database_url = os.getenv("DATABASE_URL_ADMIN") or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit(f"Falta DATABASE_URL_ADMIN (o DATABASE_URL) en {ENV_FILE}")

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
