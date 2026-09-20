import hashlib
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, TypeVar

from . import features as features_mod
from . import gfw_client
from . import modelo

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # raíz del repo
SYNC_SCRIPT = BASE_DIR / "scripts" / "sync_lambayeque.py"
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")

T = TypeVar("T")
I = TypeVar("I")

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

# La cache en memoria no sobrevive a un reinicio del proceso -- y en
# desarrollo, `uvicorn --reload` reinicia el proceso cada vez que se guarda un
# archivo de server/app/. Sin esto, cada guardado durante desarrollo volvía a
# pagar el viaje completo a GFW (varios segundos) para volver a mostrar los
# barcos. Se persiste a disco (además de en memoria) para que un reinicio
# dentro de la misma ventana de TTL lea el resultado ya calculado.
CACHE_DIR = BASE_DIR / "server" / ".cache" / "gfw"


def _archivo_cache(clave: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha256(clave.encode()).hexdigest()}.json"


def _leer_cache_disco(clave: str) -> tuple[float, object] | None:
    try:
        datos = json.loads(_archivo_cache(clave).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if datos.get("clave") != clave or datos.get("expira", 0) <= time.time():
        return None
    return (datos["expira"], datos["valor"])


def _escribir_cache_disco(clave: str, expira: float, valor: object) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _archivo_cache(clave).write_text(
            json.dumps({"clave": clave, "expira": expira, "valor": valor}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # la cache en disco es una optimización, no algo de lo que dependa la respuesta


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

        en_disco = _leer_cache_disco(clave)
        if en_disco:
            _cache[clave] = en_disco
            return en_disco[1]  # type: ignore[return-value]

        resultado = ejecutar()
        expira = time.time() + CACHE_TTL_SECONDS
        _cache[clave] = (expira, resultado)
        _escribir_cache_disco(clave, expira, resultado)
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


# GFW aplica un límite de solicitudes bastante bajo (ver comentario arriba),
# así que no se paralelizan las zonas sin límite: 3 a la vez alcanza para
# bajar el tiempo total de ~5x secuencial a ~2 tandas, sin arriesgar tantos
# 429 como paralelizar las 5 juntas.
MAX_ZONAS_CONCURRENTES = 3


def ejecutar_por_zonas(zonas: list[I], tarea: Callable[[I], T]) -> list[T]:
    """Corre `tarea` para cada zona con un pool acotado de hilos (en vez de
    una por una), preservando el orden de `zonas` en el resultado. Cada zona
    ya cachea por su propia clave, así que paralelizarlas es seguro: no hay
    trabajo duplicado, solo se solapa la espera de red de GFW."""
    if not zonas:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_ZONAS_CONCURRENTES, len(zonas))) as executor:
        return list(executor.map(tarea, zonas))


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
        # Presencia y esfuerzo son consultas independientes a GFW (~10-15s
        # cada una con resolución DIARIA) -- se piden en paralelo en vez de
        # una tras otra para no sumar sus tiempos.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futuro_presencia = executor.submit(gfw_client.obtener_presencia_diaria, desde, hasta, geojson)
            futuro_esfuerzo = executor.submit(gfw_client.obtener_esfuerzo_diario, desde, hasta, geojson)
            presencia = futuro_presencia.result()
            esfuerzo = futuro_esfuerzo.result()
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
