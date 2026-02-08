"""Database utilities for pipeline metadata queries."""

import psycopg2
import psycopg2.extras
from typing import Any
from src.config.settings import settings


def get_connection():
    """Get a PostgreSQL connection."""
    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    )


def execute_query(sql: str, params: tuple = None, read_only: bool = True) -> list[dict]:
    """Execute a SQL query and return results as list of dicts."""
    conn = get_connection()
    try:
        if read_only:
            conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            conn.commit()
            return []
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_write(sql: str, params: tuple = None) -> int:
    """Execute a write query and return affected row count."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
