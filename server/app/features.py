"""
Reconstruye, a partir de datos en vivo de GFW, un vector de features
compatible con los modelos entrenados en scripts/entrenar_patrones.py
(datos/modelos_patrones_v9.joblib).

LIMITACIÓN HONESTA: el modelo se entrenó con 13 años de datos de SISESAT, que
incluyen señales que el token actual de GFW no expone (Events API sin acceso,
registro de autorización de transbordo de PRODUCE). Esas columnas se imputan
en 0 -- se verificó con model.feature_importances_ que las 7 columnas no
disponibles (n_encuentros_transbordo_dia, n_eventos_loitering_dia,
velocidad_transbordo_min_kt, es_transbordo_no_autorizado y los 3
autorizado_transbordo_*) tienen importancia 0.0 en los 3 detectores que sí se
conectan (zona_protegida, apagon_ais, demora_puerto), así que imputarlas en 0
no le resta señal real al modelo para estos patrones -- solo "transbordo"
(no conectado) dependía de verdad de ellas.

Todo lo demás (posición, horas, vecinos, distancia a costa/puerto, huecos de
AIS, z-scores contra la flota consultada) se calcula desde la respuesta real
de GFW para el rango y polígono pedidos.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from statistics import mean, pstdev

# Mismos puertos que scripts/detectar_irregularidades.py (con coordenadas
# conocidas). El modelo espera 3 columnas de puerto adicionales para las que
# no tenemos coordenadas ("LA PUNTA ANCHORAGE", "PER-55"): esos casos, y
# cualquier puerto fuera de esta lista, se resuelven como "OTRO" -- el mismo
# bucket que usa el propio dataset de entrenamiento para puertos no listados.
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
PUERTOS_ONEHOT = [
    "BAYOVAR", "CALLAO", "CHANCAY", "CHIMBOTE", "HUACHO", "HUARMEY", "ILO",
    "LA PUNTA ANCHORAGE", "MATARANI", "OTRO", "PER-55", "PISCO",
    "PUERTO CHICAMA", "SAN JUAN DE MARCONA", "SAN NICOLAS", "TALARA",
]

# Aproximación de la línea de costa peruana (lon, lat), de norte a sur --
# suficiente para estimar dist_costa_min_nm sin depender de un dataset GIS
# externo (no confundir con los polígonos de "zonas" del sistema, que son
# áreas específicas, no la costa completa).
COSTA_PERU = [
    (-80.44, -3.40), (-81.11, -5.83), (-79.44, -7.70), (-78.60, -9.09),
    (-77.62, -11.11), (-77.27, -11.57), (-77.15, -12.05), (-76.20, -13.71),
    (-75.16, -15.35), (-75.24, -15.27), (-72.10, -17.00), (-71.34, -17.65),
    (-70.37, -18.35),
]

PAISES_ONEHOT = ["CHL", "CHN", "COL", "ECU", "ESP", "HND", "JPN", "KOR", "PAN", "PER", "TWN"]

# Confirmado con model.feature_importances_: importancia 0.0 en los 3
# detectores conectados (zona_protegida, apagon_ais, demora_puerto).
FEATURES_NO_DISPONIBLES = [
    "n_encuentros_transbordo_dia", "n_eventos_loitering_dia",
    "velocidad_transbordo_min_kt", "es_transbordo_no_autorizado",
    "autorizado_transbordo_autorizado", "autorizado_transbordo_no_autorizado",
    "autorizado_transbordo_sin_encuentro",
]

RESERVA_ARTESANAL_NM = 5.0
ZEE_NM = 200.0
MIN_DIAS_PRESENCIA = 5  # igual que scripts/detectar_irregularidades.py
RADIO_CLUSTER_NM = 5.0


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_nm = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r_nm * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_nm(lat1, lon1, lat2, lon2) * 1.852


def _distancia_costa_nm(lat: float, lon: float) -> float:
    return min(haversine_nm(lat, lon, plat, plon) for plon, plat in COSTA_PERU)


def _puerto_mas_cercano(lat: float, lon: float) -> tuple[str, float]:
    nombre, plat, plon = min(PUERTOS_PERU, key=lambda p: haversine_nm(lat, lon, p[1], p[2]))
    return nombre, haversine_nm(lat, lon, plat, plon)


def _flags_zona(dist_costa_nm: float) -> tuple[float, float, float]:
    return (
        float(dist_costa_nm <= RESERVA_ARTESANAL_NM),
        float(RESERVA_ARTESANAL_NM < dist_costa_nm <= ZEE_NM),
        float(dist_costa_nm > ZEE_NM),
    )


def _zscore(valor: float, valores: list[float]) -> float:
    if len(valores) < 2:
        return 0.0
    m, s = mean(valores), pstdev(valores)
    return (valor - m) / s if s > 0 else 0.0


def _colapsar_por_dia(registros: list[dict]) -> dict[tuple[str, str], dict]:
    """Agrupa filas GFW (una por celda visitada ese día) en un resumen por
    (mmsi, date): horas totales y lista de celdas visitadas."""
    por_clave: dict[tuple[str, str], dict] = {}
    for r in registros:
        mmsi = r.get("mmsi")
        fecha = r.get("date")
        if not mmsi or not fecha or r.get("lat") is None or r.get("lon") is None:
            continue
        clave = (mmsi, fecha)
        resumen = por_clave.setdefault(clave, {
            "mmsi": mmsi, "date": fecha, "shipName": None, "flag": None,
            "horas": 0.0, "celdas": [],
        })
        horas = r.get("hours") or 0
        resumen["horas"] += horas
        resumen["celdas"].append({"lat": r["lat"], "lon": r["lon"], "horas": horas})
        if r.get("shipName"):
            resumen["shipName"] = r.get("shipName")
        if r.get("flag"):
            resumen["flag"] = r.get("flag")
    return por_clave


def _posicion_representativa(celdas: list[dict]) -> tuple[float, float]:
    return mean(c["lat"] for c in celdas), mean(c["lon"] for c in celdas)


def construir_features_flota(
    registros_presencia: list[dict],
    registros_esfuerzo: list[dict],
) -> dict[str, dict]:

    presencia_por_dia = _colapsar_por_dia(
        [r for r in registros_presencia if r.get("vesselType") == "FISHING"]
    )
    esfuerzo_por_dia = _colapsar_por_dia(
        [r for r in registros_esfuerzo if r.get("vesselType") == "FISHING"]
    )

    por_mmsi: dict[str, list[dict]] = defaultdict(list)
    for (mmsi, _fecha), resumen in presencia_por_dia.items():
        por_mmsi[mmsi].append(resumen)
    for filas in por_mmsi.values():
        filas.sort(key=lambda f: f["date"])

    candidatos = {mmsi: filas for mmsi, filas in por_mmsi.items() if len(filas) >= MIN_DIAS_PRESENCIA}
    if not candidatos:
        return {}

    horas_por_dia: dict[str, list[float]] = defaultdict(list)
    celdas_por_dia: dict[str, list[float]] = defaultdict(list)
    fishing_horas_por_dia: dict[str, list[float]] = defaultdict(list)
    vecinos_por_celda_dia: dict[tuple[str, float, float], set[str]] = defaultdict(set)
    posiciones_por_dia: dict[str, list[tuple[str, float, float, str | None]]] = defaultdict(list)

    for (mmsi, fecha), resumen in presencia_por_dia.items():
        horas_por_dia[fecha].append(resumen["horas"])
        celdas_por_dia[fecha].append(len(resumen["celdas"]))
        lat, lon = _posicion_representativa(resumen["celdas"])
        posiciones_por_dia[fecha].append((mmsi, lat, lon, resumen.get("flag")))
        for c in resumen["celdas"]:
            clave_celda = (fecha, round(c["lat"], 2), round(c["lon"], 2))
            vecinos_por_celda_dia[clave_celda].add(mmsi)

    for (_mmsi, fecha), resumen in esfuerzo_por_dia.items():
        fishing_horas_por_dia[fecha].append(resumen["horas"])

    fishing_horas_celda_max_por_dia = {
        fecha: max(horas, default=0.0) for fecha, horas in fishing_horas_por_dia.items()
    }

    resultado: dict[str, dict] = {}

    for mmsi, filas in candidatos.items():
        fila_actual = filas[-1]
        fecha_actual = fila_actual["date"]
        lat, lon = _posicion_representativa(fila_actual["celdas"])

        horas_dia = fila_actual["horas"]
        n_celdas_dia = len(fila_actual["celdas"])
        fishing_dia = esfuerzo_por_dia.get((mmsi, fecha_actual))
        fishing_hours_dia = fishing_dia["horas"] if fishing_dia else 0.0
        fishing_ratio_dia = (fishing_hours_dia / horas_dia) if horas_dia > 0 else 0.0

        dist_costa = _distancia_costa_nm(lat, lon)
        puerto_nombre, dist_puerto = _puerto_mas_cercano(lat, lon)

        if len(filas) >= 2:
            fecha_anterior = filas[-2]["date"]
            d_actual = datetime.strptime(fecha_actual, "%Y-%m-%d").date()
            d_anterior = datetime.strptime(fecha_anterior, "%Y-%m-%d").date()
            dias_desde_ultimo_registro = (d_actual - d_anterior).days
            lat_prev, lon_prev = _posicion_representativa(filas[-2]["celdas"])
            desplazamiento_km = haversine_km(lat_prev, lon_prev, lat, lon)
            horas_transcurridas = max(dias_desde_ultimo_registro * 24, 1)
            velocidad_implicita_kt = (desplazamiento_km / 1.852) / horas_transcurridas
        else:
            dias_desde_ultimo_registro = 0
            desplazamiento_km = 0.0
            velocidad_implicita_kt = 0.0

        disp_celdas_km = 0.0
        if n_celdas_dia > 1:
            distancias = [haversine_km(lat, lon, c["lat"], c["lon"]) for c in fila_actual["celdas"]]
            disp_celdas_km = pstdev(distancias) if len(distancias) > 1 else 0.0

        vecinos_totales: set[str] = set()
        for c in fila_actual["celdas"]:
            clave_celda = (fecha_actual, round(c["lat"], 2), round(c["lon"], 2))
            vecinos_totales |= vecinos_por_celda_dia.get(clave_celda, set())
        vecinos_totales.discard(mmsi)

        bandera_actual = (fila_actual.get("flag") or "").upper()
        vecinos_distinto_pais = 0
        cluster_tamano_dia = 1
        for otro_mmsi, otro_lat, otro_lon, otra_bandera in posiciones_por_dia.get(fecha_actual, []):
            if otro_mmsi == mmsi:
                continue
            if haversine_nm(lat, lon, otro_lat, otro_lon) <= RADIO_CLUSTER_NM:
                cluster_tamano_dia += 1
                if (otra_bandera or "").upper() != bandera_actual:
                    vecinos_distinto_pais += 1

        gap_log = math.log1p(dias_desde_ultimo_registro)
        z_hours_dia = _zscore(horas_dia, horas_por_dia.get(fecha_actual, []))
        z_fishing_hours_dia = _zscore(fishing_hours_dia, fishing_horas_por_dia.get(fecha_actual, []))
        z_n_celdas_dia = _zscore(n_celdas_dia, celdas_por_dia.get(fecha_actual, []))

        features: dict[str, float] = {
            "hours_dia": horas_dia,
            "fishing_hours_dia": fishing_hours_dia,
            "fishing_ratio_dia": fishing_ratio_dia,
            "n_celdas_dia": float(n_celdas_dia),
            "lat_media": lat,
            "lon_media": lon,
            "dist_costa_min_nm": dist_costa,
            "dist_puerto_mas_cercano_nm": dist_puerto,
            "flota_fishing_hours_max_celda": fishing_horas_celda_max_por_dia.get(fecha_actual, 0.0),
            "dias_desde_ultimo_registro": float(dias_desde_ultimo_registro),
            "dias_activos_acumulados": float(len(filas)),
            "disp_celdas_km": disp_celdas_km,
            "desplazamiento_km": desplazamiento_km,
            "velocidad_implicita_kt": velocidad_implicita_kt,
            "n_vecinos_celda_max_dia": float(len(vecinos_totales)),
            "n_vecinos_pais_distinto_max_dia": float(vecinos_distinto_pais),
            "cluster_tamano_dia": float(cluster_tamano_dia),
            "z_hours_dia": z_hours_dia,
            "z_fishing_hours_dia": z_fishing_hours_dia,
            "z_n_celdas_dia": z_n_celdas_dia,
            "gap_log": gap_log,
        }
        for col in FEATURES_NO_DISPONIBLES:
            features[col] = 0.0

        zona_reserva, zona_industrial, zona_fuera_zee = _flags_zona(dist_costa)
        features["zona_dia_reserva_artesanal_5mn"] = zona_reserva
        features["zona_dia_zee_industrial"] = zona_industrial
        features["zona_dia_fuera_zee"] = zona_fuera_zee

        for pais in PAISES_ONEHOT:
            features[f"pais_inferido_{pais}"] = float(bandera_actual == pais)
        features["pais_inferido_desconocido"] = float(bandera_actual not in PAISES_ONEHOT)

        for puerto in PUERTOS_ONEHOT:
            features[f"puerto_mas_cercano_{puerto}"] = 0.0
        clave_puerto = puerto_nombre if puerto_nombre in PUERTOS_ONEHOT else "OTRO"
        features[f"puerto_mas_cercano_{clave_puerto}"] = 1.0

        # Métricas descriptivas para el frontend (no todas se le pasan al
        # modelo, pero sirven para explicar la alerta en la UI).
        racha_lejos_de_puerto = 0
        racha_actual = 0
        for f in filas:
            flat, flon = _posicion_representativa(f["celdas"])
            if _puerto_mas_cercano(flat, flon)[1] > 5.0:
                racha_actual += 1
                racha_lejos_de_puerto = max(racha_lejos_de_puerto, racha_actual)
            else:
                racha_actual = 0

        resultado[mmsi] = {
            "features": features,
            "nombre": fila_actual.get("shipName") or "Desconocido",
            "flag": fila_actual.get("flag"),
            "lat": lat,
            "lon": lon,
            "dias_sin_senal": dias_desde_ultimo_registro,
            "dias_lejos_de_puerto": racha_lejos_de_puerto,
        }

    return resultado
