"""
Analiza URLs de noticias (o de reportes en PDF, p.ej. de la Marina de Guerra
del Perú/DICAPI) para la Cola de Validación IA: descarga el documento,
extrae el texto legible, y usa Claude para determinar si describe una
infracción de pesca real (incidentes_sugeridos_ia).

El backend Node (POST /api/fuentes/analizar) crea las filas en
fuentes_noticias y llama a este script como subproceso, pasándole por
stdin la lista de fuentes a procesar.

Si no hay ANTHROPIC_API_KEY configurada, o Claude falla para una URL puntual
(clave inválida, 429, etc.), se usa como alternativa la extracción local por
reglas + spaCy de extraccion_reglas.py (sin costo ni dependencia de red hacia
Anthropic, pero con más falsos positivos en notas genéricas -- ver el
docstring de ese módulo para el detalle de las pruebas hechas). Esa
extracción local trabaja sobre texto plano y no le importa si vino de HTML o
de un PDF, así que no necesitó ningún cambio para soportar reportes en PDF.

Uso:
    echo '[{"id": "<fuente-uuid>", "url": "https://..."}]' | python scripts/analyze_news.py

Variables de entorno (se leen de server/.env):
    ANTHROPIC_API_KEY (opcional: sin ella, se usa solo la extracción local)
    DATABASE_URL
"""

import json
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import anthropic
import psycopg2
import requests
import trafilatura
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pypdf import PdfReader

import extraccion_reglas

ENV_FILE = Path(__file__).resolve().parent.parent / "server" / ".env"
load_dotenv(ENV_FILE)

USER_AGENT = "Mozilla/5.0 (compatible; PescaIlegalBot/1.0; monitoreo pesquero institucional)"
MAX_CHARS = 12000  # cota razonable de costo/latencia por artículo

# Líneas de relleno que trafilatura a veces deja dentro del texto "legible"
# (marcadores de anuncios, pies de imagen sueltos, "leer más") -- ensucian
# tanto el resumen (si el título es la primera línea real, la primera
# oración termina siendo "PUBLICIDAD") como la extracción de ubicación/tipo
# de infracción local, así que se filtran antes de devolver el texto.
_RE_LINEA_RUIDO = re.compile(
    r"^(publicidad|imagen|video recomendado|leer m[aá]s|fecha (de )?actualizaci[oó]n:?|"
    r"\d{1,2}/\d{1,2}/\d{2,4}\s*-\s*\d{1,2}:\d{2})$",
    re.IGNORECASE,
)


def _limpiar_texto(texto: str) -> str:
    lineas = [linea for linea in texto.split("\n") if linea.strip() and not _RE_LINEA_RUIDO.match(linea.strip())]
    return "\n".join(lineas)


class Extraction(BaseModel):
    es_relevante: bool = Field(
        description="true solo si la noticia describe una infracción de pesca marítima real (no pesca en general)"
    )
    titular: str
    resumen: Optional[str] = Field(default=None, description="resumen breve de 1-2 frases del hecho")
    tipo_infraccion: Optional[str] = Field(
        default=None, description="debe ser EXACTAMENTE uno de los nombres del catálogo dado, o null"
    )
    embarcacion_detectada: Optional[str] = Field(default=None, description="nombre de la embarcación si se menciona")
    # Distinta de embarcacion_detectada: la matrícula SÍ es una identidad
    # verificable (a diferencia de un nombre suelto) y permite vincular la
    # embarcación en la base de datos aunque no tenga AIS público -- ver
    # chk_embarcacion_tiene_identidad en db/schema.sql y sp_embarcaciones_vincular_o_crear.
    matricula_detectada: Optional[str] = Field(
        default=None, description="matrícula de pesca de la embarcación si se menciona explícitamente, EXACTAMENTE como aparece en el texto (ej: '37499-BM')"
    )
    ubicacion_estimada: Optional[str] = None
    confianza: float = Field(description="qué tan seguro estás de es_relevante y tipo_infraccion, entre 0 y 1")


def _es_pdf(content_type: str, url: str) -> bool:
    return "application/pdf" in content_type.lower() or urlparse(url).path.lower().endswith(".pdf")


def _extraer_de_pdf(contenido: bytes, url: str) -> tuple[str, str]:
    """Extrae título + texto de un PDF (p.ej. un reporte de la Marina de
    Guerra del Perú/DICAPI) leyendo su capa de texto -- NO hace OCR: un PDF
    escaneado (una foto/imagen del documento sin texto seleccionable) no se
    puede procesar así, y cae en el ValueError de abajo en vez de en un
    resultado vacío o inventado."""
    try:
        lector = PdfReader(BytesIO(contenido))
    except Exception as exc:
        raise ValueError(f"No se pudo leer el PDF de {url}: {exc}") from exc

    texto = _limpiar_texto("\n".join(pagina.extract_text() or "" for pagina in lector.pages).strip())
    if len(texto) < 200:
        raise ValueError(
            f"No se pudo extraer texto útil del PDF {url} "
            "(probablemente es un documento escaneado sin capa de texto -- este pipeline no hace OCR)"
        )

    metadata_titulo = lector.metadata.title if lector.metadata else None
    nombre_archivo = Path(urlparse(url).path).stem.replace("-", " ").replace("_", " ").strip()
    titulo = metadata_titulo or nombre_archivo or "Reporte PDF"
    return titulo, texto


def fetch_article(url: str) -> tuple[str, str, Optional[str]]:
    """Descarga y extrae título + texto legible + fecha de publicación de la
    fuente -- un artículo de noticias (HTML, vía trafilatura/Readability) o
    un reporte en PDF (vía _extraer_de_pdf), detectado por Content-Type o por
    la extensión de la URL. Los PDF no traen una fecha de publicación
    equivalente a la metadata de htmldate, así que ese campo siempre es None
    para ellos -- el incidente cae a now() en ese caso (ver
    sp_incidentes_registrar_desde_sugerencia)."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"No se pudo descargar {url}: {exc}") from exc

    if _es_pdf(resp.headers.get("Content-Type", ""), url):
        titulo, texto = _extraer_de_pdf(resp.content, url)
        return titulo, texto, None

    extraido = trafilatura.extract(resp.text, url=url, output_format="json", with_metadata=True)
    if not extraido:
        raise ValueError(f"No se pudo extraer contenido legible de {url} (¿requiere JavaScript?)")

    data = json.loads(extraido)
    texto = _limpiar_texto((data.get("text") or "").strip())
    if len(texto) < 200:
        raise ValueError(f"Contenido demasiado corto en {url}")

    return data.get("title") or "", texto, data.get("date") or None


def _extract_incident_claude(
    client: anthropic.Anthropic, titulo: str, texto: str, tipos_infraccion: list[str]
) -> Extraction:
    catalogo = "\n".join(f"- {t}" for t in tipos_infraccion)
    response = client.messages.parse(
        model="claude-opus-5",
        max_tokens=1024,
        system=(
            "Eres un analista que revisa noticias abiertas para un sistema de detección de pesca ilegal "
            "en el Perú.\nEvalúa si la noticia describe una infracción de pesca marítima concreta (no una "
            "nota genérica sobre el sector pesquero).\nSi aplica un tipo de infracción, debe ser EXACTAMENTE "
            f"uno de estos valores del catálogo (usa null si ninguno aplica):\n{catalogo}"
        ),
        messages=[
            {
                "role": "user",
                "content": f"TITULAR: {titulo}\n\nTEXTO DEL ARTÍCULO:\n{texto[:MAX_CHARS]}",
            }
        ],
        output_format=Extraction,
    )
    if response.parsed_output is None:
        raise ValueError("El modelo no devolvió una salida estructurada válida")
    return response.parsed_output


def _extract_incident_local(titulo: str, texto: str, tipos_infraccion: list[str]) -> Extraction:
    resultado = extraccion_reglas.extraer(titulo, texto)
    tipo_infraccion = resultado.tipo_infraccion if resultado.tipo_infraccion in tipos_infraccion else None
    return Extraction(
        es_relevante=resultado.es_relevante,
        titular=resultado.titular,
        resumen=resultado.resumen,
        tipo_infraccion=tipo_infraccion,
        embarcacion_detectada=resultado.embarcacion_detectada,
        matricula_detectada=resultado.matricula_detectada,
        ubicacion_estimada=resultado.ubicacion_estimada,
        confianza=resultado.confianza,
    )


def extract_incident(
    client: Optional[anthropic.Anthropic], titulo: str, texto: str, tipos_infraccion: list[str]
) -> Extraction:
    """Usa Claude si hay cliente disponible; si no hay ANTHROPIC_API_KEY, o
    Claude falla para esta URL puntual (clave inválida, 429, etc.), cae a la
    extracción local por reglas en vez de marcar la fuente como fallida."""
    if client is not None:
        try:
            return _extract_incident_claude(client, titulo, texto, tipos_infraccion)
        except (anthropic.APIError, ValueError) as exc:
            print(f"[analyze_news] Claude no disponible ({exc}); usando extracción local por reglas", file=sys.stderr)
    return _extract_incident_local(titulo, texto, tipos_infraccion)


def get_tipos_infraccion(cur) -> list[str]:
    cur.execute("SELECT * FROM sp_tipos_infraccion_nombres()")
    return [row[0] for row in cur.fetchall()]


def analyze_source(cur, client: Optional[anthropic.Anthropic], fuente_id: str, url: str, tipos_infraccion: list[str]) -> None:
    try:
        titulo, texto, fecha_publicacion = fetch_article(url)
        extraction = extract_incident(client, titulo, texto, tipos_infraccion)

        if not extraction.es_relevante:
            cur.execute("SELECT sp_fuentes_marcar_estado(%s, 'descartada')", (fuente_id,))
            print(f"DESCARTADA  {url}")
            return

        tipo_infraccion_id = None
        if extraction.tipo_infraccion:
            cur.execute("SELECT * FROM sp_tipos_infraccion_obtener_por_nombre(%s)", (extraction.tipo_infraccion,))
            row = cur.fetchone()
            tipo_infraccion_id = row[0] if row else None

        # Dos medios distintos pueden cubrir el mismo hecho con URLs
        # distintas -- sp_fuentes_crear solo deduplica por URL exacta, así
        # que esto cubre el caso de la misma embarcación ya reportada.
        posible_duplicado = False
        if extraction.embarcacion_detectada or extraction.matricula_detectada:
            cur.execute(
                "SELECT sp_sugerencias_verificar_duplicado(%s, %s)",
                (extraction.embarcacion_detectada, extraction.matricula_detectada),
            )
            posible_duplicado = cur.fetchone()[0]

        cur.execute(
            "SELECT sp_sugerencias_crear(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                fuente_id,
                extraction.titular or titulo,
                extraction.resumen,
                tipo_infraccion_id,
                extraction.embarcacion_detectada,
                extraction.ubicacion_estimada,
                extraction.confianza,
                fecha_publicacion,
                extraction.matricula_detectada,
                posible_duplicado,
            ),
        )
        cur.execute("SELECT sp_fuentes_marcar_estado(%s, 'exitosa')", (fuente_id,))
        print(f"OK          {url}")

    except Exception as exc:  # noqa: BLE001 - se registra y se continúa con el resto del lote
        print(f"ERROR       {url}: {exc}", file=sys.stderr)
        cur.execute("SELECT sp_fuentes_marcar_estado(%s, 'fallida')", (fuente_id,))


def main() -> None:
    raw = sys.stdin.read()
    fuentes = json.loads(raw) if raw.strip() else []
    if not fuentes:
        print('No se recibieron fuentes por stdin (se espera JSON: [{"id", "url"}, ...])', file=sys.stderr)
        return

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit(f"Falta DATABASE_URL en {ENV_FILE}")

    if anthropic_key:
        client = anthropic.Anthropic(api_key=anthropic_key)
    else:
        print("[analyze_news] Sin ANTHROPIC_API_KEY: se usa solo la extracción local por reglas", file=sys.stderr)
        client = None

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                tipos_infraccion = get_tipos_infraccion(cur)
                for fuente in fuentes:
                    analyze_source(cur, client, fuente["id"], fuente["url"], tipos_infraccion)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
