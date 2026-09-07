import json
import os
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from starlette import status

from ..db import get_cursor

router = APIRouter()

URL_LIMIT = 10  # mismo límite que muestra WebAnalyzerCard en el frontend

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # raíz del repo
ANALYZE_SCRIPT = BASE_DIR / "scripts" / "analyze_news.py"
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")


def _run_analyze_news_script(fuentes: list[dict]) -> None:
    """Lanza scripts/analyze_news.py (fetch + readability + Claude) como
    subproceso, pasándole el lote por stdin. No se espera a que termine: el
    cliente hace polling vía GET /api/fuentes o GET /api/sugerencias."""

    def _run() -> None:
        try:
            proc = subprocess.Popen(
                [PYTHON_BIN, str(ANALYZE_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out, err = proc.communicate(input=json.dumps(fuentes))
            if out.strip():
                print(f"[analyze_news] {out.strip()}")
            if err.strip():
                print(f"[analyze_news] {err.strip()}")
        except Exception as exc:
            print(f"[analyze_news] no se pudo iniciar el proceso Python: {exc}")

    threading.Thread(target=_run, daemon=True).start()


@router.post("/analizar", status_code=status.HTTP_202_ACCEPTED)
def analizar(body: dict = Body(...)):
    urls = body.get("urls")
    if not isinstance(urls, list) or len(urls) == 0:
        raise HTTPException(status_code=400, detail={"error": 'Se requiere un arreglo "urls" con al menos un elemento'})
    if len(urls) > URL_LIMIT:
        raise HTTPException(status_code=400, detail={"error": f"Máximo {URL_LIMIT} URLs por lote"})

    creados: list[dict] = []
    with get_cursor() as cur:
        for raw_url in urls:
            if not isinstance(raw_url, str):
                continue

            try:
                from urllib.parse import urlparse

                parsed = urlparse(raw_url)
                if not parsed.scheme or not parsed.netloc:
                    continue
                dominio = parsed.hostname or ""
                if dominio.startswith("www."):
                    dominio = dominio[4:]
            except Exception:
                continue  # URL inválida: se ignora silenciosamente

            cur.execute(
                """INSERT INTO fuentes_noticias (url, dominio, estado)
                   VALUES (%s, %s, 'procesando') RETURNING id""",
                (raw_url, dominio),
            )
            creados.append({"id": cur.fetchone()["id"], "url": raw_url})

    if creados:
        _run_analyze_news_script(creados)

    return {"fuentes": creados}


@router.get("")
def listar():
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, url, dominio, estado, creado_en, procesado_en
               FROM fuentes_noticias ORDER BY creado_en DESC LIMIT 50"""
        )
        return cur.fetchall()
