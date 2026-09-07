"""Tests deterministas del pipeline de features (app/features.py) que
alimenta al modelo entrenado. No dependen de la API de GFW ni de una base de
datos: usan registros sintéticos con la misma forma que devuelve
app/gfw_client.py, para poder correr en cualquier máquina/CI."""
import math

from app.features import (
    FEATURES_NO_DISPONIBLES,
    MIN_DIAS_PRESENCIA,
    RESERVA_ARTESANAL_NM,
    ZEE_NM,
    _distancia_costa_nm,
    _flags_zona,
    _puerto_mas_cercano,
    _zscore,
    construir_features_flota,
    haversine_km,
    haversine_nm,
)

CALLAO_LAT, CALLAO_LON = -12.05, -77.15  # coincide con PUERTOS_PERU y COSTA_PERU


def _registro(mmsi, fecha, lat=CALLAO_LAT, lon=CALLAO_LON, horas=5.0, vessel_type="FISHING", flag="PER", nombre="TEST BOAT"):
    return {
        "mmsi": mmsi, "date": fecha, "lat": lat, "lon": lon, "hours": horas,
        "vesselType": vessel_type, "flag": flag, "shipName": nombre,
    }


# ---------------------------------------------------------------------------
# Geometría básica
# ---------------------------------------------------------------------------

def test_haversine_mismo_punto_es_cero():
    assert haversine_nm(CALLAO_LAT, CALLAO_LON, CALLAO_LAT, CALLAO_LON) == 0.0
    assert haversine_km(CALLAO_LAT, CALLAO_LON, CALLAO_LAT, CALLAO_LON) == 0.0


def test_haversine_km_es_nm_por_1_852():
    nm = haversine_nm(-12.0, -77.0, -13.0, -76.0)
    km = haversine_km(-12.0, -77.0, -13.0, -76.0)
    assert km == nm * 1.852


def test_distancia_costa_en_punto_de_la_costa_es_cero():
    # (-77.15, -12.05) está literalmente en COSTA_PERU.
    assert _distancia_costa_nm(CALLAO_LAT, CALLAO_LON) == 0.0


def test_puerto_mas_cercano_reconoce_callao():
    nombre, distancia = _puerto_mas_cercano(CALLAO_LAT, CALLAO_LON)
    assert nombre == "CALLAO"
    assert distancia == 0.0


def test_flags_zona_umbrales():
    assert _flags_zona(0.0) == (1.0, 0.0, 0.0)  # dentro de la reserva artesanal
    assert _flags_zona(RESERVA_ARTESANAL_NM) == (1.0, 0.0, 0.0)  # límite inclusivo
    assert _flags_zona(RESERVA_ARTESANAL_NM + 0.01) == (0.0, 1.0, 0.0)  # zee industrial
    assert _flags_zona(ZEE_NM) == (0.0, 1.0, 0.0)  # límite inclusivo
    assert _flags_zona(ZEE_NM + 0.01) == (0.0, 0.0, 1.0)  # fuera de la zee


def test_zscore_formula():
    valores = [10.0, 20.0, 30.0]
    m = sum(valores) / len(valores)
    s = math.sqrt(sum((v - m) ** 2 for v in valores) / len(valores))  # pstdev (poblacional)
    assert _zscore(20.0, valores) == (20.0 - m) / s


def test_zscore_sin_suficiente_flota_devuelve_cero():
    assert _zscore(5.0, []) == 0.0
    assert _zscore(5.0, [5.0]) == 0.0


# ---------------------------------------------------------------------------
# construir_features_flota
# ---------------------------------------------------------------------------

def test_excluye_embarcaciones_con_poca_presencia():
    fechas = [f"2024-01-0{d}" for d in range(1, 3)]  # solo 2 días < MIN_DIAS_PRESENCIA
    presencia = [_registro("999999999", f) for f in fechas]
    resultado = construir_features_flota(presencia, [])
    assert "999999999" not in resultado


def test_excluye_embarcaciones_que_no_son_fishing():
    fechas = [f"2024-01-0{d}" for d in range(1, 7)]
    presencia = [_registro("888888888", f, vessel_type="CARRIER") for f in fechas]
    resultado = construir_features_flota(presencia, [])
    assert "888888888" not in resultado


def test_features_de_embarcacion_estacionaria_en_callao():
    fechas = [f"2024-01-0{d}" for d in range(1, 7)]  # 6 días >= MIN_DIAS_PRESENCIA
    assert len(fechas) >= MIN_DIAS_PRESENCIA

    presencia = [_registro("111111111", f) for f in fechas]
    esfuerzo = [_registro("111111111", fechas[-1], horas=3.0)]  # solo el último día pescó

    resultado = construir_features_flota(presencia, esfuerzo)
    assert "111111111" in resultado

    datos = resultado["111111111"]
    f = datos["features"]

    # Metadata expuesta al frontend
    assert datos["nombre"] == "TEST BOAT"
    assert datos["flag"] == "PER"
    assert datos["dias_sin_senal"] == 1  # un día de diferencia entre registros consecutivos
    assert datos["dias_lejos_de_puerto"] == 0  # nunca se aleja del puerto

    # Features geográficas: siempre en el mismo punto (Callao)
    assert f["lat_media"] == CALLAO_LAT
    assert f["lon_media"] == CALLAO_LON
    assert f["dist_costa_min_nm"] == 0.0
    assert f["dist_puerto_mas_cercano_nm"] == 0.0
    assert f["puerto_mas_cercano_CALLAO"] == 1.0
    assert f["zona_dia_reserva_artesanal_5mn"] == 1.0

    # Sin movimiento entre días: desplazamiento y velocidad en cero
    assert f["desplazamiento_km"] == 0.0
    assert f["velocidad_implicita_kt"] == 0.0
    assert f["disp_celdas_km"] == 0.0  # una sola celda por día

    # Horas/pesca del último día
    assert f["hours_dia"] == 5.0
    assert f["fishing_hours_dia"] == 3.0
    assert f["fishing_ratio_dia"] == 3.0 / 5.0
    assert f["flota_fishing_hours_max_celda"] == 3.0

    # Única embarcación de la "flota" consultada -> sin varianza -> z-score 0
    assert f["z_hours_dia"] == 0.0
    assert f["z_fishing_hours_dia"] == 0.0

    # Sin vecinos en la celda ni en el radio de cluster
    assert f["n_vecinos_celda_max_dia"] == 0.0
    assert f["n_vecinos_pais_distinto_max_dia"] == 0.0
    assert f["cluster_tamano_dia"] == 1.0  # solo ella misma

    # Bandera
    assert f["pais_inferido_PER"] == 1.0
    assert f["pais_inferido_CHN"] == 0.0
    assert f["pais_inferido_desconocido"] == 0.0

    # dias_activos_acumulados = cantidad de días con presencia en el rango
    assert f["dias_activos_acumulados"] == float(len(fechas))

    # gap_log = log1p(dias_desde_ultimo_registro)
    assert f["gap_log"] == math.log1p(1)

    # Columnas que GFW no puede reconstruir: siempre imputadas en 0
    for columna in FEATURES_NO_DISPONIBLES:
        assert f[columna] == 0.0


def test_vecinos_en_la_misma_celda_se_cuentan():
    fechas = [f"2024-01-0{d}" for d in range(1, 7)]
    presencia = [_registro("111111111", f, flag="PER") for f in fechas]
    # Un barco de otra bandera, en la MISMA celda (redondeo a 2 decimales), el último día.
    presencia.append(_registro("222222222", fechas[-1], flag="CHN"))
    # El vecino también necesita historial para no filtrarse por MIN_DIAS_PRESENCIA
    # en su propio conteo, pero aquí solo nos interesa cómo afecta a "111111111".
    for f in fechas[:-1]:
        presencia.append(_registro("222222222", f, flag="CHN"))

    resultado = construir_features_flota(presencia, [])
    f = resultado["111111111"]["features"]

    assert f["n_vecinos_celda_max_dia"] == 1.0
    assert f["n_vecinos_pais_distinto_max_dia"] == 1.0
    assert f["cluster_tamano_dia"] == 2.0  # ella misma + el vecino
