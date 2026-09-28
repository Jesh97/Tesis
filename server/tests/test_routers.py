"""Tests de los routers que antes no tenían ninguna cobertura: embarcaciones,
reportes, zonas (listar), sugerencias y fuentes. Igual que test_main.py, no
tocan una base de datos real -- get_cursor se reemplaza por un doble de
prueba donde hace falta, y los casos de validación pura ni siquiera llegan
a llamarlo."""
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth_dep import crear_token
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

_TOKEN = crear_token({"id": "00000000-0000-0000-0000-000000000003", "usuario": "analista", "rol": "analista"})
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


class _CursorEspia:
    def __init__(self, fetchone=None, fetchall=None):
        self.llamadas: list[tuple[str, tuple]] = []
        self._fetchone = fetchone
        self._fetchall = fetchall if fetchall is not None else []

    def execute(self, sql, params=()):
        self.llamadas.append((sql, params))

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall


def _cursor_falso(**kwargs):
    cursor = _CursorEspia(**kwargs)

    @contextmanager
    def _fake():
        yield cursor

    return cursor, _fake


# --- embarcaciones -----------------------------------------------------

def test_buscar_embarcacion_sin_mmsi_ni_nombre_devuelve_400():
    resp = client.get("/api/embarcaciones/buscar", headers=_AUTH)
    assert resp.status_code == 400
    assert resp.json() == {"error": 'Se requiere "mmsi" o "nombre"'}


def test_buscar_embarcacion_sin_resultados(monkeypatch):
    monkeypatch.setattr("app.routes.embarcaciones.consultar_gfw_con_cache", lambda *_a, **_kw: [])
    resp = client.get("/api/embarcaciones/buscar", headers=_AUTH, params={"mmsi": "123456789"})
    assert resp.status_code == 200
    assert resp.json() == {"encontrado": False}


def test_buscar_embarcacion_encuentra_por_mmsi(monkeypatch):
    barcos = [{"mmsi": "123456789", "nombre": "Don Pepe", "flag": "PER", "vesselType": "FISHING", "lat": -6.5, "lon": -80.1}]
    monkeypatch.setattr("app.routes.embarcaciones.consultar_gfw_con_cache", lambda *_a, **_kw: barcos)
    resp = client.get("/api/embarcaciones/buscar", headers=_AUTH, params={"mmsi": "123456789"})
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["encontrado"] is True
    assert cuerpo["barco"]["nombre"] == "Don Pepe"
    assert cuerpo["barco"]["tipo"] == "pesca_industrial"


def test_gfw_lambayeque_falla_devuelve_502(monkeypatch):
    def _falla(*_a, **_kw):
        raise RuntimeError("GFW no disponible")

    monkeypatch.setattr("app.routes.embarcaciones.consultar_gfw_con_cache", _falla)
    resp = client.get("/api/embarcaciones/gfw/lambayeque", headers=_AUTH)
    assert resp.status_code == 502


# --- reportes ------------------------------------------------------------

def test_reportes_resumen(monkeypatch):
    resumen = {"total_incidentes": 12, "confirmados": 5, "pendientes": 7, "zonas_criticas": 3}
    _cursor, fake = _cursor_falso(fetchone=resumen)
    monkeypatch.setattr("app.routes.reportes.get_cursor", fake)
    resp = client.get("/api/reportes/resumen", headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json() == resumen


def test_reportes_incidentes_por_mes(monkeypatch):
    filas = [{"mes": "2026-01", "total": 4}]
    _cursor, fake = _cursor_falso(fetchall=filas)
    monkeypatch.setattr("app.routes.reportes.get_cursor", fake)
    resp = client.get("/api/reportes/incidentes-por-mes", headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json() == filas


# --- zonas (listar) --------------------------------------------------------

def test_listar_zonas_no_exige_rol_especifico(monkeypatch):
    zonas = [{"id": "z1", "nombre": "Bahía X", "region": "Lambayeque"}]
    _cursor, fake = _cursor_falso(fetchall=zonas)
    monkeypatch.setattr("app.routes.zonas.get_cursor", fake)
    resp = client.get("/api/zonas", headers=_AUTH)  # _AUTH: rol "analista"
    assert resp.status_code == 200
    assert resp.json() == zonas


# --- sugerencias -----------------------------------------------------------

def test_listar_sugerencias(monkeypatch):
    pendientes = [{"id": "s1", "titular": "Denuncian pesca ilegal"}]
    _cursor, fake = _cursor_falso(fetchall=pendientes)
    monkeypatch.setattr("app.routes.sugerencias.get_cursor", fake)
    resp = client.get("/api/sugerencias", headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json() == pendientes


def test_rechazar_sugerencia_reenvia_el_usuario_id(monkeypatch):
    cursor, fake = _cursor_falso()
    monkeypatch.setattr("app.routes.sugerencias.get_cursor", fake)
    resp = client.post("/api/sugerencias/00000000-0000-0000-0000-0000000000aa/rechazar", headers=_AUTH)
    assert resp.status_code == 204
    _sql, params = cursor.llamadas[-1]
    assert params == ("00000000-0000-0000-0000-0000000000aa", "00000000-0000-0000-0000-000000000003")


def test_aprobar_sugerencia_no_encontrada_devuelve_404(monkeypatch):
    _cursor, fake = _cursor_falso(fetchone=None)
    monkeypatch.setattr("app.routes.sugerencias.get_cursor", fake)
    resp = client.post("/api/sugerencias/00000000-0000-0000-0000-0000000000bb/aprobar", headers=_AUTH)
    assert resp.status_code == 404
    assert resp.json() == {"error": "Sugerencia no encontrada o ya procesada"}


# --- fuentes ---------------------------------------------------------------

def test_analizar_fuentes_sin_urls_devuelve_400():
    resp = client.post("/api/fuentes/analizar", headers=_AUTH, json={"urls": []})
    assert resp.status_code == 400


def test_analizar_fuentes_supera_el_limite_devuelve_400():
    resp = client.post("/api/fuentes/analizar", headers=_AUTH, json={"urls": [f"https://x.com/{i}" for i in range(11)]})
    assert resp.status_code == 400
    assert "Máximo" in resp.json()["error"]
