"""Agregación mes a mes de la actividad AIS en la jurisdicción de Lambayeque
(vista "Tendencias" del frontend), a partir de las filas crudas de la 4Wings
Report API con resolución MENSUAL -- ver gfw_client.obtener_presencia_mensual
y obtener_esfuerzo_mensual.

Funciones puras (sin red ni base de datos) para poder testearlas con filas
armadas a mano: la consulta a GFW y la cache viven en gfw.py."""
from collections import defaultdict

BANDERA_LOCAL = "PER"
TIPO_PESQUERO = "FISHING"
TOP_BUQUES_POR_MES = 5


def _vacio_a_none(valor):
    return valor if valor not in (None, "") else None


def agregar_por_mes(presencia: list[dict], esfuerzo: list[dict]) -> dict[str, dict]:
    """Devuelve {"YYYY-MM": resumen} con:

    - buquesPresentes / horasPresencia: TODA embarcación con AIS dentro del
      polígono ese mes (pesqueras, carga, apoyo...), del dataset de presencia.
    - porTipo: esas mismas, contadas por vesselType de GFW.
    - pesquerosPresentes / pesquerosExtranjeros / porBanderaPesqueros: solo
      las de vesselType FISHING. Se separan porque verificado con datos
      reales (2024-2026) ~60% de la presencia es tráfico mercante en
      tránsito (CARGO con bandera de Liberia, Panamá, Islas Marshall...):
      contar "extranjeros" sobre el total mide rutas comerciales, no flota
      pesquera extranjera (p.ej. los ~190 poteros chinos de jun-2024).
    - buquesPescando / horasPesca: solo las que el modelo de GFW marcó con
      pesca aparente (dataset de esfuerzo). No es pesca medida, es inferida
      a partir del patrón de movimiento.
    - celdas: [[lat, lon, horas]] de pesca aparente sumadas entre barcos,
      para el mapa de calor.
    - topBuques: las TOP_BUQUES_POR_MES con más horas de pesca ese mes.

    Un mismo barco cuenta una sola vez por mes aunque aparezca en varias
    filas (varias celdas en esfuerzo)."""
    meses: dict[str, dict] = defaultdict(
        lambda: {
            "presentes": {},  # vesselId -> (flag, vesselType)
            "horas_presencia": 0.0,
            "pescando": defaultdict(float),  # vesselId -> horas
            "identidad": {},  # vesselId -> (nombre, mmsi, flag)
            "celdas": defaultdict(float),  # (lat, lon) -> horas
        }
    )

    for fila in presencia:
        vessel_id = _vacio_a_none(fila.get("vesselId"))
        if not vessel_id or not fila.get("date"):
            continue
        mes = meses[fila["date"][:7]]
        mes["presentes"][vessel_id] = (_vacio_a_none(fila.get("flag")), _vacio_a_none(fila.get("vesselType")))
        mes["horas_presencia"] += fila.get("hours") or 0

    for fila in esfuerzo:
        vessel_id = _vacio_a_none(fila.get("vesselId"))
        if not vessel_id or not fila.get("date"):
            continue
        mes = meses[fila["date"][:7]]
        horas = fila.get("hours") or 0
        mes["pescando"][vessel_id] += horas
        mes["identidad"][vessel_id] = (
            _vacio_a_none(fila.get("shipName")),
            _vacio_a_none(fila.get("mmsi")),
            _vacio_a_none(fila.get("flag")),
        )
        if fila.get("lat") is not None and fila.get("lon") is not None:
            mes["celdas"][(round(fila["lat"], 2), round(fila["lon"], 2))] += horas

    resultado = {}
    for clave, mes in meses.items():
        por_bandera_pesqueros: dict[str, int] = defaultdict(int)
        por_tipo: dict[str, int] = defaultdict(int)
        for flag, vessel_type in mes["presentes"].values():
            por_tipo[vessel_type or "Desconocido"] += 1
            if vessel_type == TIPO_PESQUERO:
                por_bandera_pesqueros[flag or "Desconocida"] += 1

        top = sorted(mes["pescando"].items(), key=lambda item: item[1], reverse=True)[:TOP_BUQUES_POR_MES]
        resultado[clave] = {
            "buquesPresentes": len(mes["presentes"]),
            "horasPresencia": round(mes["horas_presencia"], 1),
            "porTipo": dict(por_tipo),
            "pesquerosPresentes": sum(por_bandera_pesqueros.values()),
            "pesquerosExtranjeros": sum(
                n for flag, n in por_bandera_pesqueros.items() if flag not in (BANDERA_LOCAL, "Desconocida")
            ),
            "porBanderaPesqueros": dict(por_bandera_pesqueros),
            "buquesPescando": len(mes["pescando"]),
            "horasPesca": round(sum(mes["pescando"].values()), 1),
            "celdas": [[lat, lon, round(horas, 2)] for (lat, lon), horas in mes["celdas"].items() if horas > 0],
            "topBuques": [
                {
                    "vesselId": vessel_id,
                    "nombre": mes["identidad"][vessel_id][0],
                    "mmsi": mes["identidad"][vessel_id][1],
                    "flag": mes["identidad"][vessel_id][2],
                    "horas": round(horas, 1),
                }
                for vessel_id, horas in top
            ],
        }
    return resultado


def resumen_vacio() -> dict:
    """Mes sin ninguna fila en GFW (p.ej. veda, o todavía no publicado):
    se devuelve igual con ceros para que el eje de tiempo del frontend no
    tenga huecos."""
    return {
        "buquesPresentes": 0,
        "horasPresencia": 0.0,
        "porTipo": {},
        "pesquerosPresentes": 0,
        "pesquerosExtranjeros": 0,
        "porBanderaPesqueros": {},
        "buquesPescando": 0,
        "horasPesca": 0.0,
        "celdas": [],
        "topBuques": [],
    }


def _celda_principal(filas: list[dict]) -> dict:
    # Misma idea que sync_lambayeque.agrupar_por_embarcacion: la celda donde
    # pasó más horas, no un promedio (que podría caer donde nunca estuvo).
    return max(filas, key=lambda f: f.get("hours") or 0)


def barcos_del_mes(presencia: list[dict], esfuerzo: list[dict]) -> list[dict]:
    """Una fila por embarcación vista en el mes (vista "Histórico"), con la
    misma forma que LambayequeVessel del mapa de monitoreo más
    "pescando"/"horasPresencia".

    La posición es la celda donde más pescó si tuvo pesca aparente (es lo
    que interesa ubicar), y si no, la celda donde más tiempo pasó. "horas"
    son horas de pesca aparente (0 si no pescó), igual que en monitoreo."""
    presencia_por_barco: dict[str, list[dict]] = defaultdict(list)
    esfuerzo_por_barco: dict[str, list[dict]] = defaultdict(list)
    for fila in presencia:
        if _vacio_a_none(fila.get("vesselId")):
            presencia_por_barco[fila["vesselId"]].append(fila)
    for fila in esfuerzo:
        if _vacio_a_none(fila.get("vesselId")):
            esfuerzo_por_barco[fila["vesselId"]].append(fila)

    barcos = []
    for vessel_id in presencia_por_barco.keys() | esfuerzo_por_barco.keys():
        filas_pesca = esfuerzo_por_barco.get(vessel_id, [])
        filas_presencia = presencia_por_barco.get(vessel_id, [])
        horas_pesca = sum(f.get("hours") or 0 for f in filas_pesca)
        principal = _celda_principal(filas_pesca if horas_pesca > 0 else filas_presencia or filas_pesca)
        if principal.get("lat") is None or principal.get("lon") is None:
            continue
        barcos.append({
            "embarcacionId": None,
            "vesselId": vessel_id,
            "nombre": principal.get("shipName") or "Desconocido",
            "mmsi": _vacio_a_none(principal.get("mmsi")),
            "flag": _vacio_a_none(principal.get("flag")),
            "vesselType": _vacio_a_none(principal.get("vesselType")),
            "lat": principal["lat"],
            "lon": principal["lon"],
            "horas": round(horas_pesca, 2),
            "horasPresencia": round(sum(f.get("hours") or 0 for f in filas_presencia), 1),
            "pescando": horas_pesca > 0,
        })
    return barcos
