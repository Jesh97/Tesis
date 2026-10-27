import os
import threading
from datetime import date
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import modelo
from .auth_dep import usuario_actual
from .gfw import (
    CACHE_TTL_SECONDS,
    consultar_actividad_con_cache,
    consultar_actividad_mensual_rango,
    consultar_barcos_mes_con_cache,
    consultar_gfw_con_cache,
    consultar_probabilidad_zona_protegida_con_cache,
    ejecutar_por_zonas,
    iniciar_precarga_periodica,
)
from .routes.actividad import rango_por_defecto, router as actividad_router
from .routes.auditoria import router as auditoria_router
from .routes.auth import router as auth_router
from .routes.embarcaciones import router as embarcaciones_router
from .routes.fuentes import router as fuentes_router
from .routes.incidentes import router as incidentes_router
from .routes.irregularidades import (
    ACTIVIDAD_DEMO_DESDE,
    ACTIVIDAD_DEMO_HASTA,
    DEMO_DESDE,
    DEMO_HASTA,
    router as irregularidades_router,
    zonas_criticas,
)
from .routes.reportes import router as reportes_router
from .routes.sugerencias import router as sugerencias_router
from .routes.usuarios import router as usuarios_router
from .routes.zonas import router as zonas_router
from .rate_limit import RateLimitMiddleware

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Orígenes desde los que el navegador puede llamar a esta API. La app en sí
# no depende de esto en dev (Vite hace de proxy same-origin para /api, ver
# vite.config.ts), pero sin restringirlo cualquier página en cualquier
# dominio podría invocar la API desde el navegador de un usuario logueado.
# En producción, definir CORS_ORIGINS con el/los dominios reales del frontend.
_CORS_ORIGINS_POR_DEFECTO = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _CORS_ORIGINS_POR_DEFECTO).split(",") if o.strip()]

# Refresca el cache un poco antes de que expire (en vez de dejarlo vencer y
# recién recalcular cuando un usuario entra a la página) para que los barcos
# ya estén listos apenas se abre el sistema, y se mantengan así mientras el
# servidor sigue corriendo.
_INTERVALO_PRECARGA_SEGUNDOS = max(60, CACHE_TTL_SECONDS - 60)


# Misma ventana fija que RANGO_POR_DEFECTO en MonitoringPage.tsx (verificada
# en vivo: sí devuelve embarcaciones dentro del bbox de Lambayeque). Hay que
# precargar exactamente esta clave de cache para que coincida con lo que pide
# el frontend por defecto.
_RANGO_LAMBAYEQUE_DESDE = "2023-06-01"
_RANGO_LAMBAYEQUE_HASTA = "2023-09-01"


def _precargar_embarcaciones() -> None:
    consultar_gfw_con_cache(_RANGO_LAMBAYEQUE_DESDE, _RANGO_LAMBAYEQUE_HASTA, "lambayeque")


def _precargar_una_zona(zona: dict) -> None:
    consultar_gfw_con_cache(DEMO_DESDE, DEMO_HASTA, f"zona:{zona['id']}", zona["poligono"])
    consultar_probabilidad_zona_protegida_con_cache(DEMO_DESDE, DEMO_HASTA, f"zona:{zona['id']}", zona["poligono"])
    consultar_actividad_con_cache(ACTIVIDAD_DEMO_DESDE, ACTIVIDAD_DEMO_HASTA, f"zona:{zona['id']}", zona["poligono"])


def _precargar_actividad_mensual() -> None:
    # Los años del rango por defecto de la vista "Tendencias" (ver
    # rango_por_defecto en routes/actividad.py). Una vez en cache (TTL de
    # días/horas, ver gfw.py) las vueltas siguientes de este loop no tocan GFW.
    desde, hasta = rango_por_defecto(date.today())
    consultar_actividad_mensual_rango(list(range(int(desde[:4]), int(hasta[:4]) + 1)))


# Vista "Histórico": los últimos meses cerrados, del más reciente (el que se
# abre por defecto) hacia atrás. Cada mes fuera de cache son ~20MB de GFW y
# ~5-10s, así que se precargan solo los más probables de consultarse; el
# resto se pide bajo demanda al moverse por la línea de tiempo.
_MESES_HISTORICO_PRECARGA = 12


def _precargar_historico() -> None:
    hoy = date.today()
    for atras in range(1, _MESES_HISTORICO_PRECARGA + 1):
        total = hoy.year * 12 + (hoy.month - 1) - atras
        consultar_barcos_mes_con_cache(total // 12, total % 12 + 1)


def _precargar_irregularidades() -> None:
    # Zonas en paralelo (acotado, ver MAX_ZONAS_CONCURRENTES en gfw.py): cada
    # una tarda ~10-20s en GFW, y hacerlas una por una dejaba el cache frío
    # por más de un minuto después de arrancar el servidor.
    ejecutar_por_zonas(zonas_criticas(), _precargar_una_zona)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # El .joblib pesa ~1.2GB: se carga una sola vez en un hilo de fondo para
    # no bloquear el arranque del servidor ni la primera petición que no
    # dependa de él.
    threading.Thread(target=modelo.precargar, name="precarga-modelo", daemon=True).start()
    iniciar_precarga_periodica("embarcaciones-lambayeque", _precargar_embarcaciones, _INTERVALO_PRECARGA_SEGUNDOS)
    iniciar_precarga_periodica("irregularidades", _precargar_irregularidades, _INTERVALO_PRECARGA_SEGUNDOS)
    iniciar_precarga_periodica("actividad-mensual", _precargar_actividad_mensual, _INTERVALO_PRECARGA_SEGUNDOS)
    iniciar_precarga_periodica("historico", _precargar_historico, _INTERVALO_PRECARGA_SEGUNDOS)
    yield


app = FastAPI(lifespan=lifespan)

# El orden de los add_middleware() importa: Starlette envuelve el último
# agregado por afuera de los anteriores, así que CORS (agregado después)
# queda por fuera de RateLimitMiddleware. Si estuviera al revés, una
# respuesta 429 (que corta antes de llegar a CORS) saldría sin los headers
# de CORS y el navegador la reportaría como un error de CORS en vez de
# dejarle ver el 429 real al frontend.
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request, exc: StarletteHTTPException):
    detail = exc.detail
    content = detail if isinstance(detail, dict) and "error" in detail else {"error": detail}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    primer_error = exc.errors()[0]
    campo = primer_error["loc"][-1]
    return JSONResponse(status_code=400, content={"error": f'Campo inválido o faltante: "{campo}"'})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception):
    # Sin esto, cualquier excepción que no sea un HTTPException (un bug, la
    # BD caída, GFW inalcanzable, el pool de conexiones agotado) se le
    # devolvía al navegador sin el contrato {"error": ...} que usa el resto
    # de la API -- el frontend cae al mensaje genérico "Error 500" en vez de
    # uno propio, y acá no quedaba registro de qué pasó realmente. Se
    # imprime el traceback completo al log del servidor (para diagnosticar)
    # y se responde siempre JSON, sin importar qué reviente adentro.
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(status_code=500, content={"error": "Error interno del servidor"})


@app.get("/health")
def health():
    return {"ok": True}


# Todo lo que no sea /api/auth/login o /health exige sesión (Authorization: Bearer <token>).
_protegida = [Depends(usuario_actual)]

app.include_router(auth_router, prefix="/api/auth")
app.include_router(fuentes_router, prefix="/api/fuentes", dependencies=_protegida)
app.include_router(sugerencias_router, prefix="/api/sugerencias", dependencies=_protegida)
app.include_router(embarcaciones_router, prefix="/api/embarcaciones", dependencies=_protegida)
app.include_router(zonas_router, prefix="/api/zonas", dependencies=_protegida)
app.include_router(irregularidades_router, prefix="/api/irregularidades", dependencies=_protegida)
app.include_router(incidentes_router, prefix="/api/incidentes", dependencies=_protegida)
app.include_router(reportes_router, prefix="/api/reportes", dependencies=_protegida)
app.include_router(actividad_router, prefix="/api/actividad", dependencies=_protegida)
app.include_router(auditoria_router, prefix="/api/auditoria", dependencies=_protegida)
app.include_router(usuarios_router, prefix="/api/usuarios", dependencies=_protegida)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8787"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
