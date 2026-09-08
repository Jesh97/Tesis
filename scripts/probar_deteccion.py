"""
Prueba offline de los 3 detectores conectados (zona_protegida, apagon_ais,
demora_puerto) SIN llamar a la API de GFW: lee scripts/datos_prueba_gfw.json
(con la misma forma que devuelven gfw_client.obtener_presencia_diaria /
obtener_esfuerzo_diario) y lo corre por el mismo camino que server/app/gfw.py
usa en vivo (features.construir_features_flota + modelo.predecir).

Uso: python scripts/probar_deteccion.py [ruta_al_json]

El JSON de ejemplo trae 4 embarcaciones "de prueba" (más vecinos/flota de
referencia en algunos escenarios, para que los z-score de la flota tengan
varianza real) pensadas para poner a prueba cada detector:

  - 412000001 "PATRIMONIO DEL MAR": control, comportamiento normal (cerca de
    puerto, sin huecos) -- referencia para comparar contra los otros 3.
  - 412000002 "DRAGON DEL PACIFICO": transmite 10 días con pesca normal,
    desaparece 22 días y reaparece a 10km con el patrón de pesca roto --
    SÍ cruza el umbral de "apagon_ais" (prob. ~0.73 > umbral ~0.72).
  - 412000003 "LONG SPRING 88": 90 días seguidos a más de 500nm de cualquier
    puerto/costa peruana (se acerca al umbral de "demora_puerto" sin cruzarlo).
  - 412000004 "CALETA NORTE": posicionada sobre la reserva artesanal de 5mn
    (frente a Chimbote) durante 5 días (se acerca al umbral de
    "zona_protegida" sin cruzarlo).

IMPORTANTE: el modelo se entrenó con 13 años de datos históricos de SISESAT
(ver docstring de app/features.py); un escenario sintético puede acercarse
mucho al umbral de un detector sin llegar a cruzarlo -- eso no es un bug de
este script, es la misma limitación de distribución que ya documenta
features.py para los datos reconstruidos en vivo. "DRAGON DEL PACIFICO" se
ajustó (por búsqueda) hasta cruzar el umbral de "apagon_ais" para demostrar
una alerta real de punta a punta; los otros dos quedan como ejemplo de
señal elevada pero no positiva, que también es un resultado válido del
modelo.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app import features, modelo  # noqa: E402

DATOS_PRUEBA_PATH = Path(__file__).resolve().parent / "datos_prueba_gfw.json"
DETECTORES = ("zona_protegida", "apagon_ais", "demora_puerto")


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else DATOS_PRUEBA_PATH
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)

    por_mmsi = features.construir_features_flota(datos["presencia"], datos["esfuerzo"])
    if not por_mmsi:
        print("Ningun mmsi junto suficientes dias de presencia (MIN_DIAS_PRESENCIA "
              f"= {features.MIN_DIAS_PRESENCIA}) -- revisa el JSON de entrada.")
        return

    umbrales = {d: modelo.umbral(d) for d in DETECTORES}

    print(f"{'mmsi':<14}{'nombre':<24}{'detector':<16}{'prob':>8}{'umbral':>9}  detectado")
    print("-" * 80)
    for mmsi, info in por_mmsi.items():
        for nombre_detector in DETECTORES:
            resultado = modelo.predecir(nombre_detector, info["features"])
            marca = "SI" if resultado["detectado"] else "no"
            print(
                f"{mmsi:<14}{info['nombre']:<24}{nombre_detector:<16}"
                f"{resultado['probabilidad']:>8.3f}{umbrales[nombre_detector]:>9.3f}  {marca}"
            )
        print()


if __name__ == "__main__":
    main()
