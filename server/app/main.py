import os
import threading
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
    consultar_gfw_con_cache,
    consultar_probabilidad_zona_protegida_con_cache,
    iniciar_precarga_periodica,
)
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
from .routes.zonas import router as zonas_router

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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


def _precargar_irregularidades() -> None:
    for zona in zonas_criticas():
        consultar_gfw_con_cache(DEMO_DESDE, DEMO_HASTA, f"zona:{zona['id']}", zona["poligono"])
        consultar_probabilidad_zona_protegida_con_cache(DEMO_DESDE, DEMO_HASTA, f"zona:{zona['id']}", zona["poligono"])
        consultar_actividad_con_cache(ACTIVIDAD_DEMO_DESDE, ACTIVIDAD_DEMO_HASTA, f"zona:{zona['id']}", zona["poligono"])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # El .joblib pesa ~1.2GB: se carga una sola vez en un hilo de fondo para
    # no bloquear el arranque del servidor ni la primera petición que no
    # dependa de él.
    threading.Thread(target=modelo.precargar, name="precarga-modelo", daemon=True).start()
    iniciar_precarga_periodica("embarcaciones-lambayeque", _precargar_embarcaciones, _INTERVALO_PRECARGA_SEGUNDOS)
    iniciar_precarga_periodica("irregularidades", _precargar_irregularidades, _INTERVALO_PRECARGA_SEGUNDOS)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8787"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
