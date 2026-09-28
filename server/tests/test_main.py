"""Tests de la capa HTTP (app/main.py y las rutas protegidas): autenticación,
validación de entrada y manejo de errores no esperados. Ninguno toca una base
de datos real -- cubren los caminos que responden antes de llegar a
ejecutar_sp/get_cursor (401 de autenticación, 400 de validación, 404 de ruta
inexistente) o con get_cursor reemplazado por un doble de prueba (para el 500
genérico y para inspeccionar qué se le pasó a la SP de auditoría), así que
corren en cualquier máquina/CI igual que el resto de la suite."""
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth_dep import crear_token
from app.main import app

_TOKEN_ANALISTA = crear_token({"id": "00000000-0000-0000-0000-000000000001", "usuario": "analista", "rol": "analista"})
_TOKEN_ADMIN = crear_token({"id": "00000000-0000-0000-0000-000000000002", "usuario": "admin", "rol": "administrador"})


# raise_server_exceptions=False: TestClient por defecto vuelve a lanzar
# cualquier excepción no manejada además de haber recibido la respuesta 500
# (ServerErrorMiddleware de Starlette la relanza a propósito para que quede
# en el log del servidor real) -- acá se necesita la respuesta, no el
# traceback, para poder afirmar sobre el contrato {"error": ...} que sí
# recibiría el navegador.
client = TestClient(app, raise_server_exceptions=False)

_TOKEN_VALIDO = crear_token({"id": "00000000-0000-0000-0000-000000000000", "usuario": "test", "rol": "analista"})
_AUTH = {"Authorization": f"Bearer {_TOKEN_VALIDO}"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_ruta_protegida_sin_token_devuelve_401():
    resp = client.get("/api/incidentes")
    assert resp.status_code == 401
    assert resp.json() == {"error": "No autenticado"}


def test_ruta_protegida_con_token_invalido_devuelve_401():
    resp = client.get("/api/incidentes", headers={"Authorization": "Bearer token-basura"})
    assert resp.status_code == 401
    assert resp.json() == {"error": "Sesión inválida o expirada"}


def test_ruta_inexistente_devuelve_404():
    resp = client.get("/api/no-existe")
    assert resp.status_code == 404


def test_login_sin_usuario_o_password_devuelve_400():
    resp = client.post("/api/auth/login", json={"usuario": "ana"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Se requiere usuario y password"}


def test_registrar_incidente_sin_descripcion_devuelve_400():
    resp = client.post("/api/incidentes", headers=_AUTH, json={"mmsi": "123456789"})
    assert resp.status_code == 400
    assert resp.json() == {"error": 'Falta "descripcion"'}


def test_registrar_incidente_sin_mmsi_ni_vessel_devuelve_400():
    resp = client.post("/api/incidentes", headers=_AUTH, json={"descripcion": "prueba"})
    assert resp.status_code == 400
    assert resp.json() == {"error": 'Se requiere "mmsi" o "vessel"'}


def test_crear_zona_con_menos_de_3_coordenadas_devuelve_400():
    # Token de administrador: este test cubre la validación de forma del
    # body, no el control de rol (ver test_crear_zona_como_analista_devuelve_403).
    resp = client.post(
        "/api/zonas",
        headers={"Authorization": f"Bearer {_TOKEN_ADMIN}"},
        json={"nombre": "Zona X", "region": "Lambayeque", "coordenadas": [{"lat": 1, "lon": 1}]},
    )
    assert resp.status_code == 400
    assert "coordenadas" in resp.json()["error"]


_ZONA_VALIDA = {
    "nombre": "Zona X",
    "region": "Lambayeque",
    "coordenadas": [{"lat": 1, "lon": 1}, {"lat": 2, "lon": 2}, {"lat": 3, "lon": 1}],
}


def test_crear_zona_como_analista_devuelve_403():
    resp = client.post("/api/zonas", headers={"Authorization": f"Bearer {_TOKEN_ANALISTA}"}, json=_ZONA_VALIDA)
    assert resp.status_code == 403
    assert resp.json() == {"error": "No tienes permiso para realizar esta acción"}


def test_eliminar_zona_como_analista_devuelve_403():
    resp = client.delete(
        "/api/zonas/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {_TOKEN_ANALISTA}"},
    )
    assert resp.status_code == 403


def test_crear_zona_como_administrador_pasa_el_control_de_rol(monkeypatch):
    """No verifica el resultado final (necesitaría BD real): solo confirma
    que a un administrador requiere_rol lo deja pasar -- si lo bloqueara,
    esto devolvería 403 en vez de llegar a fallar más adelante contra la
    base de datos (simulada acá con un RuntimeError marcador)."""

    def _bd_simulada(*_args, **_kwargs):
        raise RuntimeError("marcador: se llegó hasta la base de datos")

    monkeypatch.setattr("app.routes.zonas.get_cursor", _bd_simulada)
    resp = client.post("/api/zonas", headers={"Authorization": f"Bearer {_TOKEN_ADMIN}"}, json=_ZONA_VALIDA)
    assert resp.status_code == 500  # no 403: el rol pasó, lo que falla es la BD simulada


class _CursorEspia:
    """Cursor de prueba que guarda cada SQL+parámetros ejecutado, para poder
    afirmar sobre qué le llega a la SP (p.ej. que el usuario_id del token
    realmente se reenvía) sin tocar una base de datos real."""

    def __init__(self):
        self.llamadas: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.llamadas.append((sql, params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


def test_confirmar_incidente_reenvia_el_usuario_id_a_la_sp(monkeypatch):
    """La auditoría (sp_incidentes_confirmar) depende de que la ruta le pase
    el "sub" del token -- si alguien cambia esa clave en el JWT o rompe el
    Depends(usuario_actual) de la ruta, este test debe fallar."""
    cursor_espia = _CursorEspia()

    @contextmanager
    def _cursor_fake():
        yield cursor_espia

    monkeypatch.setattr("app.routes.incidentes.get_cursor", _cursor_fake)
    resp = client.post("/api/incidentes/COD-1/confirmar", headers=_AUTH)
    assert resp.status_code == 204
    _sql, params = cursor_espia.llamadas[-1]
    assert params == ("COD-1", "00000000-0000-0000-0000-000000000000")


def test_auditoria_como_analista_devuelve_403():
    resp = client.get("/api/auditoria", headers=_AUTH)  # _AUTH: rol "analista"
    assert resp.status_code == 403


def test_auditoria_como_administrador_pasa_el_control_de_rol(monkeypatch):
    cursor_espia = _CursorEspia()

    @contextmanager
    def _cursor_fake():
        yield cursor_espia

    monkeypatch.setattr("app.routes.auditoria.get_cursor", _cursor_fake)
    resp = client.get("/api/auditoria?limite=7", headers={"Authorization": f"Bearer {_TOKEN_ADMIN}"})
    assert resp.status_code == 200
    _sql, params = cursor_espia.llamadas[-1]
    assert params == (7,)


def test_error_no_manejado_devuelve_json_500_en_vez_de_tumbar_el_servidor(monkeypatch):
    """Fuerza una excepción imprevista (no un error de negocio traducido por
    ejecutar_sp) dentro de una ruta protegida y confirma que el handler
    genérico de main.py la convierte en un 500 con el mismo contrato
    {"error": ...} que usa el resto de la API, en vez de una respuesta sin
    JSON o un traceback filtrado al cliente."""

    def _pool_caido(*_args, **_kwargs):
        raise RuntimeError("fallo simulado: pool de conexiones agotado")

    monkeypatch.setattr("app.routes.incidentes.get_cursor", _pool_caido)

    resp = client.get("/api/incidentes", headers=_AUTH)

    assert resp.status_code == 500
    assert resp.json() == {"error": "Error interno del servidor"}
