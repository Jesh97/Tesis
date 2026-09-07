import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, TypeVar

from . import features as features_mod
from . import gfw_client
from . import modelo

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # raíz del repo
SYNC_SCRIPT = BASE_DIR / "scripts" / "sync_lambayeque.py"
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")

T = TypeVar("T")

# GFW aplica un límite de solicitudes bastante bajo, y estas rutas se
# consultan en vivo desde el frontend. Cacheamos por (script, rango,
# polígono) para no golpear la API en cada recarga y evitar los 429 Too Many
# Requests.
CACHE_TTL_SECONDS = 10 * 60  # 10 minutos
_cache: dict[str, tuple[float, object]] = {}
# Deduplica llamadas concurrentes a la misma clave (p.ej. React StrictMode
# monta el efecto dos veces) para que no disparen dos procesos de Python:
# cada clave tiene su propio lock, así que solo la primera llamada ejecuta
# el script y las demás esperan y reciben el mismo resultado cacheado.
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _ejecutar_script(script_path: Path, args: list[str]) -> object:
    proc = subprocess.run(
        [PYTHON_BIN, str(script_path), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"El script de Python terminó con código {proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"No se pudo interpretar la salida del script: {proc.stdout[:300]}")


def _con_cache(clave: str, ejecutar: Callable[[], T]) -> T:
    cacheado = _cache.get(clave)
    if cacheado and cacheado[0] > time.time():
        return cacheado[1]  # type: ignore[return-value]

    with _locks_guard:
        lock = _locks.setdefault(clave, threading.Lock())

    with lock:
        cacheado = _cache.get(clave)
        if cacheado and cacheado[0] > time.time():
            return cacheado[1]  # type: ignore[return-value]
        resultado = ejecutar()
        _cache[clave] = (time.time() + CACHE_TTL_SECONDS, resultado)
        return resultado


def consultar_gfw_con_cache(
    desde: str,
    hasta: str,
    clave_extra: str,
    geojson: dict | None = None,
) -> list[dict]:
    """Corre scripts/sync_lambayeque.py --json: consulta GFW en vivo y
    devuelve los barcos sin guardar nada en base de datos. Si no se pasa
    geojson, el script usa por defecto el bbox del mar peruano."""
    clave = f"barcos|{clave_extra}|{desde}|{hasta}"

    def ejecutar() -> list[dict]:
        args = ["--json", "--desde", desde, "--hasta", hasta]
        if geojson:
            args += ["--geojson", json.dumps(geojson)]
        return _ejecutar_script(SYNC_SCRIPT, args)  # type: ignore[return-value]

    return _con_cache(clave, ejecutar)


def iniciar_precarga_periodica(nombre: str, tarea: Callable[[], None], intervalo_segundos: float) -> None:
    """Corre `tarea` en un hilo de fondo apenas arranca el servidor y la repite
    cada `intervalo_segundos`, para que el cache nunca llegue a expirar
    mientras la app está corriendo (en vez de esperar a que un usuario entre
    a la página y dispare la consulta a GFW en ese momento)."""

    def _loop() -> None:
        while True:
            try:
                tarea()
                print(f"[precarga] {nombre}: listo")
            except Exception as exc:
                print(f"[precarga] {nombre}: error - {exc}")
            time.sleep(intervalo_segundos)

    threading.Thread(target=_loop, name=f"precarga-{nombre}", daemon=True).start()


def _features_zona_con_cache(desde: str, hasta: str, clave_extra: str, geojson: dict) -> dict[str, dict]:
    clave = f"features|{clave_extra}|{desde}|{hasta}"

    def ejecutar() -> dict[str, dict]:
        presencia = gfw_client.obtener_presencia_diaria(desde, hasta, geojson)
        esfuerzo = gfw_client.obtener_esfuerzo_diario(desde, hasta, geojson)
        return features_mod.construir_features_flota(presencia, esfuerzo)

    return _con_cache(clave, ejecutar)


def consultar_actividad_con_cache(
    desde: str,
    hasta: str,
    clave_extra: str,
    geojson: dict,
) -> list[dict]:
    """Calcula apagon_ais y demora_puerto con los detectores entrenados en
    scripts/entrenar_patrones.py, a partir de features reconstruidas desde
    presencia AIS + esfuerzo pesquero diario de GFW (ver features.py)."""
    por_mmsi = _features_zona_con_cache(desde, hasta, clave_extra, geojson)

    resultados = []
    for mmsi, datos in por_mmsi.items():
        apagon = modelo.predecir("apagon_ais", datos["features"])
        demora = modelo.predecir("demora_puerto", datos["features"])
        if not apagon["detectado"] and not demora["detectado"]:
            continue
        resultados.append({
            "mmsi": mmsi,
            "nombre": datos["nombre"],
            "flag": datos["flag"],
            "lat": datos["lat"],
            "lon": datos["lon"],
            "apagonAis": (
                {"detectado": True, "diasSinSenal": datos["dias_sin_senal"], "probabilidad": apagon["probabilidad"]}
                if apagon["detectado"] else None
            ),
            "demoraPuerto": (
                {"detectado": True, "diasLejosDePuerto": datos["dias_lejos_de_puerto"], "probabilidad": demora["probabilidad"]}
                if demora["detectado"] else None
            ),
        })
    return resultados


def consultar_probabilidad_zona_protegida_con_cache(
    desde: str,
    hasta: str,
    clave_extra: str,
    geojson: dict,
) -> dict[str, float]:
    """Probabilidad del detector "zona_protegida" (entrenado) de que cada
    embarcación esté operando en la reserva artesanal de 5mn, calculada solo
    con features indirectas (posición, vecinos, horas de pesca, etc.). Es una
    señal REDUNDANTE al chequeo geográfico exacto que ya hace la ruta
    /zona-protegida -- ver el docstring de scripts/entrenar_patrones.py: sirve
    para cuando el cálculo directo de la regla falla o el dato de posición
    está incompleto, no para reemplazarlo."""
    por_mmsi = _features_zona_con_cache(desde, hasta, clave_extra, geojson)
    return {mmsi: modelo.predecir("zona_protegida", datos["features"])["probabilidad"] for mmsi, datos in por_mmsi.items()}
