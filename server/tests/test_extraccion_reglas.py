"""Tests deterministas de scripts/extraccion_reglas.py contra artículos
reales guardados como fixtures (server/tests/fixtures_noticias.json). No
hacen red: el texto ya está descargado y limpiado (mismo _limpiar_texto que
usa analyze_news.py), así que corren en cualquier máquina/CI.

Cada caso viene de una URL real probada a mano (ver fixtures_noticias.json
para la URL exacta) -- si un cambio en extraccion_reglas.py rompe alguno de
estos, es una regresión real sobre un artículo que sabemos que debía
funcionar así, no un falso positivo del test."""
import json
from pathlib import Path

import pytest

import extraccion_reglas

FIXTURES = json.loads((Path(__file__).parent / "fixtures_noticias.json").read_text(encoding="utf-8"))


def _extraer(clave: str) -> extraccion_reglas.ExtraccionLocal:
    fixture = FIXTURES[clave]
    return extraccion_reglas.extraer(fixture["titulo"], fixture["texto"])


# ---------------------------------------------------------------------------
# Casos que SÍ describen un hecho concreto: deben quedar relevantes, con
# tipo de infracción, embarcación y ubicación razonables.
# ---------------------------------------------------------------------------

CASOS_RELEVANTES = [
    # (clave del fixture, tipo_infraccion esperado, embarcación esperada)
    ("zorritos", "Falta de Permiso", "María Victoria B"),
    ("flota_china", "Pérdida de Señal AIS", "Lu Rong Yuan Yu 698"),
    ("paracas", "Pesca en Zona Prohibida", "Alejandría I"),
    ("derrame_petroperu", "Contaminación", "POLYAIGOS"),
    ("talara", "Falta de Permiso", "Milagroso Cautivo"),
    ("sonapescal_tian_xiang", "Falta de Permiso", "Tian Xiang"),
    ("rossana_l", "Incursión en Zona Económica Exclusiva", "Rossana L"),
    ("hong_run_668", "Visita a Puerto no Autorizado", "Hong Run 668"),
    ("mantaro_malpelo", "Pesca en Zona Prohibida", "Mantaro"),
]


@pytest.mark.parametrize("clave,tipo_esperado,embarcacion_esperada", CASOS_RELEVANTES)
def test_articulo_relevante_clasifica_bien(clave, tipo_esperado, embarcacion_esperada):
    resultado = _extraer(clave)
    assert resultado.es_relevante is True
    assert resultado.tipo_infraccion == tipo_esperado
    assert resultado.embarcacion_detectada == embarcacion_esperada


def test_talara_extrae_matricula():
    # Único fixture que trae matrícula explícita en el texto ("37499-BM").
    resultado = _extraer("talara")
    assert resultado.matricula_detectada == "37499-BM"


def test_rossana_l_no_confunde_175_millas_con_5_millas():
    # Regresión: "175 millas de la costa" contiene "5 millas..." como
    # substring puro -- _contar_coincidencias debe respetar el límite del
    # número y no clasificarlo como "Pesca en Zona Prohibida" por error.
    resultado = _extraer("rossana_l")
    assert resultado.tipo_infraccion != "Pesca en Zona Prohibida"


def test_mantaro_malpelo_detecta_zona_prohibida_por_distancia_numerica():
    # Regresión: el artículo dice "pesca tipo arrastre a 3.5 millas de
    # tierra... en aguas destinadas a la pesca artesanal", sin decir nunca
    # "zona prohibida" ni "5 millas" -- antes del fix, tipo_infraccion salía
    # None pese a que 3.5mn < 5mn es exactamente la infracción de la reserva
    # artesanal (RESERVA_ARTESANAL_NM en extraccion_reglas.py y en
    # server/app/features.py).
    resultado = _extraer("mantaro_malpelo")
    assert resultado.tipo_infraccion == "Pesca en Zona Prohibida"


def test_mantaro_malpelo_no_confunde_nombre_de_embarcacion_con_ubicacion():
    # Regresión: spaCy etiquetaba "Mantaro" (la embarcación infractora) y
    # "Río Piura" (la patrullera que intervino) como LOC por error --
    # ambos coinciden con nombres de ríos/lugares peruanos reales -- y como
    # se repiten más veces que "Tumbes"/"Punta Malpelo", ganaban por
    # frecuencia y pisaban la ubicación real del hecho.
    resultado = _extraer("mantaro_malpelo")
    assert resultado.ubicacion_estimada not in ("Mantaro", "Río Piura")


# ---------------------------------------------------------------------------
# Casos que NO describen un hecho concreto (informe general, conferencia,
# nota económica): deben quedar descartados, no en la cola de validación.
# ---------------------------------------------------------------------------

CASOS_NO_RELEVANTES = ["exportaciones", "rpp_informe", "wwf_produce", "trazabilidad"]


@pytest.mark.parametrize("clave", CASOS_NO_RELEVANTES)
def test_articulo_generico_se_descarta(clave):
    resultado = _extraer(clave)
    assert resultado.es_relevante is False
    assert resultado.tipo_infraccion is None
    assert resultado.embarcacion_detectada is None
