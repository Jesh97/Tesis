import re
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..actividad_mensual import resumen_vacio
from ..gfw import consultar_actividad_mensual_rango, consultar_barcos_mes_con_cache

router = APIRouter()

_PATRON_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Cada año fuera de cache son 2 consultas pesadas a GFW (presencia +
# esfuerzo, ~10-20s cada una): se acota el rango para que una sola petición
# no dispare decenas de consultas ni roce el rate limit de GFW.
MAX_MESES = 36
# Por defecto: los últimos 24 meses cerrados (sin el mes en curso, que
# siempre está incompleto) -- alcanza para comparar dos temporadas de pesca
# de anchoveta seguidas.
MESES_POR_DEFECTO = 24


def _sumar_meses(anio: int, mes: int, delta: int) -> tuple[int, int]:
    total = anio * 12 + (mes - 1) + delta
    return total // 12, total % 12 + 1


def _parsear_mes(valor: str, campo: str) -> tuple[int, int]:
    if not _PATRON_MES.match(valor):
        raise HTTPException(status_code=400, detail={"error": f'"{campo}" debe tener el formato AAAA-MM'})
    anio, mes = valor.split("-")
    return int(anio), int(mes)


def rango_por_defecto(hoy: date) -> tuple[str, str]:
    hasta = _sumar_meses(hoy.year, hoy.month, -1)
    desde = _sumar_meses(*hasta, -(MESES_POR_DEFECTO - 1))
    return f"{desde[0]}-{desde[1]:02d}", f"{hasta[0]}-{hasta[1]:02d}"


# Vista "Tendencias" (TrendsPage.tsx): comportamiento mes a mes de las
# embarcaciones con AIS dentro de la jurisdicción de Lambayeque. Solo lee
# GFW (con cache por año, ver gfw.consultar_actividad_mensual_con_cache): los
# incidentes por mes para comparar salen aparte, de
# /api/reportes/incidentes-por-mes-rango.
@router.get("/mensual")
def actividad_mensual(desde: str | None = Query(default=None), hasta: str | None = Query(default=None)):
    hoy = date.today()
    desde_defecto, hasta_defecto = rango_por_defecto(hoy)
    anio_desde, mes_desde = _parsear_mes(desde or desde_defecto, "desde")
    anio_hasta, mes_hasta = _parsear_mes(hasta or hasta_defecto, "hasta")

    # No tiene sentido pedir meses futuros: se recorta al mes en curso.
    if (anio_hasta, mes_hasta) > (hoy.year, hoy.month):
        anio_hasta, mes_hasta = hoy.year, hoy.month

    cantidad = (anio_hasta - anio_desde) * 12 + (mes_hasta - mes_desde) + 1
    if cantidad < 1:
        raise HTTPException(status_code=400, detail={"error": '"desde" debe ser anterior o igual a "hasta"'})
    if cantidad > MAX_MESES:
        raise HTTPException(status_code=400, detail={"error": f"El rango no puede superar {MAX_MESES} meses"})

    try:
        por_mes = consultar_actividad_mensual_rango(list(range(anio_desde, anio_hasta + 1)))
    except Exception as err:
        raise HTTPException(status_code=502, detail={"error": str(err)}) from err

    mes_en_curso = f"{hoy.year}-{hoy.month:02d}"

    meses = []
    for i in range(cantidad):
        anio, mes = _sumar_meses(anio_desde, mes_desde, i)
        clave = f"{anio}-{mes:02d}"
        meses.append({"mes": clave, "parcial": clave == mes_en_curso, **por_mes.get(clave, resumen_vacio())})

    return {"desde": meses[0]["mes"], "hasta": meses[-1]["mes"], "meses": meses}


# Vista "Histórico" (HistoricoPage.tsx): el mapa de monitoreo, pero con las
# embarcaciones de un mes puntual del pasado. Incluye todas las que tuvieron
# AIS en la zona ese mes (no solo las que pescaron), marcadas con "pescando".
@router.get("/historico")
def historico(mes: str = Query(...)):
    anio, numero_mes = _parsear_mes(mes, "mes")
    hoy = date.today()
    if (anio, numero_mes) > (hoy.year, hoy.month):
        raise HTTPException(status_code=400, detail={"error": '"mes" no puede ser futuro'})

    try:
        barcos = consultar_barcos_mes_con_cache(anio, numero_mes)
    except Exception as err:
        raise HTTPException(status_code=502, detail={"error": str(err)}) from err

    return {
        "mes": mes,
        "parcial": (anio, numero_mes) == (hoy.year, hoy.month),
        "total": len(barcos),
        "pescando": sum(1 for b in barcos if b["pescando"]),
        "barcos": barcos,
    }
