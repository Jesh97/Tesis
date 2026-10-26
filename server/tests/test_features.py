"""Tests deterministas del pipeline de features (app/features.py) que
alimenta al modelo entrenado. No dependen de la API de GFW ni de una base de
datos: usan registros sintéticos con la misma forma que devuelve
app/gfw_client.py, para poder correr en cualquier máquina/CI."""
import math
import statistics

import pytest

from app.features import (
    FEATURES_NO_DISPONIBLES,
    MIN_DIAS_PRESENCIA,
    RESERVA_ARTESANAL_NM,
    ZEE_NM,
    _distancia_costa_continental_nm,
    _distancia_costa_nm,
    _distancia_islas_nm,
    _flags_zona,
    _zscore,
    construir_features_flota,
    haversine_km,
    haversine_nm,
    puerto_mas_cercano,
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
    nombre, distancia = puerto_mas_cercano(CALLAO_LAT, CALLAO_LON)
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
    s = math.sqrt(sum((v - m) ** 2 for v in valores) / (len(valores) - 1))  # stdev muestral (ddof=1), como en train.csv
    assert _zscore(30.0, valores) == pytest.approx((30.0 - m) / s)


def test_zscore_sin_suficiente_historial_devuelve_cero():
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
    assert datos["dias_sin_puerto"] == 0  # está en Callao todos los días
    assert datos["sin_puerto_en_ventana"] is False
    assert datos["dias_pescando_en_reserva"] == 0  # "pescó" en el muelle: no cuenta como reserva

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

    # z-scores contra el historial del propio barco: mismas horas todos los
    # días -> sin varianza -> 0; pescó solo el último de 6 días -> alto.
    assert f["z_hours_dia"] == 0.0
    pesca = [0.0] * 5 + [3.0]
    assert f["z_fishing_hours_dia"] == pytest.approx((3.0 - statistics.mean(pesca)) / statistics.stdev(pesca))

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


# ---------------------------------------------------------------------------
# Señales de regla: reserva de 5 mn y días sin tocar puerto
# ---------------------------------------------------------------------------

def test_distancia_costa_usa_la_costa_real_de_lambayeque_y_las_islas():
    # Frente a Pimentel, ~3 mn mar adentro: con solo los vértices de
    # COSTA_PERU daba decenas de millas.
    assert _distancia_costa_continental_nm(-6.84, -79.99) < 5.0
    # Junto a la isla Lobos de Tierra (a ~14 mn del continente): cerca de la
    # isla (lo que ve el modelo), lejos del continente (la reserva de 5 mn).
    assert _distancia_costa_nm(-6.43, -80.90) < 5.0
    assert _distancia_islas_nm(-6.43, -80.90) < 5.0
    assert _distancia_costa_continental_nm(-6.43, -80.90) > 10.0
    # Mar adentro de verdad.
    assert _distancia_costa_nm(-6.6, -81.5) > 30.0


def test_pesca_dentro_de_las_5_mn_de_lambayeque_cuenta_dias_en_reserva():
    fechas = [f"2024-01-0{d}" for d in range(1, 8)]
    lejos = (-6.6, -80.6)  # ~25 mn de la costa
    frente_a_morrope = (-6.6, -80.1)  # ~3 mn de la costa, lejos de muelles
    presencia = [_registro("777000001", f, *lejos) for f in fechas[:4]]
    presencia += [_registro("777000001", f, *frente_a_morrope) for f in fechas[4:]]
    esfuerzo = [_registro("777000001", f, *frente_a_morrope, horas=3.0) for f in fechas[4:]]
    esfuerzo.append(_registro("777000001", fechas[0], *lejos, horas=3.0))  # pescar lejos no cuenta

    datos = construir_features_flota(presencia, esfuerzo)["777000001"]

    assert datos["dias_pescando_en_reserva"] == 3
    assert datos["dist_min_reserva_nm"] < 5.0
    assert datos["dias_pescando_cerca_islas"] == 0


def test_pesca_junto_a_las_islas_lobos_cuenta_aparte_de_la_reserva():
    fechas = [f"2024-01-0{d}" for d in range(1, 7)]
    junto_a_la_isla = (-6.43, -80.90)
    presencia = [_registro("777000007", f, *junto_a_la_isla) for f in fechas]
    esfuerzo = [_registro("777000007", f, *junto_a_la_isla, horas=3.0) for f in fechas[-2:]]

    datos = construir_features_flota(presencia, esfuerzo)["777000007"]

    assert datos["dias_pescando_cerca_islas"] == 2
    assert datos["dist_min_islas_nm"] < 5.0
    assert datos["dias_pescando_en_reserva"] == 0


def test_estar_en_la_reserva_sin_pescar_no_cuenta():
    fechas = [f"2024-01-0{d}" for d in range(1, 7)]
    presencia = [_registro("777000002", f, -6.43, -80.90) for f in fechas]
    datos = construir_features_flota(presencia, [])["777000002"]
    assert datos["dias_pescando_en_reserva"] == 0


def test_dias_sin_puerto_cuenta_desde_la_ultima_visita_a_un_desembarcadero():
    fechas = [f"2024-01-{d:02d}" for d in range(1, 31)]
    san_jose = (-6.77, -79.97)  # desembarcadero de Lambayeque, no puerto oficial
    alta_mar = (-6.6, -82.0)
    presencia = [_registro("777000003", f, *(san_jose if i == 4 else alta_mar)) for i, f in enumerate(fechas)]
    datos = construir_features_flota(presencia, [])["777000003"]
    assert datos["dias_sin_puerto"] == 25  # del 5 al 30 de enero
    assert datos["sin_puerto_en_ventana"] is False


def test_dias_sin_puerto_sin_ninguna_visita_es_un_minimo():
    fechas = [f"2024-01-{d:02d}" for d in range(1, 31)]
    presencia = [_registro("777000004", f, -6.6, -82.0) for f in fechas]
    datos = construir_features_flota(presencia, [])["777000004"]
    assert datos["dias_sin_puerto"] == 29
    assert datos["sin_puerto_en_ventana"] is True


def test_menos_de_una_hora_de_pesca_en_la_reserva_no_cuenta():
    fechas = [f"2024-01-0{d}" for d in range(1, 7)]
    presencia = [_registro("777000005", f, -6.43, -80.90) for f in fechas]
    esfuerzo = [_registro("777000005", f, -6.43, -80.90, horas=0.5) for f in fechas]
    datos = construir_features_flota(presencia, esfuerzo)["777000005"]
    assert datos["dias_pescando_en_reserva"] == 0


def test_un_hueco_de_senal_corta_la_racha_sin_puerto():
    # 20 días en alta mar, 10 días sin señal, reaparece y sigue 5 días:
    # durante el hueco no se sabe si tocó puerto -> se cuenta desde que reaparece.
    fechas = [f"2024-01-{d:02d}" for d in range(1, 21)] + [f"2024-02-{d:02d}" for d in range(1, 6)]
    presencia = [_registro("777000006", f, -6.6, -82.0) for f in fechas]
    datos = construir_features_flota(presencia, [])["777000006"]
    assert datos["dias_sin_puerto"] == 4  # del 1 al 5 de febrero
    assert datos["sin_puerto_en_ventana"] is True
