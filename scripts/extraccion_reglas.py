"""
Alternativa a extract_incident() de analyze_news.py que NO depende de la API
de Anthropic. Usa reglas por palabras clave para relevancia/tipo de
infracción + spaCy (NER en español) para embarcación y ubicación, en vez de
un LLM.

analyze_news.py la usa automáticamente cuando no hay ANTHROPIC_API_KEY
configurada, o cuando Claude falla para una URL puntual (ver
_extract_incident_local en ese módulo).

Probado contra 5 artículos reales (gestion.pe, larepublica.pe, infobae.com,
rpp.pe): acierta relevancia + tipo de infracción + embarcación + ubicación en
los 4 casos que narran un hecho concreto (multa, embarcación detectada,
derrame puntual). Falla en notas genéricas/de análisis que hablan del tema
sin describir un hecho concreto -- ahí las marca como relevantes por error
(falso positivo), porque el conteo de palabras clave no distingue "narra un
hecho" de "opina sobre el tema" como sí lo haría un LLM. Como la Cola de
Validación IA igual pasa por revisión de un analista antes de aprobar, un
falso positivo ahí es ruido descartable, no un incidente falso automático.

Uso (standalone, para seguir probando):
    python scripts/extraccion_reglas.py <url>
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

import spacy

_NLP = None


def _nlp():
    global _NLP
    if _NLP is None:
        _NLP = spacy.load("es_core_news_md")
    return _NLP


# Señales de que la noticia describe un hecho concreto de infracción (no una
# nota genérica del sector pesquero: exportaciones, ferias, cuotas, etc.)
PALABRAS_RELEVANCIA = [
    "pesca ilegal", "pesca no autorizada", "pesca clandestina", "flota ilegal",
    "sin autorización", "sin autorizacion", "sin permiso", "sin licencia",
    "decomis", "incautad", "detenid", "detención", "detencion", "arrestad",
    "capturad", "sancion", "multa", "denuncia penal", "denunciad",
    "infracción", "infraccion", "irregular", "clandestin",
    # "interven"/"intercept" cubren los verbos más comunes de estas notas
    # (intervenida, intervenido, intervino, interceptó, interceptada) -- se
    # encontró en pruebas reales que faltaban por completo de esta lista.
    "interven", "intervino", "intervinieron", "intercept",
    "doble fondo", "bodega oculta", "compartimento oculto",
    "apagó su señal", "apago su senal", "apagón ais", "apagon ais",
    "sin señal ais", "sin senal ais", "desconectó el ais", "desconecto el ais",
    "evade el control", "evita el control", "eludir el control", "eludiendo el control",
    "zona reservada", "zona prohibida", "reserva de 5 millas", "milla marina artesanal",
    "transbordo ilegal", "transbordo no autorizado", "trasiego ilegal",
    "vertimiento", "derrame", "contamina",
    "zona económica exclusiva", "zona economica exclusiva",
    "encuentro sospechoso", "reunión de embarcaciones", "reunion de embarcaciones",
    "puerto no autorizado", "atracó sin autorización", "atraco sin autorizacion",
    "control satelital", "seguimiento satelital", "monitoreo satelital",
    "posicionamiento apagado", "dispositivo de seguimiento",
]

# Señales de nota genérica del sector (bajan la confianza si dominan el texto)
PALABRAS_GENERICAS = [
    "exportación", "exportacion", "mercado internacional", "feria gastronómica",
    "feria gastronomica", "producto bandera", "gastronomía", "gastronomia",
    "temporada de pesca", "cuota de pesca aprobada", "acuerdo comercial",
    "tratado de libre comercio", "crecimiento económico", "crecimiento economico",
]

TIPO_INFRACCION_PALABRAS: dict[str, list[str]] = {
    "Pesca en Zona Prohibida": [
        "zona prohibida", "zona reservada", "reserva de 5 millas", "milla artesanal",
        "área protegida", "area protegida", "zona protegida",
        "dentro de las 5 millas", "5 millas del mar", "5 millas de la costa",
    ],
    "Falta de Permiso": [
        "sin permiso", "sin autorización", "sin autorizacion", "sin licencia",
        "licencia vencida", "no autorizada", "no autorizado",
    ],
    "Transbordo Ilegal": [
        "transbordo ilegal", "transbordo no autorizado", "trasiego ilegal", "trasbordo",
    ],
    "Contaminación": [
        "contamina", "derrame", "vertimiento", "residuos al mar", "combustible al mar",
    ],
    # OJO: términos como "control satelital"/"seguimiento satelital" se
    # sacaron a propósito -- aparecen tanto cuando SÍ se apagó el AIS como en
    # texto puramente regulatorio ("la ley exige seguimiento satelital"), y
    # en un artículo sobre navegación sin permiso ganaban por frecuencia sin
    # que la nota hablara de una pérdida de señal real. Ver
    # RE_APAGADO_CERCA_DE_SEÑAL para cubrir esos casos con más precisión.
    "Pérdida de Señal AIS": [
        "apagó su señal", "apago su senal", "apagón ais", "apagon ais",
        "sin señal ais", "sin senal ais", "desconectó el ais", "desconecto el ais",
    ],
    "Velocidad Inusual": [
        "velocidad inusual", "aceleró de forma", "acelero de forma",
        "movimiento errático", "movimiento erratico",
    ],
    "Encuentro Sospechoso en Alta Mar": [
        "encuentro sospechoso", "reunión de embarcaciones", "reunion de embarcaciones",
        "cita en alta mar", "transbordo en altamar",
    ],
    "Incursión en Zona Económica Exclusiva": [
        "zona económica exclusiva", "zona economica exclusiva", "incursión en la zee",
        "incursion en la zee", "aguas jurisdiccionales",
        "200 millas marinas", "límite de las 200 millas", "limite de las 200 millas",
        "dominio marítimo", "dominio maritimo",
    ],
    "Visita a Puerto no Autorizado": [
        "puerto no autorizado", "atracó sin autorización", "atraco sin autorizacion",
        "ingreso irregular a puerto", "ingreso sospechoso", "arribo forzoso",
    ],
}

# Caso "la embarcación china Lu Rong Yuan Yu 698": el nombre viene pegado al
# sustantivo, sin comillas.
# Los adjetivos cubren ambos géneros ("barco chino" / "embarcación china"):
# faltaban las formas masculinas y se perdían casos reales (ver docstring).
_ADJETIVOS_EMBARCACION = (
    r"chin[oa]|peruan[oa]|extranjer[oa]|ecuatorian[oa]|corean[oa]|taiwan[eé]sa?|"
    r"pesquer[oa]|industrial|artesanal|de\sbandera\s\w+"
)
RE_EMBARCACION_PEGADA = re.compile(
    r"(?:embarcaci[oó]n|buque|nave|pesquero|barco)s?\s+"
    rf"(?:(?:{_ADJETIVOS_EMBARCACION})\s+){{0,2}}"
    r"([A-Z0-9ÁÉÍÓÚÑ][\wÁÉÍÓÚÑ]*(?:\s+[A-Z0-9ÁÉÍÓÚÑ][\wÁÉÍÓÚÑ]*){0,4})"
)

# Caso "una embarcación ... identificada/conocida como 'María Victoria B'": el
# nombre viene entre comillas (rectas o tipográficas), a veces con texto de
# por medio ("identificada como", "de nombre", etc.) entre el sustantivo y la
# comilla -- se prueba primero porque es más confiable que RE_EMBARCACION_PEGADA
# cuando hay comillas de por medio.
RE_EMBARCACION_ENTRE_COMILLAS = re.compile(
    r"(?:embarcaci[oó]n|buque|nave|pesquero|barco)s?"
    r"[^\"'“”]{0,60}?"
    r"[\"'“]([^\"'”]{2,60})[\"'”]",
    re.IGNORECASE,
)

# Señal fuerte de "Pérdida de Señal AIS": "apagado"/"desconectado" cerca de
# "señal"/"posicionamiento"/etc., en cualquier orden ("apagó su señal" o
# "mantuvo apagado su equipo de posicionamiento"). Más preciso que contar
# palabras sueltas -- ver el comentario en TIPO_INFRACCION_PALABRAS.
RE_APAGADO_CERCA_DE_SEÑAL = re.compile(
    r"(?:apag[oó]|apagad[oa]|desconect[oó]|desconectad[oa])[^.]{0,50}"
    r"(?:se[ñn]al|\bais\b|posicionamiento|rastreo|transmisor)"
    r"|"
    r"(?:se[ñn]al|\bais\b|posicionamiento|rastreo|transmisor)[^.]{0,50}"
    r"(?:apag[oó]|apagad[oa]|desconect[oó]|desconectad[oa])",
    re.IGNORECASE,
)

# Señal fuerte de "Falta de Permiso": "sin" cerca de "autorización"/"permiso"/
# "licencia", en cualquier orden y con texto de por medio ("sin contar con la
# autorización de zarpe"), en vez de exigir la frase exacta pegada.
RE_SIN_AUTORIZACION = re.compile(
    r"\bsin\b[^.]{0,30}(?:autorizaci[oó]n|permiso|licencia)",
    re.IGNORECASE,
)

# Matrícula de pesca (ej. "matrícula 37499-BM"): a diferencia del nombre, SÍ
# es una identidad válida para crear la fila de embarcaciones (ver
# chk_embarcacion_tiene_identidad en schema.sql) -- vale la pena extraerla
# aunque el nombre ya se haya encontrado, porque muchas embarcaciones
# artesanales nunca van a aparecer en una búsqueda de GFW (no transmiten AIS).
RE_MATRICULA = re.compile(
    r"matr[ií]cula\s*:?\s*(?:n[°º]?\.?\s*)?([A-Z]{0,4}-?\d{3,8}-?[A-Z]{0,4})",
    re.IGNORECASE,
)


@dataclass
class ExtraccionLocal:
    es_relevante: bool
    titular: str
    resumen: str | None
    tipo_infraccion: str | None
    embarcacion_detectada: str | None
    matricula_detectada: str | None
    ubicacion_estimada: str | None
    confianza: float
    debug: dict = field(default_factory=dict)


def _contar_coincidencias(texto_low: str, palabras: list[str]) -> int:
    total = 0
    for p in palabras:
        if p[0].isdigit():
            # Evita que p.ej. "5 millas..." matchee dentro de "175 millas..."
            # (el "5" final de 175) -- .count() hace substring puro, sin
            # respetar límites de número.
            total += len(re.findall(r"(?<!\d)" + re.escape(p), texto_low))
        else:
            total += texto_low.count(p)
    return total


def _clasificar_relevancia(texto_low: str) -> tuple[bool, float, int]:
    positivas = _contar_coincidencias(texto_low, PALABRAS_RELEVANCIA)
    genericas = _contar_coincidencias(texto_low, PALABRAS_GENERICAS)
    es_relevante = positivas >= 1 and positivas > genericas * 0.5
    confianza = max(0.0, min(1.0, 0.25 + 0.15 * positivas - 0.1 * genericas))
    return es_relevante, confianza, positivas


def _clasificar_tipo(texto: str, texto_low: str) -> str | None:
    if RE_APAGADO_CERCA_DE_SEÑAL.search(texto):
        return "Pérdida de Señal AIS"
    if RE_SIN_AUTORIZACION.search(texto):
        return "Falta de Permiso"

    mejor_tipo = None
    mejor_score = 0
    for tipo, palabras in TIPO_INFRACCION_PALABRAS.items():
        score = _contar_coincidencias(texto_low, palabras)
        if score > mejor_score:
            mejor_score = score
            mejor_tipo = tipo
    return mejor_tipo


def _extraer_embarcacion(texto: str) -> str | None:
    m = RE_EMBARCACION_ENTRE_COMILLAS.search(texto)
    if m:
        return m.group(1).strip()
    m = RE_EMBARCACION_PEGADA.search(texto)
    return m.group(1).strip() if m else None


def _extraer_matricula(texto: str) -> str | None:
    m = RE_MATRICULA.search(texto)
    return m.group(1).strip().upper() if m else None


# Siglas/organismos del sector que el modelo NER etiqueta como LOC por error
# (nombres propios en mayúscula, mismo patrón superficial que un lugar).
ORGANISMOS_NO_LUGAR = {
    "produce", "calamasur", "sernanp", "imarpe", "fondepes", "osinergmin",
    "dicapi", "oefa", "sanipes", "congreso", "snp", "uit",
    "sociedad nacional de pesquería", "ministerio de la producción",
    "ministerio público", "fiscalía", "fiscalía especializada",
    "policía nacional", "pnp", "poder judicial", "estado", "estado peruano",
}


def _extraer_ubicacion(doc) -> str | None:
    # Solo LOC: MISC mezcla organizaciones/siglas (p.ej. "Produce") que no son
    # lugares, y diluían el conteo del lugar real más mencionado.
    lugares = [ent.text for ent in doc.ents if ent.label_ == "LOC" and ent.text.lower() not in ORGANISMOS_NO_LUGAR]
    if not lugares:
        return None
    from collections import Counter
    return Counter(lugares).most_common(1)[0][0]


def _resumen_extractivo(texto: str, max_oraciones: int = 2) -> str:
    oraciones = re.split(r"(?<=[.!?])\s+", texto.strip())
    return " ".join(oraciones[:max_oraciones])[:400]


def extraer(titulo: str, texto: str) -> ExtraccionLocal:
    texto_low = texto.lower()
    es_relevante, confianza, n_positivas = _clasificar_relevancia(texto_low)

    if not es_relevante:
        return ExtraccionLocal(
            es_relevante=False,
            titular=titulo,
            resumen=None,
            tipo_infraccion=None,
            embarcacion_detectada=None,
            matricula_detectada=None,
            ubicacion_estimada=None,
            confianza=confianza,
            debug={"positivas": n_positivas},
        )

    embarcacion = _extraer_embarcacion(texto)
    matricula = _extraer_matricula(texto)
    if embarcacion is None and matricula is None:
        # En los 7 artículos reales probados (ver docstring del módulo), los
        # 5 que describen un hecho concreto SIEMPRE nombran la embarcación (o
        # dan su matrícula); los 2 falsos positivos (nota de RPP sobre el
        # problema en general, conferencia WWF/Produce) no nombran ninguna.
        # No tener ninguna identidad es la señal más confiable de "esto no es
        # un hecho puntual" que se encontró -- se descarta acá en vez de
        # dejarla pendiente con "No determinado" en la Cola de Validación.
        return ExtraccionLocal(
            es_relevante=False,
            titular=titulo,
            resumen=None,
            tipo_infraccion=None,
            embarcacion_detectada=None,
            matricula_detectada=None,
            ubicacion_estimada=None,
            confianza=min(confianza, 0.3),
            debug={"positivas": n_positivas, "motivo": "sin embarcación ni matrícula"},
        )

    doc = _nlp()(texto[:5000])
    return ExtraccionLocal(
        es_relevante=True,
        titular=titulo,
        resumen=_resumen_extractivo(texto),
        tipo_infraccion=_clasificar_tipo(texto, texto_low),
        embarcacion_detectada=embarcacion,
        matricula_detectada=matricula,
        ubicacion_estimada=_extraer_ubicacion(doc),
        confianza=confianza,
        debug={"positivas": n_positivas, "entidades": [(e.text, e.label_) for e in doc.ents]},
    )


def main() -> None:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from analyze_news import fetch_article

    url = sys.argv[1]
    titulo, texto, _fecha_publicacion = fetch_article(url)
    resultado = extraer(titulo, texto)
    print(f"es_relevante:          {resultado.es_relevante}")
    print(f"confianza:              {resultado.confianza:.2f}")
    print(f"titular:                {resultado.titular}")
    print(f"resumen:                {resultado.resumen}")
    print(f"tipo_infraccion:        {resultado.tipo_infraccion}")
    print(f"embarcacion_detectada:  {resultado.embarcacion_detectada}")
    print(f"matricula_detectada:    {resultado.matricula_detectada}")
    print(f"ubicacion_estimada:     {resultado.ubicacion_estimada}")
    print(f"debug:                  {resultado.debug}")


if __name__ == "__main__":
    main()
