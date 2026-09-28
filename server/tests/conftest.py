"""Fixtures compartidas por toda la suite. app.rate_limit lleva un contador
global por proceso (ver server/app/rate_limit.py): sin resetearlo entre
tests, un archivo que haga muchas requests sin token (todas caen en la misma
identidad por IP) podría, a medida que la suite crezca, empezar a chocar con
el límite y devolver 429 en vez del código que el test realmente quiere
probar -- un fallo intermitente y difícil de rastrear."""
import pytest

from app.rate_limit import _contadores


@pytest.fixture(autouse=True)
def _sin_limite_de_solicitudes_entre_tests():
    _contadores.clear()
    yield
    _contadores.clear()
