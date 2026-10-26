"""Tests de la vista "Tendencias": la agregación mes a mes (pura, con filas de
GFW armadas a mano) y la validación de rango de /api/actividad/mensual, sin
tocar GFW real (consultar_actividad_mensual_rango se reemplaza)."""
from datetime import date

from fastapi.testclient import TestClient

from app.actividad_mensual import agregar_por_mes
from app.auth_dep import crear_token
from app.main import app
from app.routes.actividad import rango_por_defecto

client = TestClient(app, raise_server_exceptions=False)

_TOKEN = crear_token({"id": "00000000-0000-0000-0000-000000000003", "usuario": "analista", "rol": "analista"})
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


def _presencia(vessel_id, mes, flag="PER", vessel_type="FISHING", horas=1.0):
    return {"vesselId": vessel_id, "date": mes, "flag": flag, "vesselType": vessel_type, "hours": horas}


def _esfuerzo(vessel_id, mes, lat, lon, horas, nombre="BARCO", flag="PER"):
    return {
        "vesselId": vessel_id, "date": mes, "lat": lat, "lon": lon, "hours": horas,
        "shipName": nombre, "mmsi": "760000001", "flag": flag,
    }


# --- agregación ---------------------------------------------------------

def test_agregar_cuenta_cada_barco_una_vez_por_mes():
    esfuerzo = [
        _esfuerzo("a", "2025-07", -7.1, -80.5, 2.0),
        _esfuerzo("a", "2025-07", -7.0, -80.4, 3.0),  # mismo barco, otra celda
        _esfuerzo("b", "2025-07", -7.1, -80.5, 1.0),
    ]
    resultado = agregar_por_mes([], esfuerzo)["2025-07"]
    assert resultado["buquesPescando"] == 2
    assert resultado["horasPesca"] == 6.0
    # Celdas sumadas entre barcos: (-7.1, -80.5) tiene 2 + 1.
    assert sorted(resultado["celdas"]) == [[-7.1, -80.5, 3.0], [-7.0, -80.4, 3.0]]
    assert [b["vesselId"] for b in resultado["topBuques"]] == ["a", "b"]
    assert resultado["topBuques"][0]["horas"] == 5.0


def test_agregar_banderas_solo_cuenta_pesqueros():
    presencia = [
        _presencia("a", "2025-11", flag="PER"),
        _presencia("b", "2025-11", flag="CHN"),
        _presencia("c", "2025-11", flag="CHN"),
        _presencia("d", "2025-11", flag=""),
        # Mercante en tránsito: cuenta en la presencia total, no en la flota pesquera.
        _presencia("e", "2025-11", flag="LBR", vessel_type="CARGO"),
    ]
    resultado = agregar_por_mes(presencia, [])["2025-11"]
    assert resultado["buquesPresentes"] == 5
    assert resultado["porTipo"] == {"FISHING": 4, "CARGO": 1}
    assert resultado["pesquerosPresentes"] == 4
    assert resultado["porBanderaPesqueros"] == {"PER": 1, "CHN": 2, "Desconocida": 1}
    # Ni la bandera local ni la desconocida cuentan como extranjeras.
    assert resultado["pesquerosExtranjeros"] == 2


def test_agregar_separa_meses_e_ignora_filas_sin_vessel_id():
    presencia = [_presencia("a", "2025-01"), _presencia("a", "2025-02"), {"vesselId": "", "date": "2025-01"}]
    resultado = agregar_por_mes(presencia, [])
    assert set(resultado) == {"2025-01", "2025-02"}
    assert resultado["2025-01"]["buquesPresentes"] == 1


# --- ruta -----------------------------------------------------------------

def test_rango_por_defecto_son_24_meses_cerrados():
    assert rango_por_defecto(date(2026, 10, 24)) == ("2024-10", "2026-09")
    assert rango_por_defecto(date(2026, 1, 5)) == ("2024-01", "2025-12")


def test_mensual_formato_invalido_devuelve_400():
    resp = client.get("/api/actividad/mensual", headers=_AUTH, params={"desde": "2025-13", "hasta": "2025-12"})
    assert resp.status_code == 400
    assert resp.json() == {"error": '"desde" debe tener el formato AAAA-MM'}


def test_mensual_rango_invertido_o_muy_largo_devuelve_400():
    resp = client.get("/api/actividad/mensual", headers=_AUTH, params={"desde": "2025-06", "hasta": "2025-01"})
    assert resp.status_code == 400
    resp = client.get("/api/actividad/mensual", headers=_AUTH, params={"desde": "2020-01", "hasta": "2025-01"})
    assert resp.status_code == 400
    assert "36 meses" in resp.json()["error"]


def test_mensual_completa_meses_sin_datos_con_ceros(monkeypatch):
    pedidos = []

    def falso(anios):
        pedidos.extend(anios)
        return agregar_por_mes([_presencia("a", "2024-12")], [])

    monkeypatch.setattr("app.routes.actividad.consultar_actividad_mensual_rango", falso)
    resp = client.get("/api/actividad/mensual", headers=_AUTH, params={"desde": "2024-11", "hasta": "2025-02"})
    assert resp.status_code == 200
    datos = resp.json()
    assert pedidos == [2024, 2025]
    assert [m["mes"] for m in datos["meses"]] == ["2024-11", "2024-12", "2025-01", "2025-02"]
    assert [m["buquesPresentes"] for m in datos["meses"]] == [0, 1, 0, 0]
    assert not any(m["parcial"] for m in datos["meses"])


def test_mensual_error_de_gfw_devuelve_502(monkeypatch):
    def falla(_anios):
        raise RuntimeError("Falta GFW_API_TOKEN")

    monkeypatch.setattr("app.routes.actividad.consultar_actividad_mensual_rango", falla)
    resp = client.get("/api/actividad/mensual", headers=_AUTH, params={"desde": "2025-01", "hasta": "2025-02"})
    assert resp.status_code == 502
    assert resp.json() == {"error": "Falta GFW_API_TOKEN"}


def test_mensual_sin_sesion_devuelve_401():
    assert client.get("/api/actividad/mensual").status_code == 401


# --- histórico ------------------------------------------------------------

def test_barcos_del_mes_posicion_y_pesca():
    from app.actividad_mensual import barcos_del_mes

    presencia = [
        {"vesselId": "p", "lat": -7.0, "lon": -80.0, "hours": 10, "shipName": "PESQ", "vesselType": "FISHING"},
        {"vesselId": "p", "lat": -6.5, "lon": -80.5, "hours": 2, "shipName": "PESQ", "vesselType": "FISHING"},
        {"vesselId": "c", "lat": -6.2, "lon": -82.0, "hours": 5, "shipName": "CARGUERO", "vesselType": "CARGO"},
    ]
    esfuerzo = [{"vesselId": "p", "lat": -6.5, "lon": -80.5, "hours": 1.5, "shipName": "PESQ", "vesselType": "FISHING"}]
    barcos = {b["vesselId"]: b for b in barcos_del_mes(presencia, esfuerzo)}

    # Si pescó, se ubica donde pescó (aunque haya pasado más tiempo en otra celda).
    assert (barcos["p"]["lat"], barcos["p"]["lon"]) == (-6.5, -80.5)
    assert barcos["p"]["pescando"] is True
    assert barcos["p"]["horas"] == 1.5
    assert barcos["p"]["horasPresencia"] == 12
    assert barcos["c"]["pescando"] is False
    assert barcos["c"]["horas"] == 0


def test_historico_valida_mes(monkeypatch):
    monkeypatch.setattr("app.routes.actividad.consultar_barcos_mes_con_cache", lambda *_a: [])
    assert client.get("/api/actividad/historico", headers=_AUTH, params={"mes": "2025-1"}).status_code == 400
    assert client.get("/api/actividad/historico", headers=_AUTH, params={"mes": "2999-01"}).status_code == 400
    resp = client.get("/api/actividad/historico", headers=_AUTH, params={"mes": "2025-08"})
    assert resp.status_code == 200
    assert resp.json() == {"mes": "2025-08", "parcial": False, "total": 0, "pescando": 0, "barcos": []}
