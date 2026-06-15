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


def search_message_row_ids_pg(query: str) -> Optional[List[int]]:
    """
    Busca en message_text y en la URL del mensaje.
    Devuelve la clave interna messages.id de cada fila que coincide.
    Usar messages.id (no message_id de Telegram): el mismo número puede repetirse en otro canal.
    """
    q = (query or "").strip()
    if not q:
        return None
    try:
        sql = text(
            """
            SELECT m.id
            FROM messages m
            WHERE to_tsvector('spanish', coalesce(m.message_text, '') || ' ' || coalesce(m.url, ''))
                  @@ plainto_tsquery('spanish', :q)
            """
        )
        result = db.session.execute(sql, {"q": q})
        rows = result.fetchall()
        ids = [r[0] for r in rows if r and r[0] is not None]
        logger.info("search_index_pg: búsqueda '%s' -> %d filas", q[:50], len(ids))
        return ids
    except Exception as exc:
        logger.warning("search_index_pg: error en búsqueda '%s': %s", q[:50], exc)
        return None


# Alias legacy
search_message_ids_pg = search_message_row_ids_pg
