import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from . import actividad_mensual
from . import deteccion
from . import features as features_mod
from . import gfw_client
from . import modelo

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # raíz del repo

# scripts/sync_lambayeque.py expone construir_geojson_bbox/LAMBAYEQUE_BBOX y
# la lógica para agrupar filas de GFW por embarcación (ver consultar_gfw_con_cache
# más abajo). Se importa en el mismo proceso -- igual que ya hace gfw_client.py
# para el resto de las consultas -- en vez de lanzarlo como subproceso: evitar
# un intérprete de Python nuevo (con sus imports) por cada consulta fuera de
# cache, sin timeout ni serialización por stdout de por medio.
_SCRIPTS_DIR = BASE_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import sync_lambayeque  # noqa: E402 (necesita el sys.path.insert de arriba)

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


def _con_cache(clave: str, ejecutar: Callable[[], T], ttl_segundos: float = CACHE_TTL_SECONDS) -> T:
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
        expira = time.time() + ttl_segundos
        _cache[clave] = (expira, resultado)
        _escribir_cache_disco(clave, expira, resultado)
        return resultado


def consultar_gfw_con_cache(
    desde: str,
    hasta: str,
    clave_extra: str,
    geojson: dict | None = None,
) -> list[dict]:
    """Consulta GFW en vivo (vía sync_lambayeque, en el mismo proceso -- ver
    el import arriba) y devuelve los barcos sin guardar nada en base de
    datos. Si no se pasa geojson, usa por defecto el bbox de la jurisdicción
    de Lambayeque (LAMBAYEQUE_BBOX)."""
    clave = f"barcos|{clave_extra}|{desde}|{hasta}"

    def ejecutar() -> list[dict]:
        token = os.getenv("GFW_API_TOKEN")
        if not token:
            raise RuntimeError("Falta GFW_API_TOKEN")
        geo = geojson or sync_lambayeque.construir_geojson_bbox(sync_lambayeque.LAMBAYEQUE_BBOX)
        # Mismo lock que las consultas de gfw_client: GFW solo acepta un
        # reporte de 4Wings a la vez por token.
        with gfw_client.lock_reporte_4wings:
            barcos = sync_lambayeque.obtener_barcos_en_zona(token, desde, hasta, geo)
        agrupados = sync_lambayeque.agrupar_por_embarcacion(barcos)
        return [sync_lambayeque.a_json(b) for b in agrupados]

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
    # v3: agrega las señales de regla (dias_sin_puerto, dias_pescando_en_reserva,
    # apagado_en_frontera_zee):
    # una entrada en disco con el formato anterior no debe leerse.
    clave = f"features:v3|{clave_extra}|{desde}|{hasta}"

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
    """Alertas de apagón de AIS, demora en puerto y pesca en la reserva
    artesanal de 5 mn, a partir de features reconstruidas desde presencia
    AIS + esfuerzo pesquero diario de GFW (ver features.py). Cada patrón
    combina regla + detector entrenado: ver deteccion.py."""
    por_mmsi = _features_zona_con_cache(desde, hasta, clave_extra, geojson)
    return [
        alerta
        for mmsi, datos in por_mmsi.items()
        if (alerta := deteccion.evaluar_actividad(mmsi, datos)) is not None
    ]


# TTL más largo que CACHE_TTL_SECONDS: a diferencia de la posición de un
# barco (que cambia todo el tiempo), su última visita a puerto conocida rara
# vez cambia en el corto plazo, y esta consulta es bajo demanda (un click del
# analista, no una precarga masiva) -- no tiene sentido volver a golpear la
# Events API de GFW cada 10 minutos por el mismo barco.
CACHE_TTL_ULTIMO_PUERTO_SEGUNDOS = 6 * 60 * 60  # 6 horas


def consultar_ultimo_puerto_con_cache(vessel_id: str) -> dict | None:
    """Última visita a puerto real (Events API) para un vessel_id de GFW.
    Se cachea por separado de consultar_gfw_con_cache/_con_cache (TTL propio,
    ver arriba) porque se pide bajo demanda por barco, no por zona/rango."""
    clave = f"ultimo_puerto|{vessel_id}"

    def ejecutar() -> dict | None:
        resultado = gfw_client.obtener_ultima_visita_puerto(vessel_id)
        if resultado is None or not resultado.get("fin"):
            return resultado

        fin = datetime.fromisoformat(resultado["fin"].replace("Z", "+00:00"))
        dias_desde_salida = (datetime.now(timezone.utc) - fin).days

        # "Zona no autorizada": el ancla real (Events API) quedó lejos de
        # cualquiera de los 13 puertos oficiales -- ver
        # features.UMBRAL_ZONA_NO_AUTORIZADA_NM para cómo se calibró el
        # umbral con datos reales (evita marcar sub-muelles de un puerto
        # real, como "MARQUEZ" en Callao, como si fueran clandestinos).
        puerto_oficial_cercano = None
        dist_puerto_oficial_nm = None
        zona_no_autorizada = False
        if resultado.get("lat") is not None and resultado.get("lon") is not None:
            puerto_oficial_cercano, dist_puerto_oficial_nm = features_mod.puerto_mas_cercano(resultado["lat"], resultado["lon"])
            zona_no_autorizada = dist_puerto_oficial_nm > features_mod.UMBRAL_ZONA_NO_AUTORIZADA_NM

        return {
            "puerto": resultado["puerto"],
            "fechaSalida": resultado["fin"],
            "diasDesdeSalida": dias_desde_salida,
            "duracionHorasEnPuerto": resultado["duracion_horas"],
            "zonaNoAutorizada": zona_no_autorizada,
            "puertoOficialMasCercano": puerto_oficial_cercano,
            "distPuertoOficialNm": round(dist_puerto_oficial_nm, 1) if dist_puerto_oficial_nm is not None else None,
        }

    return _con_cache(clave, ejecutar, ttl_segundos=CACHE_TTL_ULTIMO_PUERTO_SEGUNDOS)


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


# Vista "Tendencias": un año cerrado ya no cambia en GFW (salvo
# reprocesamientos ocasionales del dataset), así que se cachea por mucho más
# tiempo que el resto. El año en curso sí recibe datos nuevos (con el rezago
# propio del dataset público), por eso se refresca más seguido.
CACHE_TTL_ANIO_CERRADO_SEGUNDOS = 30 * 24 * 60 * 60  # 30 días
CACHE_TTL_ANIO_EN_CURSO_SEGUNDOS = 6 * 60 * 60  # 6 horas


def consultar_actividad_mensual_con_cache(anio: int) -> dict[str, dict]:
    """Resumen mes a mes (ver actividad_mensual.agregar_por_mes) de un año
    calendario completo dentro del bbox de Lambayeque. Se cachea por año
    (y no por el rango exacto que pide el frontend) para que cualquier rango
    reutilice los años ya consultados: GFW tarda ~10-20s por año y por
    dataset. Los años se piden de a uno (ver consultar_actividad_mensual_rango)."""
    clave = f"actividad_mensual|lambayeque|{anio}"
    hoy = date.today()
    en_curso = anio >= hoy.year

    def ejecutar() -> dict[str, dict]:
        geo = sync_lambayeque.construir_geojson_bbox(sync_lambayeque.LAMBAYEQUE_BBOX)
        # El fin de date-range de 4Wings es exclusivo (verificado: con
        # "2025-01-01,2026-01-01" llegan exactamente los 12 meses de 2025).
        desde = f"{anio}-01-01"
        hasta = hoy.isoformat() if en_curso else f"{anio + 1}-01-01"
        # Una tras otra a propósito (no en paralelo como en
        # _features_zona_con_cache): dos reportes mensuales simultáneos
        # devuelven 429 -- ver el comentario en gfw_client._TIMEOUT_MENSUAL.
        presencia = gfw_client.obtener_presencia_mensual(desde, hasta, geo)
        esfuerzo = gfw_client.obtener_esfuerzo_mensual(desde, hasta, geo)
        return actividad_mensual.agregar_por_mes(presencia, esfuerzo)

    ttl = CACHE_TTL_ANIO_EN_CURSO_SEGUNDOS if en_curso else CACHE_TTL_ANIO_CERRADO_SEGUNDOS
    return _con_cache(clave, ejecutar, ttl_segundos=ttl)


def consultar_actividad_mensual_rango(anios: list[int]) -> dict[str, dict]:
    """Une el resumen mensual de varios años. Secuencial, no con
    ejecutar_por_zonas: GFW rechaza (429) reportes de 4Wings simultáneos."""
    return {clave: datos for anio in anios for clave, datos in consultar_actividad_mensual_con_cache(anio).items()}


def consultar_barcos_mes_con_cache(anio: int, mes: int) -> list[dict]:
    """Embarcaciones vistas en un mes dentro del bbox de Lambayeque (vista
    "Histórico"), ver actividad_mensual.barcos_del_mes. Mismo criterio de TTL
    que consultar_actividad_mensual_con_cache: un mes cerrado casi no cambia,
    el mes en curso sí."""
    clave = f"barcos_mes|lambayeque|{anio}-{mes:02d}"
    hoy = date.today()
    en_curso = (anio, mes) >= (hoy.year, hoy.month)

    def ejecutar() -> list[dict]:
        geo = sync_lambayeque.construir_geojson_bbox(sync_lambayeque.LAMBAYEQUE_BBOX)
        desde = f"{anio}-{mes:02d}-01"
        siguiente = f"{anio + 1}-01-01" if mes == 12 else f"{anio}-{mes + 1:02d}-01"
        hasta = hoy.isoformat() if en_curso else siguiente
        # Secuencial: GFW rechaza (429) dos reportes de 4Wings a la vez.
        presencia = gfw_client.obtener_presencia_mes(desde, hasta, geo)
        esfuerzo = gfw_client.obtener_esfuerzo_mes(desde, hasta, geo)
        return actividad_mensual.barcos_del_mes(presencia, esfuerzo)

    ttl = CACHE_TTL_ANIO_EN_CURSO_SEGUNDOS if en_curso else CACHE_TTL_ANIO_CERRADO_SEGUNDOS
    return _con_cache(clave, ejecutar, ttl_segundos=ttl)
