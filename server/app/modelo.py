"""Carga (una sola vez, perezosamente) el modelo entrenado en
scripts/entrenar_patrones.py y expone predicciones para los 3 detectores
conectados: zona_protegida, apagon_ais, demora_puerto.

"transbordo" no se conecta: su target depende de datos de la Events API de
GFW y del registro de autorización de PRODUCE, a los que este token no tiene
acceso -- ver features.py para el detalle de qué se pudo y no se pudo
reconstruir desde datos en vivo."""
import threading
from pathlib import Path

import joblib
import pandas as pd

MODELO_PATH = Path(__file__).resolve().parent.parent.parent / "datos" / "modelos_patrones_v9.joblib"
DETECTORES_CONECTADOS = ("zona_protegida", "apagon_ais", "demora_puerto")

# El modelo se entrenó con datos/train.csv, que prepare_data.py ya había
# pasado por un StandardScaler (valor_entrenamiento = (crudo - media) /
# escala). features.py arma valores CRUDOS (grados, millas, horas...), así
# que hay que aplicar la misma transformación antes de predecir -- sin esto
# el modelo recibía valores fuera de su rango (p.ej. lat -6.8 cuando en
# entrenamiento lat_media vive entre -1.6 y 2.6) y zona_protegida acertaba
# como una moneda al aire.
#
# El scaler.joblib original no está disponible; (media, escala) se
# recuperaron con scripts/recuperar_escalado.py cruzando train.csv con los
# datos crudos de GFW de los que salió (mmsi_unido.csv). Ver ese script
# para cómo se obtuvo cada una y con qué exactitud.
ESCALADO: dict[str, tuple[float, float]] = {
    # Exactas (recomputación fila a fila, R² = 1.0):
    "hours_dia": (22.108263, 5.976809),
    "fishing_hours_dia": (5.379111, 6.200595),
    "fishing_ratio_dia": (0.236859, 0.271943),
    "n_celdas_dia": (8.578999, 9.972365),
    "lat_media": (-13.555222, 3.969597),
    "lon_media": (-79.727675, 2.931520),
    "dias_desde_ultimo_registro": (3.253529, 30.443149),
    "dias_activos_acumulados": (409.519948, 387.120731),
    "gap_log": (0.787205, 0.513701),
    "desplazamiento_km": (67.436627, 101.948070),
    "velocidad_implicita_kt": (1.326108, 1.764942),
    "z_hours_dia": (-0.009544, 1.024896),
    "z_fishing_hours_dia": (-0.037037, 0.993844),
    "z_n_celdas_dia": (-0.054931, 0.921601),
    # Exacta por anclas: los flags de zona del mismo CSV fijan dónde valen
    # 5mn y 200mn.
    "dist_costa_min_nm": (177.101106, 155.249756),
    # Conteos enteros: la escala es el inverso del paso entre valores
    # distintos del CSV, la media sale del mínimo crudo (0, o 1 en cluster).
    "n_vecinos_celda_max_dia": (17.725193, 17.788930),
    "n_vecinos_pais_distinto_max_dia": (1.645981, 4.583557),
    "cluster_tamano_dia": (38.164476, 61.236946),
    # Aproximadas: definición original no reproducible exacta.
    "dist_puerto_mas_cercano_nm": (177.101106, 155.180852),  # corr. 0.9996 con dist_costa
    "disp_celdas_km": (10.915196, 13.578687),  # R² 0.96
}

# Columnas que no se pueden calcular en vivo (sin Events API / registro de
# PRODUCE, o con definición original desconocida): se fija el valor más
# común en train, ya en escala de entrenamiento. Todas tienen importancia
# 0 o <= 1% en los 3 detectores conectados.
VALOR_FIJO_ESCALADO: dict[str, float] = {
    "flota_fishing_hours_max_celda": -0.314090,
    "n_encuentros_transbordo_dia": -0.071544,
    "velocidad_transbordo_min_kt": 0.071536,
    "es_transbordo_no_autorizado": -0.055421,
}


def escalar(features: dict[str, float]) -> dict[str, float]:
    """Lleva un vector de features crudas (features.py) a la escala de
    entrenamiento. Las columnas binarias/one-hot no se escalaron en
    prepare_data.py y pasan tal cual."""
    resultado = dict(features)
    for columna, (media, escala) in ESCALADO.items():
        if columna in resultado:
            resultado[columna] = (resultado[columna] - media) / escala
    resultado.update(VALOR_FIJO_ESCALADO)
    return resultado

_modelos: dict | None = None
_lock = threading.Lock()


def _cargar() -> dict:
    global _modelos
    if _modelos is not None:
        return _modelos
    with _lock:
        if _modelos is None:
            print(f"[modelo] cargando {MODELO_PATH} (archivo grande, puede tardar)...")
            todos = joblib.load(MODELO_PATH)
            _modelos = {k: v for k, v in todos.items() if k in DETECTORES_CONECTADOS}
            print(f"[modelo] listo: {list(_modelos.keys())}")
        return _modelos


def precargar() -> None:
    """Dispara la carga del modelo (para llamarse en un hilo de fondo al
    arrancar el servidor y no bloquear la primera petición)."""
    _cargar()


def umbral(nombre_detector: str) -> float:
    return _cargar()[nombre_detector]["threshold"]


def predecir(nombre_detector: str, features: dict[str, float], ya_escaladas: bool = False) -> dict:
    """`features` crudas, tal como las arma features.py. `ya_escaladas=True`
    solo para filas que ya vienen en escala de entrenamiento (datos/test.csv,
    ver scripts/probar_modelo_casos_reales.py)."""
    modelos = _cargar()
    info = modelos[nombre_detector]
    columnas = info["features"]
    if not ya_escaladas:
        features = escalar(features)
    # DataFrame con los mismos nombres de columna que en el entrenamiento
    # (evita el warning de sklearn y descarta cualquier duda de alineación).
    fila = pd.DataFrame([[features.get(c, 0.0) for c in columnas]], columns=columnas)
    proba = float(info["model"].predict_proba(fila)[0][1])
    return {
        "probabilidad": proba,
        "detectado": bool(proba >= info["threshold"]),
    }
