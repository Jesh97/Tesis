"""Tests del límite general de solicitudes (server/app/rate_limit.py), que
complementa el bloqueo específico de /api/auth/login. No dependen de una
base de datos: /health no toca la BD y es la ruta más simple para golpear
muchas veces seguidas."""
from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import LIMITE_SOLICITUDES

client = TestClient(app, raise_server_exceptions=False)


def test_bajo_el_limite_no_bloquea():
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_health_no_tiene_limite():
    """/health está en _RUTAS_SIN_LIMITE porque lo golpea un chequeo de
    salud (uptime monitor, balanceador) a una frecuencia que no depende de
    un usuario real -- confirmamos que de verdad no cuenta para el límite
    pidiéndolo más veces de las que el límite general permitiría."""
    for _ in range(LIMITE_SOLICITUDES + 20):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_excede_el_limite_devuelve_429_con_headers_de_cors():
    for _ in range(LIMITE_SOLICITUDES):
        resp = client.get("/api/no-existe", headers={"Origin": "http://localhost:5173"})
        assert resp.status_code == 404

    resp = client.get("/api/no-existe", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 429
    assert resp.json() == {"error": "Demasiadas solicitudes. Intenta de nuevo en un minuto."}
    # Confirma que RateLimitMiddleware quedó DENTRO de CORSMiddleware (ver el
    # comentario en main.py sobre el orden de add_middleware): si estuviera
    # al revés, esta respuesta 429 saldría sin este header y el navegador la
    # reportaría como un error de CORS en vez de exponerle el 429 al frontend.
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
