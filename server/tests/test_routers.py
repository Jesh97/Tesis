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


# --- usuarios ------------------------------------------------------------

_TOKEN_ADMIN = crear_token({"id": "00000000-0000-0000-0000-000000000001", "usuario": "admin", "rol": "administrador"})
_AUTH_ADMIN = {"Authorization": f"Bearer {_TOKEN_ADMIN}"}
_NUEVO_USUARIO = {"usuario": "J.Perez", "nombreCompleto": "Juan Pérez", "password": "clave-segura", "rol": "analista"}


def test_listar_usuarios_exige_administrador():
    resp = client.get("/api/usuarios", headers=_AUTH)  # _AUTH: rol "analista"
    assert resp.status_code == 403


def test_crear_usuario_exige_administrador():
    resp = client.post("/api/usuarios", headers=_AUTH, json=_NUEVO_USUARIO)
    assert resp.status_code == 403


def test_crear_usuario_no_permite_rol_administrador():
    resp = client.post("/api/usuarios", headers=_AUTH_ADMIN, json={**_NUEVO_USUARIO, "rol": "administrador"})
    assert resp.status_code == 400


def test_crear_usuario_rechaza_password_corta():
    resp = client.post("/api/usuarios", headers=_AUTH_ADMIN, json={**_NUEVO_USUARIO, "password": "corta"})
    assert resp.status_code == 400


def test_crear_usuario_guarda_hash_y_no_la_password(monkeypatch):
    import bcrypt

    creado = {"id": "u1", "usuario": "j.perez", "nombre_completo": "Juan Pérez", "rol": "analista"}
    cursor, fake = _cursor_falso(fetchone=creado)
    monkeypatch.setattr("app.routes.usuarios.get_cursor", fake)
    resp = client.post("/api/usuarios", headers=_AUTH_ADMIN, json=_NUEVO_USUARIO)
    assert resp.status_code == 201
    assert resp.json() == creado
    _sql, params = cursor.llamadas[0]
    usuario, password_hash, nombre, rol, creado_por = params
    assert usuario == "j.perez"
    assert password_hash != "clave-segura"
    assert bcrypt.checkpw(b"clave-segura", password_hash.encode())
    assert (nombre, rol) == ("Juan Pérez", "analista")
    assert creado_por == "00000000-0000-0000-0000-000000000001"


_ID_USUARIO = "00000000-0000-0000-0000-000000000009"


def test_cambiar_password_exige_administrador():
    resp = client.post(f"/api/usuarios/{_ID_USUARIO}/password", headers=_AUTH, json={"password": "otra-clave-1"})
    assert resp.status_code == 403


def test_cambiar_password_guarda_hash(monkeypatch):
    import bcrypt

    cursor, fake = _cursor_falso()
    monkeypatch.setattr("app.routes.usuarios.get_cursor", fake)
    resp = client.post(f"/api/usuarios/{_ID_USUARIO}/password", headers=_AUTH_ADMIN, json={"password": "otra-clave-1"})
    assert resp.status_code == 204
    _sql, (usuario_id, password_hash, admin_id) = cursor.llamadas[0]
    assert usuario_id == _ID_USUARIO
    assert bcrypt.checkpw(b"otra-clave-1", password_hash.encode())
    assert admin_id == "00000000-0000-0000-0000-000000000001"


def test_cambiar_password_rechaza_password_corta():
    resp = client.post(f"/api/usuarios/{_ID_USUARIO}/password", headers=_AUTH_ADMIN, json={"password": "corta"})
    assert resp.status_code == 400


def test_deshabilitar_usuario_exige_administrador():
    resp = client.post(f"/api/usuarios/{_ID_USUARIO}/estado", headers=_AUTH, json={"activo": False})
    assert resp.status_code == 403


def test_deshabilitar_usuario(monkeypatch):
    cursor, fake = _cursor_falso()
    monkeypatch.setattr("app.routes.usuarios.get_cursor", fake)
    resp = client.post(f"/api/usuarios/{_ID_USUARIO}/estado", headers=_AUTH_ADMIN, json={"activo": False})
    assert resp.status_code == 204
    assert cursor.llamadas[0][1] == (_ID_USUARIO, False, "00000000-0000-0000-0000-000000000001")


def test_cambiar_estado_sin_booleano_devuelve_400():
    resp = client.post(f"/api/usuarios/{_ID_USUARIO}/estado", headers=_AUTH_ADMIN, json={"activo": "no"})
    assert resp.status_code == 400
