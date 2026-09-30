# -*- coding: utf-8 -*-
"""
Upsert de canales y mensajes en PostgreSQL.
Usado por scripts/import_dataset.py y scraper.py (--postgres).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from flask import Flask

from config import Config
from models import Channel, Message, db

logger = logging.getLogger(__name__)

_channel_cache: Dict[str, int] = {}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


def _normalize_username(value) -> str:
    username = str(value or "").strip()
    return username or "Desconocido"


def _normalize_title(row, username: str) -> str:
    if "Title" in row and pd.notna(row.get("Title")):
        title = str(row.get("Title")).strip()
        if title:
            return title
    return username


def _parse_int(value, default: int = 0) -> int:
    try:
        parsed = int(pd.to_numeric(value, errors="coerce"))
        return default if pd.isna(parsed) else parsed
    except (TypeError, ValueError):
        return default


def _parse_float(value, default: float = 0.0) -> float:
    try:
        parsed = float(pd.to_numeric(value, errors="coerce"))
        return default if pd.isna(parsed) else parsed
    except (TypeError, ValueError):
        return default


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in ("", "nat", "none", "null")
    return False


def _optional_str(value, max_len: Optional[int] = None) -> Optional[str]:
    if _is_missing(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if max_len is not None:
        text = text[:max_len]
    return text or None


def _parse_dt(value):
    if _is_missing(value):
        return None
    try:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
        if _is_missing(parsed):
            return None
        if hasattr(parsed, "tzinfo") and parsed.tzinfo is not None:
            return parsed.tz_convert(None).to_pydatetime()
        return parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed
    except Exception:
        return None


def _parse_label(value) -> Optional[int]:
    if _is_missing(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_or_create_channel(username: str, title: str) -> int:
    if username in _channel_cache:
        return _channel_cache[username]
    channel = Channel.query.filter_by(username=username).first()
    if not channel:
        channel = Channel(username=username, title=title)
        db.session.add(channel)
        db.session.flush()
    elif title and channel.title != title:
        channel.title = title
    _channel_cache[username] = channel.id
    return channel.id


def _row_fields(row) -> Optional[Tuple[int, int, Dict[str, Any]]]:
    username = _normalize_username(row.get("Username"))
    title = _normalize_title(row, username)
    message_id = _parse_int(row.get("Message ID"), default=-1)
    if message_id < 0:
        return None
    channel_id = _get_or_create_channel(username, title)
    fields = {
        "message_text": _optional_str(row.get("Message Text"), 500000),
        "date_sent": _parse_dt(row.get("Date Sent")),
        "views": _parse_int(row.get("Views")),
        "forwards": _parse_int(row.get("Forwards")),
        "replies": _parse_int(row.get("Replies")),
        "url": _optional_str(row.get("URL"), 2000),
        "embed": _optional_str(row.get("Embed"), 50000),
        "score": _parse_float(row.get("Score")),
        "label": _parse_label(row.get("Label")),
        "media_type": _optional_str(row.get("Media Type"), 100),
        "creation_date": _parse_dt(row.get("Creation Date")),
        "edit_date": _parse_dt(row.get("Edit Date")),
        "average_views": (
            _parse_float(row.get("Average Views"))
            if pd.notna(row.get("Average Views", None))
            else None
        ),
    }
    return message_id, channel_id, fields


def upsert_dataframe(
    df: pd.DataFrame,
    batch_size: int = 500,
    preserve_labels: bool = True,
) -> Dict[str, int]:
    """
    Inserta o actualiza mensajes. Devuelve estadísticas {channels, inserted, updated}.
    """
    if df is None or df.empty:
        return {"channels": 0, "inserted": 0, "updated": 0}

    if "Username" not in df.columns or "Message ID" not in df.columns:
        raise ValueError("El DataFrame debe incluir columnas 'Username' y 'Message ID'")

    stats = {"channels": 0, "inserted": 0, "updated": 0}
    total = len(df)

    for start in range(0, total, batch_size):
        batch = df.iloc[start : start + batch_size]
        for _, row in batch.iterrows():
            parsed = _row_fields(row)
            if not parsed:
                continue
            message_id, channel_id, fields = parsed
            existing = Message.query.filter_by(message_id=message_id, channel_id=channel_id).first()
            if existing:
                existing.message_text = fields["message_text"]
                existing.date_sent = fields["date_sent"]
                existing.views = fields["views"]
                existing.forwards = fields["forwards"]
                existing.replies = fields["replies"]
                existing.url = fields["url"]
                existing.embed = fields["embed"]
                existing.score = fields["score"]
                existing.media_type = fields["media_type"]
                existing.creation_date = fields["creation_date"]
                existing.edit_date = fields["edit_date"]
                existing.average_views = fields["average_views"]
                incoming_label = fields["label"]
                if incoming_label is not None:
                    existing.label = incoming_label
                elif not preserve_labels:
                    existing.label = None
                stats["updated"] += 1
            else:
                db.session.add(
                    Message(
                        message_id=message_id,
                        channel_id=channel_id,
                        **fields,
                    )
                )
                stats["inserted"] += 1
        db.session.commit()
        logger.info(
            "pg_upsert: procesadas %d / %d filas (+%d nuevos, ~%d actualizados)",
            min(start + batch_size, total),
            total,
            stats["inserted"],
            stats["updated"],
        )

    stats["channels"] = len(_channel_cache)
    return stats


def upsert_records(records: list, batch_size: int = 500, preserve_labels: bool = True) -> Dict[str, int]:
    if not records:
        return {"channels": 0, "inserted": 0, "updated": 0}
    return upsert_dataframe(pd.DataFrame(records), batch_size=batch_size, preserve_labels=preserve_labels)


def clear_channel_cache() -> None:
    _channel_cache.clear()
