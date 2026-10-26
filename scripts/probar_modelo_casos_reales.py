"""
Prueba si el modelo entrenado (datos/modelos_patrones_v9.joblib) detecta las
irregularidades para las que se entrenó, usando CASOS REALES del conjunto de
test (datos/test.csv, separado por tiempo de train.csv) guardados en un JSON.

A diferencia de probar_deteccion.py (escenarios sintéticos armados a mano y
pasados por features.construir_features_flota), aquí cada caso es una fila
real con su etiqueta calculada con la MISMA regla que usó
entrenar_patrones.py:

  - zona_protegida: zona_dia_reserva_artesanal_5mn == 1
  - apagon_ais:     gap_log > percentil 95 de train
  - demora_puerto:  dias_activos_acumulados > percentil 95 de train

Las features van tal cual están en el CSV (ya estandarizadas por
prepare_data.py), que es la escala con la que se entrenó el modelo.

Uso:
  python scripts/probar_modelo_casos_reales.py              # genera el JSON si no existe y lo evalúa
  python scripts/probar_modelo_casos_reales.py --regenerar  # vuelve a muestrear casos de test.csv
  python scripts/probar_modelo_casos_reales.py otra_ruta.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app import modelo  # noqa: E402

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
CASOS_PATH = Path(__file__).resolve().parent / "casos_prueba_modelo.json"
CASOS_POR_CLASE = 25
RANDOM_STATE = 42

# Columnas de identificación / etiquetas que no son features del modelo.
NO_FEATURES = {
    "mmsi", "date", "puerto_mas_cercano_original", "nombre_incidente_candidato",
    "lugar_texto_incidente_candidato", "nombre_confirmado", "incidente_candidato",
    "dias_al_incidente_candidato", "incidente_confirmado",
}


def generar_casos(destino: Path) -> None:
    import pandas as pd

    print("Leyendo datos/train.csv (para los percentiles 95) y datos/test.csv...")
    train = pd.read_csv(DATOS_DIR / "train.csv", low_memory=False, usecols=["gap_log", "dias_activos_acumulados"])
    test = pd.read_csv(DATOS_DIR / "test.csv", low_memory=False)

    reglas = {
        "zona_protegida": ("zona_dia_reserva_artesanal_5mn", None),
        "apagon_ais": ("gap_log", float(train["gap_log"].quantile(0.95))),
        "demora_puerto": ("dias_activos_acumulados", float(train["dias_activos_acumulados"].quantile(0.95))),
    }

    columnas_features = [c for c in test.columns if c not in NO_FEATURES]
    casos = []
    for detector, (columna, umbral_p95) in reglas.items():
        etiqueta = (test[columna] > umbral_p95) if umbral_p95 is not None else (test[columna] == 1)
        for esperado, subconjunto in ((True, test[etiqueta]), (False, test[~etiqueta])):
            muestra = subconjunto.sample(n=CASOS_POR_CLASE, random_state=RANDOM_STATE)
            for _, fila in muestra.iterrows():
                casos.append({
                    "detector": detector,
                    "esperado": esperado,
                    "mmsi": str(fila["mmsi"]),
                    "date": fila["date"],
                    "features": {c: float(fila[c]) for c in columnas_features if pd.notna(fila[c])},
                })

    destino.write_text(json.dumps({
        "origen": "datos/test.csv",
        "regla_etiqueta": {d: {"columna": c, "umbral_p95_train": u} for d, (c, u) in reglas.items()},
        "casos": casos,
    }, indent=1), encoding="utf-8")
    print(f"Guardados {len(casos)} casos en {destino}")


def evaluar(ruta: Path) -> None:
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    print(f"\n{'detector':<16}{'positivos detectados':>22}{'negativos sin alerta':>22}{'prob. media +/-':>18}")
    print("-" * 78)
    for detector in modelo.DETECTORES_CONECTADOS:
        casos = [c for c in datos["casos"] if c["detector"] == detector]
        if not casos:
            continue
        resultados = [(c, modelo.predecir(detector, c["features"], ya_escaladas=True)) for c in casos]
        positivos = [r for c, r in resultados if c["esperado"]]
        negativos = [r for c, r in resultados if not c["esperado"]]
        tp = sum(r["detectado"] for r in positivos)
        tn = sum(not r["detectado"] for r in negativos)
        prob_pos = sum(r["probabilidad"] for r in positivos) / max(len(positivos), 1)
        prob_neg = sum(r["probabilidad"] for r in negativos) / max(len(negativos), 1)
        print(
            f"{detector:<16}{f'{tp}/{len(positivos)}':>22}{f'{tn}/{len(negativos)}':>22}"
            f"{f'{prob_pos:.2f} / {prob_neg:.2f}':>18}"
        )

        fallos = [(c, r) for c, r in resultados if r["detectado"] != c["esperado"]]
        for c, r in fallos:
            tipo = "no detectado" if c["esperado"] else "falsa alarma"
            print(f"    {tipo:<13} mmsi {c['mmsi']} {c['date']}  prob {r['probabilidad']:.3f} (umbral {modelo.umbral(detector):.3f})")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ruta = Path(args[0]) if args else CASOS_PATH
    if "--regenerar" in sys.argv or not ruta.exists():
        generar_casos(ruta)
    evaluar(ruta)


if __name__ == "__main__":
    main()
