# -*- coding: utf-8 -*-
"""Grafo de canales (reenvíos) y lista monitored_channels."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from models import Channel, ChannelEdge, MonitoredChannel, db

logger = logging.getLogger(__name__)


def normalize_username(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip()
    text = text.replace("https://", "").replace("http://", "")
    text = text.replace("t.me/", "").replace("telegram.me/", "")
    if text.startswith("@"):
        text = text[1:]
    text = text.split("/")[0].split("?")[0].strip()
    return text.lower()


def get_or_create_channel_row(username: str, title: Optional[str] = None) -> Optional[Channel]:
    username = normalize_username(username)
    if not username:
        return None
    channel = Channel.query.filter_by(username=username).first()
    if not channel:
        channel = Channel(username=username, title=title or username)
        db.session.add(channel)
        db.session.flush()
    elif title and channel.title != title:
        channel.title = title
    return channel


def load_active_monitored_usernames() -> List[str]:
    rows = (
        MonitoredChannel.query.filter(
            MonitoredChannel.status == "active",
            MonitoredChannel.discontinued.is_(False),
        )
        .order_by(MonitoredChannel.username)
        .all()
    )
    return [row.username for row in rows]


def mark_monitored_channel_error(username: str, error_message: str) -> None:
    username = normalize_username(username)
    if not username:
        return
    row = MonitoredChannel.query.filter_by(username=username).first()
    if not row:
        row = MonitoredChannel(
            username=username,
            title=username,
            status="error",
            discontinued=True,
            source="csv_import",
            last_error=(error_message or "")[:2000],
        )
        db.session.add(row)
    else:
        row.status = "error"
        row.discontinued = True
        row.last_error = (error_message or "")[:2000]
    db.session.commit()
    logger.warning("Canal marcado como descontinuado: %s — %s", username, error_message[:120])


def mark_monitored_channel_success(username: str, title: Optional[str] = None) -> None:
    username = normalize_username(username)
    if not username:
        return
    row = MonitoredChannel.query.filter_by(username=username).first()
    now = datetime.utcnow()
    if not row:
        row = MonitoredChannel(
            username=username,
            title=title or username,
            status="active",
            discontinued=False,
            source="csv_import",
            last_scraped_at=now,
        )
        db.session.add(row)
    else:
        row.status = "active"
        row.discontinued = False
        row.last_error = None
        row.last_scraped_at = now
        if title:
            row.title = title
    db.session.commit()


def upsert_channel_edges(pairs: Iterable[Tuple[str, str]], batch_commit: int = 200) -> int:
    """Incrementa aristas origen→destino. pairs: (source_username, target_username)."""
    updated = 0
    now = datetime.utcnow()
    pending = 0
    for source_username, target_username in pairs:
        source_username = normalize_username(source_username)
        target_username = normalize_username(target_username)
        if not source_username or not target_username or source_username == target_username:
            continue
        source = get_or_create_channel_row(source_username)
        target = get_or_create_channel_row(target_username)
        if not source or not target:
            continue
        edge = ChannelEdge.query.filter_by(
            source_channel_id=source.id,
            target_channel_id=target.id,
        ).first()
        if edge:
            edge.forward_count = (edge.forward_count or 0) + 1
            edge.last_seen_at = now
        else:
            db.session.add(
                ChannelEdge(
                    source_channel_id=source.id,
                    target_channel_id=target.id,
                    forward_count=1,
                    last_seen_at=now,
                )
            )
        updated += 1
        pending += 1
        if pending >= batch_commit:
            db.session.commit()
            pending = 0
    if pending:
        db.session.commit()
    return updated


def is_channel_invalid_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "channelinvalid",
            "no user has",
            "nobody is using",
            "username not occupied",
            "username invalid",
            "username is unacceptable",
            "could not find",
        )
    )


def is_telegram_session_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "wrong session id" in text or "security error while unpacking" in text


async def resolve_forward_username(message, client) -> Optional[str]:
    """Resuelve el username del canal origen de un reenvío."""
    try:
        forward = getattr(message, "forward", None)
        if not forward:
            return None
        chat = getattr(forward, "chat", None)
        if chat and getattr(chat, "username", None):
            return chat.username
        if getattr(forward, "channel_id", None):
            entity = await client.get_entity(forward.channel_id)
            return getattr(entity, "username", None)
        fwd_from = getattr(message, "fwd_from", None)
        if fwd_from and getattr(fwd_from, "from_id", None):
            entity = await client.get_entity(fwd_from.from_id)
            return getattr(entity, "username", None)
    except Exception as exc:
        logger.debug("No se pudo resolver forward: %s", exc)
    return None
