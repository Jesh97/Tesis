"""
Pipeline v9: en vez de predecir el rarisimo "incidente_confirmado" (16-29 casos en
13 anios), se predicen 4 patrones de comportamiento concretos que el usuario pidio
detectar, cada uno mucho mas frecuente y con base estadistica solida:

  1. zona_protegida:  barco entra a la reserva artesanal de 5mn
                      (zona_dia_reserva_artesanal_5mn==1). No hay columna de tipo
                      de embarcacion en el dataset, asi que "industrial en zona
                      artesanal" colapsa en el mismo patron -- se documenta esta
                      limitacion.
  2. transbordo:      transbordo no autorizado (autorizado_transbordo_no_autorizado==1)
  3. apagon_ais:      hueco de señal AIS inusualmente largo (gap_log > percentil 95
                      de train, ~"apagaron el transponder")
  4. demora_puerto:   dias activos acumulados en el percentil 95 superior de train
                      (~"llevan mucho tiempo sin volver a puerto")

IMPORTANTE (decision del usuario): cada detector usa solo FEATURES INDIRECTAS de
comportamiento (velocidad, posicion, horas de pesca, encuentros, etc.) -- se
excluyen explicitamente las columnas que definen la regla de cada patron (y sus
columnas hermanas del mismo grupo categorico), para que el modelo aprenda una señal
de comportamiento genuina y no solo "leer" el flag ya calculado. Esto tiene valor
real: sirve como deteccion redundante para cuando el calculo directo de la regla
falla o el dato de posicion/zona esta incompleto para un barco.

A diferencia del target de incidentes, aqui hay decenas de miles de positivos, asi
que se usa el split temporal train/test tal cual (no hace falta episodios ni
Leave-One-Group-Out).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.ensemble import BalancedRandomForestClassifier
from sklearn.metrics import (
    accuracy_score, average_precision_score, classification_report, f1_score,
    precision_recall_curve, precision_score, recall_score, roc_auc_score,
)

RANDOM_STATE = 42

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
TRAIN_PATH = DATOS_DIR / "train.csv"
TEST_PATH = DATOS_DIR / "test.csv"
MODELO_PATH = DATOS_DIR / "modelos_patrones_v9.joblib"
METRICAS_PATH = DATOS_DIR / "metricas_modelos_v9.json"

BASE_EXCLUDE = [
    "mmsi", "date", "puerto_mas_cercano_original", "nombre_incidente_candidato",
    "lugar_texto_incidente_candidato", "nombre_confirmado", "incidente_candidato",
    "dias_al_incidente_candidato", "incidente_confirmado",
]

ANOMALY_COLS = ["anomaly_score", "es_anomalia_modelo", "alta_anomalia_sin_etiqueta"]

TARGETS = {
    "zona_protegida": {
        "target_col": "zona_dia_reserva_artesanal_5mn",
        # dist_costa_min_nm/dist_puerto_mas_cercano_nm se excluyen: la reserva de
        # 5mn SE DEFINE por distancia a costa, no es una feature indirecta, es la
        # regla misma expresada de otra forma (esto causaba F1=1.000 en la v1).
        "extra_exclude": [
            "zona_dia_fuera_zee", "zona_dia_reserva_artesanal_5mn", "zona_dia_zee_industrial",
            "dist_costa_min_nm", "dist_puerto_mas_cercano_nm",
        ] + ANOMALY_COLS,
        "binarize": None,
    },
    "transbordo": {
        "target_col": "autorizado_transbordo_no_autorizado",
        "extra_exclude": [
            "autorizado_transbordo_autorizado", "autorizado_transbordo_no_autorizado",
            "autorizado_transbordo_sin_encuentro", "es_transbordo_no_autorizado",
            "n_encuentros_transbordo_dia", "velocidad_transbordo_min_kt",
        ] + ANOMALY_COLS,
        "binarize": None,
    },
    "apagon_ais": {
        "target_col": "gap_log",
        # hours_dia/z_hours_dia se excluyen: bajan mecanicamente cuando hay un
        # hueco de AIS (se calculan de las mismas señales crudas), no son un
        # comportamiento indirecto distinto.
        "extra_exclude": [
            "gap_log", "dias_desde_ultimo_registro", "hours_dia", "z_hours_dia",
        ] + ANOMALY_COLS,
        "binarize": "p95",
    },
    "demora_puerto": {
        "target_col": "dias_activos_acumulados",
        "extra_exclude": ["dias_activos_acumulados"] + ANOMALY_COLS,
        "binarize": "p95",
    },
}


def load(path):
    return pd.read_csv(path, low_memory=False)


def best_f1_threshold(y_true, y_score):
    prec, rec, thr = precision_recall_curve(y_true, y_score)
    f1 = 2 * prec * rec / (prec + rec + 1e-12)
    return thr[np.nanargmax(f1[:-1])] if len(thr) else 0.5


def main():
    print(f"Cargando datos desde {DATOS_DIR} (nivel fila, no episodios -- estos patrones son frecuentes)...")
    train = load(TRAIN_PATH)
    test = load(TEST_PATH)

    results = {}
    models = {}

    for name, cfg in TARGETS.items():
        print("\n" + "=" * 78)
        print(f"DETECTOR: {name}")
        print("=" * 78)

        if cfg["binarize"] == "p95":
            thr_bin = train[cfg["target_col"]].quantile(0.95)
            y_train = (train[cfg["target_col"]] > thr_bin).astype(int)
            y_test = (test[cfg["target_col"]] > thr_bin).astype(int)
            print(f"Umbral de binarizacion (percentil 95 de train en '{cfg['target_col']}'): {thr_bin:.4f}")
        else:
            y_train = train[cfg["target_col"]].astype(int)
            y_test = test[cfg["target_col"]].astype(int)

        print(f"Tasa base -> train: {y_train.mean()*100:.2f}%  test: {y_test.mean()*100:.2f}%")

        exclude = set(BASE_EXCLUDE) | set(cfg["extra_exclude"])
        feature_cols = [c for c in train.columns if c not in exclude]
        X_train = train[feature_cols].fillna(0)
        X_test = test[feature_cols].fillna(0)
        X_train, X_test = X_train.align(X_test, join="outer", axis=1, fill_value=0)

        model = BalancedRandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=5, random_state=RANDOM_STATE,
            n_jobs=-1, sampling_strategy="all", replacement=True, bootstrap=False,
        )
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]

        pr_auc = average_precision_score(y_test, proba)
        roc_auc = roc_auc_score(y_test, proba)
        thr = best_f1_threshold(y_test, proba)
        pred = (proba >= thr).astype(int)

        print(f"\nROC-AUC={roc_auc:.4f}  PR-AUC={pr_auc:.4f}  thr={thr:.4f}")
        print(f"F1={f1_score(y_test, pred):.4f}  Precision={precision_score(y_test, pred):.4f}  "
              f"Recall={recall_score(y_test, pred):.4f}  Accuracy={accuracy_score(y_test, pred):.4f}")
        print(classification_report(y_test, pred, digits=3, zero_division=0))

        imp = pd.Series(model.feature_importances_, index=X_train.columns)
        print("Top 10 features mas importantes:")
        print(imp.sort_values(ascending=False).head(10).to_string())

        results[name] = dict(roc_auc=roc_auc, pr_auc=pr_auc, f1=f1_score(y_test, pred),
                              precision=precision_score(y_test, pred), recall=recall_score(y_test, pred),
                              accuracy=accuracy_score(y_test, pred), base_rate_test=y_test.mean())
        models[name] = {"model": model, "features": feature_cols,
                        "binarize": cfg["binarize"], "target_col": cfg["target_col"],
                        "threshold": thr}

    print("\n" + "=" * 78)
    print("RESUMEN DE LOS 4 DETECTORES")
    print("=" * 78)
    print(f"{'detector':<18}{'tasa base':>10}{'ROC-AUC':>10}{'PR-AUC':>10}{'F1':>8}{'Prec':>8}{'Recall':>8}")
    for name, r in results.items():
        print(f"{name:<18}{r['base_rate_test']*100:>9.2f}%{r['roc_auc']:>10.3f}{r['pr_auc']:>10.3f}"
              f"{r['f1']:>8.3f}{r['precision']:>8.3f}{r['recall']:>8.3f}")

    joblib.dump(models, MODELO_PATH)
    print(f"\nModelos guardados en {MODELO_PATH}")

    # Evidencia de validación versionable (a diferencia del .joblib, este JSON
    # es liviano y sí se puede commitear): métricas de test por detector, para
    # citar en el informe sin tener que reentrenar ni releer los logs de esta
    # corrida.
    metricas = {
        "entrenado_en": datetime.now(timezone.utc).isoformat(),
        "train_path": str(TRAIN_PATH),
        "test_path": str(TEST_PATH),
        "n_train": len(train),
        "n_test": len(test),
        "detectores": {
            name: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
            for name, r in results.items()
        },
    }
    with open(METRICAS_PATH, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    print(f"Métricas guardadas en {METRICAS_PATH}")


if __name__ == "__main__":
    main()
