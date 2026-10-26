"""Decisión final de alertas por embarcación: combina las REGLAS (la
definición legal / operativa del patrón, calculada en features.py) con los
DETECTORES ENTRENADOS (modelo.py). Una alerta salta si dispara cualquiera.

Por qué hacen falta las reglas además del modelo (verificado con
scripts/simular_irregularidades.py y con casos reales de datos/test.csv):

  - zona_protegida: el modelo casi no vio casos de Lambayeque (0.2% de los
    positivos de entrenamiento) y detecta solo ~38% de los casos reales de
    reserva de 5 mn de esta zona (vs ~97% en el resto del litoral). Además
    aprendió el perfil "cerca de la costa sin pescar" (barcos entrando o
    saliendo de puerto), no "pescando dentro de las 5 mn".
  - demora_puerto: la etiqueta con la que se entrenó (dias_activos_acumulados
    > p95) cuenta días con AIS desde 2012, no días sin volver a puerto; sus
    "positivos" son barcos peruanos con mucho historial, cerca de la costa.

islasProtegidas es solo regla: pesca a menos de RADIO_ISLAS_PROTEGIDAS_NM
de las islas Lobos (RNSIIPG). Va aparte de la reserva de 5 mn, que se mide
desde la costa continental.

apagon_ais sí se apoya en el modelo (detecta ~95% de los apagones simulados
y reales); no necesita regla.
"""
from . import modelo

# Días corridos sin tocar puerto ni desembarcadero a partir de los cuales se
# alerta. Un cerquero de anchoveta hace viajes de 1-3 días y un potero
# artesanal de pota de 15-20: 20 días ya está fuera de lo normal para la
# flota que descarga en Lambayeque.
UMBRAL_DIAS_SIN_PUERTO = 20
# Con un solo día pescando dentro de las 5 mn ya hay infracción.
UMBRAL_DIAS_EN_RESERVA = 1


def evaluar_actividad(mmsi: str, datos: dict) -> dict | None:
    """Alertas de una embarcación (salida de features.construir_features_flota),
    con la forma que consume el frontend (useActividadSospechosaAlertas.ts).
    None si no dispara nada."""
    apagon = modelo.predecir("apagon_ais", datos["features"])
    demora = modelo.predecir("demora_puerto", datos["features"])
    zona = modelo.predecir("zona_protegida", datos["features"])

    demora_por_regla = datos["dias_sin_puerto"] >= UMBRAL_DIAS_SIN_PUERTO
    reserva_por_regla = datos["dias_pescando_en_reserva"] >= UMBRAL_DIAS_EN_RESERVA
    demora_detectada = demora["detectado"] or demora_por_regla
    reserva_detectada = reserva_por_regla or zona["detectado"]
    islas_detectada = datos["dias_pescando_cerca_islas"] >= UMBRAL_DIAS_EN_RESERVA

    if not (apagon["detectado"] or demora_detectada or reserva_detectada or islas_detectada):
        return None

    # Combina el apagón de AIS ya detectado por el modelo entrenado con la
    # señal geográfica de features.cruce_frontera_zee_tras_hueco: solo se
    # marca cuando además de irse la señal, la embarcación estaba cerca o
    # fuera del límite de las 200mn ANTES de apagarse y reaparece dentro
    # de la ZEE peruana -- ver el comentario en features.py.
    cruce_frontera = apagon["detectado"] and datos["cruce_frontera_zee_tras_hueco"]

    return {
        "mmsi": mmsi,
        "nombre": datos["nombre"],
        "flag": datos["flag"],
        "lat": datos["lat"],
        "lon": datos["lon"],
        "apagonAis": (
            {"detectado": True, "diasSinSenal": datos["dias_sin_senal"], "probabilidad": apagon["probabilidad"]}
            if apagon["detectado"] else None
        ),
        "demoraPuerto": (
            {
                "detectado": True,
                "diasLejosDePuerto": datos["dias_sin_puerto"],
                # Si no tocó puerto en toda la ventana consultada, el número es
                # un mínimo (lleva al menos esos días).
                "alMenos": datos["sin_puerto_en_ventana"],
                "porRegla": demora_por_regla,
                "probabilidad": demora["probabilidad"],
            }
            if demora_detectada else None
        ),
        "reservaArtesanal": (
            {
                "detectado": True,
                "diasPescando": datos["dias_pescando_en_reserva"],
                "distCostaMinNm": round(datos["dist_min_reserva_nm"], 1) if datos["dist_min_reserva_nm"] is not None else None,
                "porRegla": reserva_por_regla,
                "probabilidad": zona["probabilidad"],
            }
            if reserva_detectada else None
        ),
        # Solo regla: el radio (features.RADIO_ISLAS_PROTEGIDAS_NM) es un
        # parámetro a confirmar con la norma de la RNSIIPG.
        "islasProtegidas": (
            {
                "detectado": True,
                "diasPescando": datos["dias_pescando_cerca_islas"],
                "distIslaMinNm": round(datos["dist_min_islas_nm"], 1),
            }
            if islas_detectada else None
        ),
        "cruceFronteraZee": (
            {
                "detectado": True,
                "distCostaAntesNm": round(datos["dist_costa_anterior_nm"], 1),
                "distCostaAhoraNm": round(datos["dist_costa_actual_nm"], 1),
                "diasSinSenal": datos["dias_sin_senal"],
                "probabilidad": apagon["probabilidad"],
            }
            if cruce_frontera else None
        ),
    }
