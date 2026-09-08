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


def predecir(nombre_detector: str, features: dict[str, float]) -> dict:
    modelos = _cargar()
    info = modelos[nombre_detector]
    columnas = info["features"]
    # DataFrame con los mismos nombres de columna que en el entrenamiento
    # (evita el warning de sklearn y descarta cualquier duda de alineación).
    fila = pd.DataFrame([[features.get(c, 0.0) for c in columnas]], columns=columnas)
    proba = float(info["model"].predict_proba(fila)[0][1])
    return {
        "probabilidad": proba,
        "detectado": bool(proba >= info["threshold"]),
    }
