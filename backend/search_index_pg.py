# -*- coding: utf-8 -*-
"""
Búsqueda full-text sobre PostgreSQL (tsvector/plainto_tsquery).
Usado cuando DATABASE_URL está definido; no se carga el dataset en memoria.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import func, text
from models import Message, db

logger = logging.getLogger(__name__)


def search_message_ids_pg(query: str) -> Optional[List[int]]:
    """
    Busca en message_text y en la URL del mensaje.
    Devuelve lista de message_id que coinciden, o [] si no hay coincidencias.
    Devuelve None solo si la búsqueda no pudo ejecutarse (error).
    """
    q = (query or "").strip()
    if not q:
        return None
    try:
        # Escapar comillas simples para evitar SQL injection
        safe = q.replace("'", "''")
        # plainto_tsquery convierte la frase en tokens AND; config 'spanish' para mejor stemming
        ts_query = f"plainto_tsquery('spanish', :q)"
        sql = text(
            """
            SELECT m.message_id
            FROM messages m
            WHERE to_tsvector('spanish', coalesce(m.message_text, '') || ' ' || coalesce(m.url, ''))
                  @@ plainto_tsquery('spanish', :q)
            """
        )
        result = db.session.execute(sql, {"q": q})
        rows = result.fetchall()
        ids = [r[0] for r in rows if r and r[0] is not None]
        logger.info("search_index_pg: búsqueda '%s' -> %d resultados", q[:50], len(ids))
        return ids
    except Exception as exc:
        logger.warning("search_index_pg: error en búsqueda '%s': %s", q[:50], exc)
        return None
