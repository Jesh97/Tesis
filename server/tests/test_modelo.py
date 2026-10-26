"""Test de integración del modelo entrenado (app/modelo.py). No revalida la
precisión del modelo -- eso ya lo reporta scripts/entrenar_patrones.py al
entrenar (ROC-AUC, F1, etc.) -- solo prueba que la integración (carga del
.joblib + predict_proba con el vector de columnas correcto) no está rota.

Se salta automáticamente si datos/modelos_patrones_v9.joblib no existe: el
archivo pesa ~1.2GB y no está versionado en git (ver datos/ en .gitignore),
así que un clon nuevo del repo no lo tiene hasta que alguien lo entrena o lo
copia a mano."""
import pytest

from app import modelo

pytestmark = pytest.mark.slow

requiere_modelo = pytest.mark.skipif(
    not modelo.MODELO_PATH.exists(),
    reason=f"no existe {modelo.MODELO_PATH} (archivo grande, no versionado en git)",
)


def test_escalar_lleva_valores_crudos_a_la_escala_de_entrenamiento():
    # Las constantes de lat/lon son las del scaler original (las mismas que
    # usa scripts/cargar_incidentes_csv.py para revertirlo).
    media_lat, escala_lat = modelo.ESCALADO["lat_media"]
    assert media_lat == pytest.approx(-13.555222) and escala_lat == pytest.approx(3.969597)

    crudo = {"lat_media": -6.8, "hours_dia": 22.108263, "pais_inferido_PER": 1.0, "zona_dia_reserva_artesanal_5mn": 1.0}
    escalado = modelo.escalar(crudo)

    assert escalado["lat_media"] == pytest.approx((-6.8 - media_lat) / escala_lat)
    assert escalado["hours_dia"] == pytest.approx(0.0)  # la media cruda -> 0
    # one-hot / flags binarios no se escalaron en prepare_data.py
    assert escalado["pais_inferido_PER"] == 1.0
    assert escalado["zona_dia_reserva_artesanal_5mn"] == 1.0
    # columnas sin dato en vivo -> valor típico de train, ya escalado
    assert escalado["es_transbordo_no_autorizado"] == modelo.VALOR_FIJO_ESCALADO["es_transbordo_no_autorizado"]
    # no modifica el diccionario de entrada
    assert crudo["lat_media"] == -6.8


def test_dist_costa_escalada_cae_en_los_bordes_de_las_zonas_del_csv():
    # En train.csv el corte de zona_dia_reserva_artesanal_5mn está en
    # dist_costa estandarizada ~= -1.1085 y el de fuera_zee (200mn) en ~0.1475.
    assert modelo.escalar({"dist_costa_min_nm": 5.0})["dist_costa_min_nm"] == pytest.approx(-1.1085, abs=1e-3)
    assert modelo.escalar({"dist_costa_min_nm": 200.0})["dist_costa_min_nm"] == pytest.approx(0.1475, abs=1e-3)


@requiere_modelo
def test_carga_los_tres_detectores_conectados():
    modelos = modelo._cargar()
    assert set(modelos.keys()) == set(modelo.DETECTORES_CONECTADOS)
    for nombre, info in modelos.items():
        assert "model" in info and "features" in info and "threshold" in info
        assert len(info["features"]) > 0
        assert 0.0 <= info["threshold"] <= 1.0


@requiere_modelo
def test_transbordo_no_esta_conectado():
    modelos = modelo._cargar()
    assert "transbordo" not in modelos


@requiere_modelo
@pytest.mark.parametrize("nombre_detector", ["zona_protegida", "apagon_ais", "demora_puerto"])
def test_predecir_devuelve_probabilidad_valida(nombre_detector):
    # Vector vacío: predecir() debe rellenar con 0.0 las columnas faltantes
    # (mismo criterio de imputación que usa el propio entrenamiento).
    resultado = modelo.predecir(nombre_detector, {})

    assert set(resultado.keys()) == {"probabilidad", "detectado"}
    assert isinstance(resultado["probabilidad"], float)
    assert 0.0 <= resultado["probabilidad"] <= 1.0
    assert isinstance(resultado["detectado"], bool)


@requiere_modelo
def test_predecir_detector_no_conectado_falla_explicitamente():
    with pytest.raises(KeyError):
        modelo.predecir("transbordo", {})
