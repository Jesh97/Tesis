"""
Valida de punta a punta el camino EN VIVO del modelo (features.py +
modelo.escalar) contra el dataset de entrenamiento:

1. Toma días del conjunto de test (datos/test.csv, ya estandarizado).
2. Para cada día D arma registros con la misma forma que devuelve GFW a
   partir de los datos crudos (mmsi_unido.csv, ventana de VENTANA_DIAS días
   hasta D) y los pasa por features.construir_features_flota, igual que
   server/app/gfw.py.
3. Compara, por (mmsi, D): cada feature escalada contra la del CSV, y si
   cada detector da la misma decisión con las features en vivo que con la
   fila real -- con el escalado (camino actual) y sin él (camino anterior).

Uso: python scripts/validar_escalado.py [ruta mmsi_unido.csv]
"""
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app import features, modelo  # noqa: E402

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
MMSI_UNIDO = Path(r"D:\datos\Codigo\datos_unidos\mmsi_unido.csv")
VENTANA_DIAS = 90
N_DIAS = 8
PAISES = features.PAISES_ONEHOT


def bandera(fila) -> str | None:
    for pais in PAISES:
        if fila.get(f"pais_inferido_{pais}") == 1:
            return pais
    return None


def main():
    ruta_crudo = Path(sys.argv[1]) if len(sys.argv) > 1 else MMSI_UNIDO
    print("Leyendo datos/test.csv y datos crudos...")
    test = pd.read_csv(DATOS_DIR / "test.csv", low_memory=False)
    test["date"] = test["date"].astype(str)
    crudo = pd.read_csv(ruta_crudo)
    crudo["date"] = crudo["date"].astype(str)
    crudo = crudo[crudo["mmsi"].isin(test["mmsi"].unique())]

    banderas = {str(f["mmsi"]): bandera(f) for f in test.drop_duplicates("mmsi").to_dict("records")}
    fechas = sorted(test["date"].unique())
    dias = [fechas[i] for i in np.linspace(VENTANA_DIAS, len(fechas) - 1, N_DIAS).astype(int)]

    pares = []  # (fila real del CSV, features crudas en vivo)
    for dia in dias:
        desde = (pd.Timestamp(dia) - timedelta(days=VENTANA_DIAS - 1)).strftime("%Y-%m-%d")
        ventana = crudo[(crudo["date"] >= desde) & (crudo["date"] <= dia)]
        presencia, esfuerzo = [], []
        for r in ventana.itertuples(index=False):
            base = {"mmsi": str(r.mmsi), "date": r.date, "shipName": None, "flag": banderas.get(str(r.mmsi)),
                    "vesselType": "FISHING", "lat": r.cell_ll_lat, "lon": r.cell_ll_lon}
            presencia.append({**base, "hours": r.hours})
            if r.fishing_hours > 0:
                esfuerzo.append({**base, "hours": r.fishing_hours})
        por_mmsi = features.construir_features_flota(presencia, esfuerzo)
        reales = test[test["date"] == dia].set_index(test[test["date"] == dia]["mmsi"].astype(str))
        for mmsi, info in por_mmsi.items():
            if mmsi in reales.index and ventana[(ventana["mmsi"].astype(str) == mmsi)]["date"].max() == dia:
                pares.append((reales.loc[mmsi], info["features"]))
        print(f"  {dia}: {len(por_mmsi)} barcos con features, acumulados {len(pares)} pares")

    print(f"\nFeatures escaladas en vivo vs CSV ({len(pares)} pares, correlación y error absoluto mediano):")
    for columna in modelo.ESCALADO:
        en_vivo = np.array([modelo.escalar(f)[columna] for _, f in pares])
        real = np.array([float(r[columna]) for r, _ in pares])
        corr = np.corrcoef(en_vivo, real)[0, 1] if en_vivo.std() > 0 and real.std() > 0 else float("nan")
        print(f"  {columna:<34} corr={corr:6.3f}  err_mediano={np.median(np.abs(en_vivo - real)):.3f}")

    print("\nMisma decisión que con la fila real del CSV:")
    for detector in modelo.DETECTORES_CONECTADOS:
        real = [modelo.predecir(detector, r.to_dict(), ya_escaladas=True)["detectado"] for r, _ in pares]
        con_escalado = [modelo.predecir(detector, f)["detectado"] for _, f in pares]
        sin_escalado = [modelo.predecir(detector, f, ya_escaladas=True)["detectado"] for _, f in pares]
        positivos = sum(real)
        print(f"  {detector:<16} con escalado {np.mean(np.equal(real, con_escalado)):6.1%}   "
              f"sin escalado (antes) {np.mean(np.equal(real, sin_escalado)):6.1%}   "
              f"[positivos reales {positivos}: detectados con escalado "
              f"{sum(a and b for a, b in zip(real, con_escalado))}, antes {sum(a and b for a, b in zip(real, sin_escalado))}]")


if __name__ == "__main__":
    main()
