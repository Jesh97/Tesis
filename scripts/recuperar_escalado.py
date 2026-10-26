"""
Recupera (media, escala) del StandardScaler con el que prepare_data.py
estandarizó datos/train.csv, cuyo scaler.joblib original se perdió. Imprime
las constantes que van en ESCALADO / VALOR_FIJO_ESCALADO de
server/app/modelo.py.

Idea: train.csv guarda std = (crudo - media) / escala, así que
crudo = std * escala + media. Si se recalcula el valor crudo de una columna
para las mismas (mmsi, date) desde los datos crudos de GFW de los que salió
el dataset (mmsi_unido.csv), una regresión lineal crudo ~ std da escala
(pendiente) y media (intercepto); R² = 1 confirma que la definición
recalculada es exactamente la original.

Para lo que no se puede recalcular exacto:
  - dist_costa_min_nm: los flags zona_dia_reserva_artesanal_5mn y
    zona_dia_fuera_zee del mismo CSV marcan dónde el crudo vale 5 y 200 mn
    (dos puntos -> recta exacta).
  - conteos enteros (vecinos, cluster): el paso entre valores distintos del
    CSV es 1/escala; la media sale del mínimo crudo (0, o 1 en cluster, que
    se cuenta a sí mismo).
  - dist_puerto_mas_cercano_nm: correlación 0.9996 con dist_costa; se
    ajusta contra dist_costa ya recuperada (aproximada).
  - disp_celdas_km: pendiente de la regresión (R² 0.96) con mínimo crudo 0.
  - columnas sin dato en vivo: valor más común en train (ya estandarizado).

Uso: python scripts/recuperar_escalado.py [ruta mmsi_unido.csv]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
MMSI_UNIDO = Path(r"D:\datos\Codigo\datos_unidos\mmsi_unido.csv")
R_NM = 3440.065

SIN_DATO_EN_VIVO = ["flota_fishing_hours_max_celda", "n_encuentros_transbordo_dia",
                    "velocidad_transbordo_min_kt", "es_transbordo_no_autorizado"]


def hav_nm(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return R_NM * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def ajustar(estandarizado, crudo) -> tuple[float, float, float]:
    ok = np.isfinite(estandarizado) & np.isfinite(crudo)
    escala, media = np.polyfit(estandarizado[ok], crudo[ok], 1)
    r2 = np.corrcoef(estandarizado[ok], crudo[ok])[0, 1] ** 2
    return float(media), float(escala), float(r2)


def recalcular_crudo(ruta: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Features crudas por (mmsi, date), con las definiciones verificadas."""
    m = pd.read_csv(ruta)
    m["date"] = m["date"].astype(str)
    g = m.groupby(["mmsi", "date"]).agg(
        hours_dia=("hours", "sum"),
        fishing_hours_dia=("fishing_hours", "sum"),
        n_celdas_dia=("hours", "size"),
        lat_media=("cell_ll_lat", "mean"),
        lon_media=("cell_ll_lon", "mean"),
    ).reset_index().sort_values(["mmsi", "date"])
    g["fishing_ratio_dia"] = np.where(g.hours_dia > 0, g.fishing_hours_dia / g.hours_dia, 0)
    g["dias_desde_ultimo_registro"] = g.groupby("mmsi")["date"].transform(lambda s: pd.to_datetime(s).diff().dt.days).fillna(0)
    g["dias_activos_acumulados"] = g.groupby("mmsi").cumcount() + 1
    g["gap_log"] = np.log1p(g["dias_desde_ultimo_registro"])

    prev_lat = g.groupby("mmsi")["lat_media"].shift()
    prev_lon = g.groupby("mmsi")["lon_media"].shift()
    g["desplazamiento_km"] = (hav_nm(prev_lat, prev_lon, g.lat_media, g.lon_media) * 1.852).fillna(0)
    g["velocidad_implicita_kt"] = (g.desplazamiento_km / 1.852) / np.maximum(g.dias_desde_ultimo_registro * 24, 1)

    # z-score contra el historial completo del propio barco, ddof=1
    for c in ["hours_dia", "fishing_hours_dia", "n_celdas_dia"]:
        grp = g.groupby("mmsi")[c]
        g["z_" + c] = (g[c] - grp.transform("mean")) / grp.transform("std")

    mm = m.merge(g[["mmsi", "date", "lat_media", "lon_media"]], on=["mmsi", "date"])
    mm["dist_km"] = hav_nm(mm.lat_media, mm.lon_media, mm.cell_ll_lat, mm.cell_ll_lon) * 1.852
    disp = mm.groupby(["mmsi", "date"])["dist_km"].std(ddof=0).rename("disp_celdas_km").reset_index()
    g = g.merge(disp, on=["mmsi", "date"], how="left")
    g["disp_celdas_km"] = g["disp_celdas_km"].fillna(0)
    return g


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else MMSI_UNIDO
    print("Leyendo datos/train.csv y", ruta)
    t = pd.read_csv(DATOS_DIR / "train.csv", low_memory=False)
    t["date"] = t["date"].astype(str)
    j = t.merge(recalcular_crudo(ruta), on=["mmsi", "date"], suffixes=("", "_crudo"))
    print(f"filas train: {len(t)}, cruzadas con crudo: {len(j)}\n")

    escalado: dict[str, tuple[float, float, str]] = {}
    for c in ["hours_dia", "fishing_hours_dia", "fishing_ratio_dia", "n_celdas_dia", "lat_media", "lon_media",
              "dias_desde_ultimo_registro", "dias_activos_acumulados", "gap_log", "desplazamiento_km",
              "velocidad_implicita_kt", "z_hours_dia", "z_fishing_hours_dia", "z_n_celdas_dia"]:
        media, escala, r2 = ajustar(j[c].values, j[c + "_crudo"].values)
        escalado[c] = (media, escala, f"regresión R²={r2:.6f}")

    d = t["dist_costa_min_nm"]
    reserva, fuera = t["zona_dia_reserva_artesanal_5mn"] == 1, t["zona_dia_fuera_zee"] == 1
    s5 = (d[reserva].max() + d[~reserva & (d > d[reserva].max())].min()) / 2
    s200 = (d[~fuera & (d < d[fuera].min())].max() + d[fuera].min()) / 2
    escala_costa = 195 / (s200 - s5)
    media_costa = 5 - s5 * escala_costa
    escalado["dist_costa_min_nm"] = (media_costa, escala_costa, "anclas 5mn/200mn de los flags de zona")

    for c, minimo in [("n_vecinos_celda_max_dia", 0), ("n_vecinos_pais_distinto_max_dia", 0), ("cluster_tamano_dia", 1)]:
        u = np.unique(t[c].round(9))
        escala = 1 / np.min(np.diff(u))
        escalado[c] = (minimo - u[0] * escala, escala, f"conteo entero, paso 1, mínimo crudo {minimo}")

    costa_crudo = d * escala_costa + media_costa
    escala_p, media_p = np.polyfit(t["dist_puerto_mas_cercano_nm"], costa_crudo, 1)
    escalado["dist_puerto_mas_cercano_nm"] = (media_p, escala_p, "aprox.: ajustada contra dist_costa (corr 0.9996)")

    _, escala_disp, r2 = ajustar(j["disp_celdas_km"].values, j["disp_celdas_km_crudo"].values)
    escalado["disp_celdas_km"] = (-t["disp_celdas_km"].min() * escala_disp, escala_disp, f"aprox.: R²={r2:.3f}, mínimo crudo 0")

    print("ESCALADO = {")
    for c, (media, escala, origen) in escalado.items():
        print(f'    "{c}": ({media:.6f}, {escala:.6f}),  # {origen}')
    print("}\n\nVALOR_FIJO_ESCALADO = {")
    for c in SIN_DATO_EN_VIVO:
        print(f'    "{c}": {t[c].round(6).mode()[0]:.6f},')
    print("}")


if __name__ == "__main__":
    main()
