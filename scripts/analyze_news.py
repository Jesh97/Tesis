"""
Analiza URLs de noticias para la Cola de Validación IA: descarga el
artículo, extrae el texto legible, y usa Claude para determinar si
describe una infracción de pesca real (incidentes_sugeridos_ia).

El backend Node (POST /api/fuentes/analizar) crea las filas en
fuentes_noticias y llama a este script como subproceso, pasándole por
stdin la lista de fuentes a procesar.

Uso:
    echo '[{"id": "<fuente-uuid>", "url": "https://..."}]' | python scripts/analyze_news.py

Variables de entorno (se leen de server/.env):
    ANTHROPIC_API_KEY
    DATABASE_URL
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import anthropic
import psycopg2
import requests
import trafilatura
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ENV_FILE = Path(__file__).resolve().parent.parent / "server" / ".env"
load_dotenv(ENV_FILE)

USER_AGENT = "Mozilla/5.0 (compatible; PescaIlegalBot/1.0; monitoreo pesquero institucional)"
MAX_CHARS = 12000  # cota razonable de costo/latencia por artículo


class Extraction(BaseModel):
    es_relevante: bool = Field(
        description="true solo si la noticia describe una infracción de pesca marítima real (no pesca en general)"
    )
    titular: str
    resumen: Optional[str] = Field(default=None, description="resumen breve de 1-2 frases del hecho")
    tipo_infraccion: Optional[str] = Field(
        default=None, description="debe ser EXACTAMENTE uno de los nombres del catálogo dado, o null"
    )
    embarcacion_detectada: Optional[str] = Field(default=None, description="nombre/matrícula/IMO si hay")
    ubicacion_estimada: Optional[str] = None
    confianza: float = Field(description="qué tan seguro estás de es_relevante y tipo_infraccion, entre 0 y 1")


def fetch_article(url: str) -> tuple[str, str]:
    """Descarga y extrae título + texto legible del artículo (equivalente a Mozilla Readability)."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"No se pudo descargar {url}: {exc}") from exc

    extraido = trafilatura.extract(resp.text, url=url, output_format="json", with_metadata=True)
    if not extraido:
        raise ValueError(f"No se pudo extraer contenido legible de {url} (¿requiere JavaScript?)")

    data = json.loads(extraido)
    texto = (data.get("text") or "").strip()
    if len(texto) < 200:
        raise ValueError(f"Contenido demasiado corto en {url}")

    return data.get("title") or "", texto


def extract_incident(
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


def get_tipos_infraccion(cur) -> list[str]:
    cur.execute("SELECT nombre FROM tipos_infraccion ORDER BY nombre")
    return [row[0] for row in cur.fetchall()]


def analyze_source(cur, client: anthropic.Anthropic, fuente_id: str, url: str, tipos_infraccion: list[str]) -> None:
    try:
        titulo, texto = fetch_article(url)
        extraction = extract_incident(client, titulo, texto, tipos_infraccion)

        if not extraction.es_relevante:
            cur.execute(
                "UPDATE fuentes_noticias SET estado = 'fallida', procesado_en = now() WHERE id = %s",
                (fuente_id,),
            )
            print(f"DESCARTADA  {url}")
            return

        tipo_infraccion_id = None
        if extraction.tipo_infraccion:
            cur.execute("SELECT id FROM tipos_infraccion WHERE nombre = %s", (extraction.tipo_infraccion,))
            row = cur.fetchone()
            tipo_infraccion_id = row[0] if row else None

        cur.execute(
            """
            INSERT INTO incidentes_sugeridos_ia
                (fuente_id, titular, resumen, tipo_infraccion_id, embarcacion_detectada, ubicacion_estimada, confianza)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fuente_id,
                extraction.titular or titulo,
                extraction.resumen,
                tipo_infraccion_id,
                extraction.embarcacion_detectada,
                extraction.ubicacion_estimada,
                extraction.confianza,
            ),
        )
        cur.execute(
            "UPDATE fuentes_noticias SET estado = 'exitosa', procesado_en = now() WHERE id = %s",
            (fuente_id,),
        )
        print(f"OK          {url}")

    except Exception as exc:  # noqa: BLE001 - se registra y se continúa con el resto del lote
        print(f"ERROR       {url}: {exc}", file=sys.stderr)
        cur.execute(
            "UPDATE fuentes_noticias SET estado = 'fallida', procesado_en = now() WHERE id = %s",
            (fuente_id,),
        )


def main() -> None:
    raw = sys.stdin.read()
    fuentes = json.loads(raw) if raw.strip() else []
    if not fuentes:
        print('No se recibieron fuentes por stdin (se espera JSON: [{"id", "url"}, ...])', file=sys.stderr)
        return

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    database_url = os.getenv("DATABASE_URL")
    if not anthropic_key:
        raise SystemExit(f"Falta ANTHROPIC_API_KEY en {ENV_FILE}")
    if not database_url:
        raise SystemExit(f"Falta DATABASE_URL en {ENV_FILE}")

    client = anthropic.Anthropic(api_key=anthropic_key)
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
