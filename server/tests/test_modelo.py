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
