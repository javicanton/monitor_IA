# -*- coding: utf-8 -*-
"""
DataStore sobre PostgreSQL. Usado cuando DATABASE_URL está definido.
Todas las consultas son paginadas/filtradas por SQL; no se carga el dataset entero en memoria.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd
from flask import current_app
from sqlalchemy import and_, case, cast, func, or_, text, distinct
from sqlalchemy.orm import joinedload

from models import Channel, Message, MessageTopic, db

logger = logging.getLogger(__name__)

# Límite máximo de resultados por página para evitar consultas pesadas
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 24


def _parse_topic_filter(topic_filter) -> List[int]:
    topic_ids = []
    if isinstance(topic_filter, str):
        topic_ids = [x.strip() for x in topic_filter.split(",") if x.strip()]
    elif isinstance(topic_filter, list):
        topic_ids = list(topic_filter)
    result = []
    for item in topic_ids:
        if isinstance(item, dict) and "id" in item:
            item = item["id"]
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _date_expr(model=Message):
    return func.coalesce(
        model.date_sent,
        model.creation_date,
    )


class DataStorePG:
    """Store de mensajes sobre PostgreSQL. Sin carga en memoria."""

    def _search_query(self, filters: Dict) -> str:
        return (filters.get("search") or filters.get("q") or "").strip()

    def _search_ids(self, filters: Dict) -> Optional[List[int]]:
        search_query = self._search_query(filters)
        if not search_query:
            return None
        try:
            from search_index_pg import search_message_ids_pg

            ids = search_message_ids_pg(search_query)
            if ids:
                return ids
        except Exception as exc:
            logger.warning("Búsqueda full-text PostgreSQL no disponible: %s", exc)
        return None

    def _apply_text_search(self, q, search_query: str):
        terms = [
            term
            for term in search_query.split()
            if term.upper() not in ("AND", "OR", "NOT") and term.strip()
        ]
        if not terms:
            terms = [search_query]
        for term in terms:
            pattern = f"%{term}%"
            q = q.filter(
                or_(
                    Message.message_text.ilike(pattern),
                    Channel.title.ilike(pattern),
                    Message.embed.ilike(pattern),
                )
            )
        return q

    def _apply_filters(
        self,
        q,
        filters: Dict,
        search_ids: Optional[List[int]],
        join_topics: bool,
        use_like_search: bool = False,
    ):
        search_query = self._search_query(filters)
        if search_ids is not None:
            q = q.filter(Message.message_id.in_(search_ids))
        elif use_like_search and search_query:
            q = self._apply_text_search(q, search_query)
        channel = filters.get("channel")
        if channel:
            if isinstance(channel, list):
                q = q.filter(Channel.title.in_(channel))
            else:
                q = q.filter(Channel.title == channel)
        # Channel ya está en el join en el caller; no volver a hacer join

        topic_filter = filters.get("topics") or filters.get("topic")
        topic_ids = _parse_topic_filter(topic_filter) if topic_filter else []
        if topic_ids:
            if not join_topics:
                q = q.outerjoin(MessageTopic, Message.id == MessageTopic.message_id)
            q = q.filter(MessageTopic.topic_id.in_(topic_ids))
        elif join_topics:
            q = q.outerjoin(MessageTopic, Message.id == MessageTopic.message_id)

        score_min = filters.get("scoreMin")
        if score_min not in (None, ""):
            try:
                q = q.filter(Message.score >= float(score_min))
            except (TypeError, ValueError):
                pass
        score_max = filters.get("scoreMax")
        if score_max not in (None, ""):
            try:
                q = q.filter(Message.score <= float(score_max))
            except (TypeError, ValueError):
                pass
        label_val = filters.get("label")
        if label_val not in (None, ""):
            try:
                q = q.filter(Message.label == int(label_val))
            except (TypeError, ValueError):
                pass
        media_type = filters.get("mediaType")
        if media_type:
            types = [media_type] if isinstance(media_type, str) else media_type
            types = [str(t).lower() for t in types if t]
            if types:
                q = q.filter(func.lower(func.coalesce(Message.media_type, "")).in_(types))
        date_start = filters.get("dateStart")
        if date_start:
            q = q.filter(func.date(_date_expr()) >= func.cast(date_start, db.Date))
        date_end = filters.get("dateEnd")
        if date_end:
            q = q.filter(func.date(_date_expr()) <= func.cast(date_end, db.Date))
        return q

    def _order_by(self, q, filters: Dict):
        sort_by = filters.get("sortBy", "score")
        if sort_by == "views":
            return q.order_by(Message.views.desc().nullslast(), Message.message_id.desc())
        if sort_by == "date":
            return q.order_by(_date_expr().desc().nullslast(), Message.message_id.desc())
        if sort_by == "channel":
            return q.order_by(Channel.title.asc(), Message.message_id.desc())
        return q.order_by(Message.score.desc().nullslast(), Message.message_id.desc())

    def query_messages(self, filters: Dict, limit: int, offset: int) -> Tuple[pd.DataFrame, int]:
        limit = min(max(1, limit), MAX_PAGE_SIZE)
        offset = max(0, offset)
        search_query = self._search_query(filters)
        search_ids = self._search_ids(filters) if search_query else None
        use_like_search = bool(search_query and search_ids is None)
        topic_filter = filters.get("topics") or filters.get("topic")
        join_topics = bool(topic_filter)

        q = db.session.query(
            Message.embed,
            func.coalesce(Message.score, 0).label("Score"),
            Message.message_id,
            Message.url,
            Message.label,
            MessageTopic.topic_id if join_topics else cast(None, db.Integer).label("topic_id"),
        )
        if join_topics:
            q = q.outerjoin(MessageTopic, Message.id == MessageTopic.message_id)
        q = q.join(Channel, Message.channel_id == Channel.id)
        q = self._apply_filters(q, filters, search_ids, join_topics, use_like_search=use_like_search)
        count_q = q.with_entities(func.count(distinct(Message.id)))
        total = count_q.scalar() or 0
        q = self._order_by(q, filters)
        q = q.offset(offset).limit(limit)
        rows = q.all()

        data = []
        for r in rows:
            data.append({
                "Embed": r.embed,
                "Score": float(r.Score) if r.Score is not None else 0,
                "Message ID": r.message_id,
                "URL": r.url,
                "Label": r.label,
                "topic_id": r.topic_id,
            })
        df = pd.DataFrame(data)
        return df, total

    def get_channels(self) -> List[str]:
        rows = db.session.query(Channel.title).distinct().filter(
            Channel.title.isnot(None),
            func.trim(Channel.title) != "",
        ).order_by(func.lower(Channel.title)).all()
        return [r[0] for r in rows if r and r[0]]

    def get_date_bounds(self) -> Tuple[Optional[str], Optional[str]]:
        """Devuelve (min_date, max_date) como strings YYYY-MM-DD para el date picker."""
        row = db.session.query(
            func.min(func.date(_date_expr())).label("min_d"),
            func.max(func.date(_date_expr())).label("max_d"),
        ).select_from(Message).filter(_date_expr().isnot(None)).first()
        if not row or (row.min_d is None and row.max_d is None):
            return None, None
        return (
            str(row.min_d) if row.min_d else None,
            str(row.max_d) if row.max_d else None,
        )

    def messages_over_time(self, filters: Dict) -> List[Dict]:
        filters = {k: v for k, v in (filters or {}).items() if k not in ("dateStart", "dateEnd")}
        search_query = self._search_query(filters)
        search_ids = self._search_ids(filters) if search_query else None
        use_like_search = bool(search_query and search_ids is None)
        topic_filter = filters.get("topics") or filters.get("topic")
        join_topics = bool(topic_filter)

        q = db.session.query(
            func.date(_date_expr()).label("day"),
            func.count(Message.id).label("count"),
        ).join(Channel, Message.channel_id == Channel.id)
        if topic_filter:
            q = q.outerjoin(MessageTopic, Message.id == MessageTopic.message_id)
        q = self._apply_filters(q, filters, search_ids, join_topics, use_like_search=use_like_search)
        q = q.filter(_date_expr().isnot(None))
        q = q.group_by(func.date(_date_expr())).order_by(func.date(_date_expr()))
        rows = q.all()
        return [{"date": str(r.day), "count": r.count} for r in rows]

    def export_filtered_dataframe(self, filters: Dict) -> pd.DataFrame:
        topic_filter = filters.get("topics") or filters.get("topic")
        join_topics = bool(topic_filter)
        search_query = self._search_query(filters)
        search_ids = self._search_ids(filters) if search_query else None
        use_like_search = bool(search_query and search_ids is None)

        q = db.session.query(
            Message.message_id,
            Message.message_text,
            Channel.title,
            _date_expr().label("Date Sent"),
            func.coalesce(Message.views, 0).label("Views"),
            func.coalesce(Message.score, 0).label("Score"),
            Message.label,
            Message.url,
            Message.media_type,
            Message.average_views,
            MessageTopic.topic_id if join_topics else cast(None, db.Integer).label("topic_id"),
        )
        if join_topics:
            q = q.outerjoin(MessageTopic, Message.id == MessageTopic.message_id)
        q = q.join(Channel, Message.channel_id == Channel.id)
        q = self._apply_filters(q, filters, search_ids, join_topics, use_like_search=use_like_search)
        q = self._order_by(q, filters)
        rows = q.all()

        columns = [
            "Message ID", "Message Text", "Title", "Date Sent", "Views", "Score",
            "Label", "URL", "Media Type", "Average Views", "topic_id",
        ]
        data = []
        for r in rows:
            data.append({
                "Message ID": r.message_id,
                "Message Text": r.message_text,
                "Title": r[2],
                "Date Sent": r[3],
                "Views": r.Views,
                "Score": r.Score,
                "Label": r.label,
                "URL": r.url,
                "Media Type": r.media_type,
                "Average Views": getattr(r, "average_views", None),
                "topic_id": r.topic_id,
            })
        return pd.DataFrame(data, columns=columns)

    def update_label(self, message_id: int, label: int) -> bool:
        updated = Message.query.filter(Message.message_id == message_id).update({"label": label})
        db.session.commit()
        return updated > 0

    def get_messages_list(self, limit: int = 500) -> List[Dict]:
        """Lista de mensajes para /api/messages con límite para no cargar todo en memoria."""
        limit = min(limit, MAX_PAGE_SIZE * 5)
        q = (
            db.session.query(
                Message.message_id,
                Message.message_text,
                Channel.title,
                Message.views,
                Message.average_views,
                Message.label,
            )
            .join(Channel, Message.channel_id == Channel.id)
            .order_by(Message.score.desc().nullslast(), Message.message_id.desc())
            .limit(limit)
        )
        rows = q.all()
        return [
            {
                "Message ID": r.message_id,
                "Message Text": r.message_text,
                "Title": r.title,
                "Views": r.views,
                "Average Views": r.average_views,
                "Label": r.label,
            }
            for r in rows
        ]
