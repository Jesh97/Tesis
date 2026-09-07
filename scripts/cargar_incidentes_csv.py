"""
Carga a Postgres los incidentes CONFIRMADOS (incidente_confirmado==1) que
ya vienen en datos/train.csv y datos/test.csv -- son parte del dataset base
del proyecto de tesis (13 años de historial), no algo que este sistema
detecte en vivo.

Para cada (mmsi, nombre_confirmado) único se toma la fila más antigua como
fecha/posición representativa del incidente, se hace upsert de la
embarcación (por mmsi) y se inserta una fila en "incidentes".

NOTA IMPORTANTE sobre las coordenadas: lat_media/lon_media en el CSV NO son
grados reales -- prepare_data.py (E:\\Preparación de datos) las estandarizó
con sklearn.StandardScaler antes de guardar train/test.csv. Aquí se
revierte esa transformación con la media/desviación EXACTAS del
scaler.joblib que generó este mismo train.csv (E:\\Preparación de
datos\\data_prepared\\scaler.joblib), hardcodeadas abajo para que este
script no dependa de una ruta fuera del repo. Si algún día se regenera
modelo.csv con otro scaler, estas constantes quedan obsoletas.

Clasificación de tipo de infracción: el catálogo de tipos_infraccion no
tiene una categoría para "muerte de tripulante" ni "evade controles" (son
2 de los 28 casos) -- se archivan como 'Falta de Permiso' por ser el cajón
menos incorrecto del catálogo actual; el texto real del incidente queda
íntegro en la descripción.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / "server" / ".env"
load_dotenv(ENV_FILE)

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"

# scaler.joblib fit en train.csv (mean_/scale_ de las columnas lat_media/lon_media)
LAT_MEAN, LAT_SCALE = -13.555221697855293, 3.969597366109545
LON_MEAN, LON_SCALE = -79.72767519685125, 2.9315197981910597

TIPO_INFRACCION_CATALOGO = [
    ("Pesca en Zona Prohibida", "red", "alto"),
    ("Falta de Permiso", "dark", "medio"),
    ("Transbordo Ilegal", "amber", "alto"),
    ("Contaminación", "gray", "medio"),
    ("Pérdida de Señal AIS", "amber", "medio"),
    ("Velocidad Inusual", "gray", "bajo"),
    ("Encuentro Sospechoso en Alta Mar", "red", "alto"),
    ("Incursión en Zona Económica Exclusiva", "red", "alto"),
    ("Visita a Puerto no Autorizado", "dark", "medio"),
]


def clasificar(texto: str) -> tuple[str, str]:
    """(tipo_infraccion, gravedad) a partir del texto libre del incidente."""
    t = texto.lower()
    if "zee" in t or "200m" in t or "200 mill" in t:
        tipo = "Incursión en Zona Económica Exclusiva"
    elif "puerto" in t:
        tipo = "Visita a Puerto no Autorizado"
    else:
        tipo = "Falta de Permiso"
    gravedad = "medio" if "multa" in t else "alto"
    return tipo, gravedad


def cargar_incidentes_confirmados() -> pd.DataFrame:
    cols = [
        "mmsi", "date", "nombre_confirmado", "lugar_texto_incidente_candidato",
        "incidente_confirmado", "lat_media", "lon_media",
    ]
    train = pd.read_csv(DATOS_DIR / "train.csv", usecols=cols, low_memory=False)
    test = pd.read_csv(DATOS_DIR / "test.csv", usecols=cols, low_memory=False)
    todo = pd.concat([train, test], ignore_index=True)
    confirmados = todo[todo["incidente_confirmado"] == 1].copy()
    confirmados["date"] = pd.to_datetime(confirmados["date"])
    confirmados = confirmados.sort_values("date")
    # una fila por incidente: la más antigua de cada (mmsi, nombre_confirmado)
    unicos = confirmados.groupby(["mmsi", "nombre_confirmado"], as_index=False).first()
    unicos["lat"] = unicos["lat_media"] * LAT_SCALE + LAT_MEAN
    unicos["lon"] = unicos["lon_media"] * LON_SCALE + LON_MEAN
    return unicos


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit(f"Falta DATABASE_URL en {ENV_FILE}")

    incidentes = cargar_incidentes_confirmados()
    print(f"Incidentes confirmados únicos en el CSV: {len(incidentes)}")

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                # catálogo de tipos de infracción (idempotente)
                for nombre, color, gravedad in TIPO_INFRACCION_CATALOGO:
                    cur.execute(
                        """INSERT INTO tipos_infraccion (nombre, color_indicador, gravedad_sugerida)
                           VALUES (%s, %s, %s) ON CONFLICT (nombre) DO NOTHING""",
                        (nombre, color, gravedad),
                    )

                insertados = 0
                for _, fila in incidentes.iterrows():
                    mmsi = str(int(fila["mmsi"]))
                    tipo, gravedad = clasificar(fila["lugar_texto_incidente_candidato"] or "")

                    cur.execute(
                        """
                        INSERT INTO embarcaciones (nombre, mmsi, bandera, tipo)
                        VALUES (%s, %s, 'CHN', 'pesca_industrial')
                        ON CONFLICT (mmsi) DO UPDATE SET nombre = EXCLUDED.nombre
                        RETURNING id
                        """,
                        (fila["nombre_confirmado"], mmsi),
                    )
                    embarcacion_id = cur.fetchone()[0]

                    cur.execute("SELECT id FROM tipos_infraccion WHERE nombre = %s", (tipo,))
                    tipo_infraccion_id = cur.fetchone()[0]

                    # evita duplicar si el script se corre más de una vez
                    cur.execute(
                        "SELECT 1 FROM incidentes WHERE embarcacion_id = %s AND fecha_deteccion = %s",
                        (embarcacion_id, fila["date"]),
                    )
                    if cur.fetchone():
                        continue

                    cur.execute(
                        """
                        INSERT INTO incidentes
                            (embarcacion_id, tipo_infraccion_id, descripcion, gravedad, estado,
                             fecha_deteccion, latitud, longitud)
                        VALUES (%s, %s, %s, %s, 'confirmado', %s, %s, %s)
                        """,
                        (
                            embarcacion_id, tipo_infraccion_id,
                            fila["lugar_texto_incidente_candidato"],
                            gravedad, fila["date"], fila["lat"], fila["lon"],
                        ),
                    )
                    insertados += 1

        print(f"Insertados {insertados} incidentes nuevos en Postgres.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
