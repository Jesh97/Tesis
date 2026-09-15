import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.pool
from dotenv import load_dotenv
from fastapi import HTTPException
from psycopg2 import errors as pg_errors
from psycopg2.extras import RealDictCursor

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    # Conecta perezosamente (recién en la primera consulta), igual que
    # pg.Pool de node-postgres, en lugar de al importar el módulo.
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, dsn=DATABASE_URL)
    return _pool


@contextmanager
def get_cursor():
    """Cursor con auto-commit/rollback, equivalente a pool.query() de node-postgres."""
    conn = _get_pool().getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


# Las funciones de db/procedures.sql señalan un error de negocio (duplicado,
# no encontrado, estado inválido, etc.) con `RAISE EXCEPTION '<status>|<mensaje>'`.
# Todas las rutas llaman a las funciones a través de este helper en vez de
# psycopg2 directo, para traducir eso a un HTTPException sin repetir el
# try/except en cada endpoint.
_PATRON_ERROR_SP = re.compile(r"^(\d{3})\|(.*)$", re.DOTALL)


def ejecutar_sp(cur, sql: str, parametros: tuple = ()) -> None:
    try:
        cur.execute(sql, parametros)
    except pg_errors.RaiseException as err:
        mensaje = (err.diag.message_primary or str(err)).strip()
        coincidencia = _PATRON_ERROR_SP.match(mensaje)
        if coincidencia:
            raise HTTPException(status_code=int(coincidencia.group(1)), detail={"error": coincidencia.group(2)}) from err
        raise HTTPException(status_code=500, detail={"error": mensaje}) from err
