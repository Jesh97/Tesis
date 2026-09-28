"""Tests del bloqueo por intentos fallidos en /api/auth/login (app/routes/auth.py).
Mockea get_cursor para simular "usuario no encontrado" sin tocar una base de
datos real -- el límite de intentos se revisa antes de llegar a la BD en la
mayoría de los casos, pero un intento fallido real (contraseña incorrecta)
necesita completar el flujo normal para quedar registrado, de ahí el mock."""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.routes.auth as auth_module
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


@contextmanager
def _cursor_que_no_encuentra_usuario():
    cur = MagicMock()
    cur.fetchone.return_value = None
    yield cur


@pytest.fixture(autouse=True)
def _sin_intentos_previos():
    auth_module._intentos_fallidos.clear()
    yield
    auth_module._intentos_fallidos.clear()


def test_login_bloquea_tras_varios_intentos_fallidos_seguidos(monkeypatch):
    monkeypatch.setattr(auth_module, "get_cursor", _cursor_que_no_encuentra_usuario)

    for _ in range(auth_module._INTENTOS_MAXIMOS):
        resp = client.post("/api/auth/login", json={"usuario": "ana", "password": "incorrecta"})
        assert resp.status_code == 401

    resp = client.post("/api/auth/login", json={"usuario": "ana", "password": "incorrecta"})
    assert resp.status_code == 429
    assert "Demasiados intentos" in resp.json()["error"]


def test_login_no_bloquea_a_otro_usuario_aunque_comparta_ip(monkeypatch):
    monkeypatch.setattr(auth_module, "get_cursor", _cursor_que_no_encuentra_usuario)

    for _ in range(auth_module._INTENTOS_MAXIMOS):
        client.post("/api/auth/login", json={"usuario": "ana", "password": "incorrecta"})

    # Misma IP de TestClient, usuario distinto -> clave (ip, usuario) distinta,
    # no debería heredar el bloqueo de "ana".
    resp = client.post("/api/auth/login", json={"usuario": "otro-usuario", "password": "incorrecta"})
    assert resp.status_code == 401


def test_login_exitoso_no_cuenta_como_intento_fallido(monkeypatch):
    """Encadena intentos fallidos y luego uno exitoso: el éxito debe limpiar
    el contador (_limpiar_intentos), no sumarse a él."""
    fila_valida = {
        "id": "1",
        "usuario": "ana",
        "nombre_completo": "Ana Torres",
        "rol": "analista",
        "activo": True,
        "password_hash": auth_module._HASH_SEÑUELO,
    }

    @contextmanager
    def _cursor_usuario_valido():
        cur = MagicMock()
        cur.fetchone.return_value = fila_valida
        yield cur

    monkeypatch.setattr(auth_module, "get_cursor", _cursor_que_no_encuentra_usuario)
    for _ in range(auth_module._INTENTOS_MAXIMOS - 1):
        resp = client.post("/api/auth/login", json={"usuario": "ana", "password": "cualquiera"})
        assert resp.status_code == 401

    monkeypatch.setattr(auth_module, "get_cursor", _cursor_usuario_valido)
    monkeypatch.setattr(auth_module.bcrypt, "checkpw", lambda *_a, **_kw: True)
    resp = client.post("/api/auth/login", json={"usuario": "ana", "password": "correcta"})
    assert resp.status_code == 200

    # Si el éxito no hubiera limpiado el contador, este intento (el nro.
    # _INTENTOS_MAXIMOS + 1 fallido de la ronda anterior) ya estaría bloqueado.
    monkeypatch.setattr(auth_module, "get_cursor", _cursor_que_no_encuentra_usuario)
    monkeypatch.setattr(auth_module.bcrypt, "checkpw", lambda *_a, **_kw: False)
    resp = client.post("/api/auth/login", json={"usuario": "ana", "password": "incorrecta"})
    assert resp.status_code == 401
