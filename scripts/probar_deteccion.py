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
    puerto, sin huecos). Al estar pegado a Bayóvar también roza el umbral
    de "zona_protegida" (~0.57).
  - 412000002 "DRAGON DEL PACIFICO": transmite 10 días con pesca normal,
    desaparece 22 días y reaparece a 10km con el patrón de pesca roto --
    cruza el umbral de "apagon_ais" (prob. ~0.86 > umbral ~0.70).
  - 412000003 "LONG SPRING 88": 90 días seguidos a más de 500nm de cualquier
    puerto/costa peruana. NO cruza "demora_puerto": el modelo aprendió
    dias_activos_acumulados contando desde 2012, y aquí solo hay 90 días.
  - 412000004 "CALETA NORTE": posicionada sobre la reserva artesanal de 5mn
    (frente a Chimbote) durante 5 días -- cruza "zona_protegida" (~0.76).

Hasta que modelo.predecir aplicó el escalado de entrenamiento (ver
modelo.ESCALADO), ninguno de estos escenarios -- ni ningún caso real --
cruzaba los umbrales en vivo.

Para una prueba con casos reales etiquetados ver
scripts/probar_modelo_casos_reales.py, y para validar el camino en vivo
contra el dataset de entrenamiento, scripts/validar_escalado.py.
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
