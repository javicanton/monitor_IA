# -*- coding: utf-8 -*-
"""
Búsqueda full-text sobre PostgreSQL (tsvector / plainto_tsquery / to_tsquery).
Usado cuando DATABASE_URL está definido; no se carga el dataset en memoria.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import text

from search_boolean import has_boolean_operators, parse_boolean_search, parsed_to_tsquery

logger = logging.getLogger(__name__)

_VECTOR = "to_tsvector('spanish', coalesce(m.message_text, '') || ' ' || coalesce(m.url, ''))"


def search_message_row_ids_pg(query: str) -> Optional[List[int]]:
    """
    Busca en message_text y en la URL del mensaje.
    Devuelve la clave interna messages.id de cada fila que coincide.
    Soporta operadores AND, OR y NOT si están presentes en la consulta.
    """
    q = (query or "").strip()
    if not q:
        return None
    try:
        if has_boolean_operators(q):
            parsed = parse_boolean_search(q)
            tsq = parsed_to_tsquery(parsed) if parsed else None
            if tsq:
                try:
                    sql = text(
                        f"""
                        SELECT m.id
                        FROM messages m
                        WHERE {_VECTOR} @@ to_tsquery('spanish', :tsq)
                        """
                    )
                    return db_execute(sql, {"tsq": tsq})
                except Exception as bool_exc:
                    logger.warning(
                        "search_index_pg: to_tsquery falló para '%s' (%s); probando plainto_tsquery",
                        q[:50],
                        bool_exc,
                    )
        sql = text(
            f"""
            SELECT m.id
            FROM messages m
            WHERE {_VECTOR} @@ plainto_tsquery('spanish', :q)
            """
        )
        return db_execute(sql, {"q": q})
    except Exception as exc:
        logger.warning("search_index_pg: error en búsqueda '%s': %s", q[:50], exc)
        return None


def db_execute(sql, params) -> Optional[List[int]]:
    from models import db

    result = db.session.execute(sql, params)
    rows = result.fetchall()
    ids = [r[0] for r in rows if r and r[0] is not None]
    return ids


# Alias legacy
search_message_ids_pg = search_message_row_ids_pg
