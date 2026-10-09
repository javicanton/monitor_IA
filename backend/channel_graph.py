# -*- coding: utf-8 -*-
"""Grafo de canales (reenvíos) y lista monitored_channels."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func

from models import Channel, ChannelEdge, Message, MonitoredChannel, db

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
    """Detecta fallos de sesión Telethon que deben abortar el scraper (no solo un canal)."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if any(token in name for token in ("authkey", "sessionrevoked", "userdeactivated", "sessionexpired")):
        return True
    return (
        "wrong session id" in text
        or "security error while unpacking" in text
        or "authorization key" in text
        or "the key is not registered" in text
        or "session revoked" in text
    )


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


def _message_date_expr():
    return func.coalesce(Message.date_sent, Message.creation_date)


def resolve_channel_row(username: str) -> Optional[Channel]:
    """
    Resuelve la fila `channels` asociada a un username de grafo/monitorización.

    A menudo el username de monitored_channels no coincide exactamente con
    channels.username (p.ej. título distinto, mayúsculas, o el scraper guardó
    el título como identidad). Probamos varias claves para poder calcular stats
    cuando sí hay mensajes.
    """
    username = normalize_username(username)
    if not username:
        return None

    channel = Channel.query.filter_by(username=username).first()
    if channel:
        return channel

    channel = (
        Channel.query.filter(func.lower(Channel.username) == username).first()
    )
    if channel:
        return channel

    mon = MonitoredChannel.query.filter(
        func.lower(MonitoredChannel.username) == username
    ).first()
    if mon and mon.title:
        title = mon.title.strip()
        channel = Channel.query.filter(Channel.title == title).first()
        if channel:
            return channel
        channel = (
            Channel.query.filter(func.lower(Channel.title) == title.lower()).first()
        )
        if channel:
            return channel

    # Título o username que contenga el handle (p.ej. "Alvise …")
    channel = (
        Channel.query.filter(func.lower(Channel.title).like(f"%{username}%"))
        .order_by(Channel.id)
        .first()
    )
    if channel:
        return channel

    return None


def add_or_reactivate_monitored_channel(
    username: str,
    title: Optional[str] = None,
    source: str = "manual",
) -> MonitoredChannel:
    """Alta o reactivación en monitored_channels (uso admin)."""
    username = normalize_username(username)
    if not username:
        raise ValueError("username vacío")
    row = MonitoredChannel.query.filter(
        func.lower(MonitoredChannel.username) == username
    ).first()
    now = datetime.utcnow()
    if not row:
        row = MonitoredChannel(
            username=username,
            title=title or username,
            status="active",
            discontinued=False,
            source=source or "manual",
            last_error=None,
        )
        db.session.add(row)
    else:
        row.status = "active"
        row.discontinued = False
        row.last_error = None
        row.source = source or row.source or "manual"
        if title:
            row.title = title
        row.updated_at = now
    get_or_create_channel_row(username, title=title or (row.title if row else username))
    db.session.commit()
    return row


def build_channel_graph_payload(
    min_forwards: int = 1,
    include_discontinued: bool = True,
) -> Dict[str, Any]:
    """Nodos + aristas para la página de canales (reenvíos)."""
    min_forwards = max(1, int(min_forwards or 1))

    monitored_rows = MonitoredChannel.query.all()
    monitored_by_user: Dict[str, MonitoredChannel] = {
        normalize_username(row.username): row for row in monitored_rows if row.username
    }

    # Conteos por channel_id → luego se indexan por username resuelto
    msg_counts_by_id = {
        int(channel_id): int(count or 0)
        for channel_id, count in (
            db.session.query(Message.channel_id, func.count(Message.id))
            .group_by(Message.channel_id)
            .all()
        )
        if channel_id is not None
    }
    msg_counts: Dict[str, int] = {}
    if msg_counts_by_id:
        for ch in Channel.query.filter(Channel.id.in_(list(msg_counts_by_id.keys()))).all():
            u = normalize_username(ch.username)
            if not u:
                continue
            msg_counts[u] = msg_counts.get(u, 0) + int(msg_counts_by_id.get(ch.id, 0) or 0)

    edge_q = ChannelEdge.query.filter(ChannelEdge.forward_count >= min_forwards)
    edges_raw = edge_q.all()

    channel_ids = set()
    for edge in edges_raw:
        channel_ids.add(edge.source_channel_id)
        channel_ids.add(edge.target_channel_id)

    channels_by_id: Dict[int, Channel] = {}
    if channel_ids:
        for ch in Channel.query.filter(Channel.id.in_(channel_ids)).all():
            channels_by_id[ch.id] = ch

    # Incluir siempre canales monitorizados (aunque sin aristas)
    monitored_usernames = set(monitored_by_user.keys())
    if monitored_usernames:
        for ch in Channel.query.filter(Channel.username.in_(monitored_usernames)).all():
            channels_by_id[ch.id] = ch

    degree: Dict[str, int] = {}
    edges: List[Dict[str, Any]] = []
    for edge in edges_raw:
        source = channels_by_id.get(edge.source_channel_id)
        target = channels_by_id.get(edge.target_channel_id)
        if not source or not target:
            continue
        src_u = normalize_username(source.username)
        tgt_u = normalize_username(target.username)
        if not src_u or not tgt_u or src_u == tgt_u:
            continue
        edges.append(
            {
                "source": src_u,
                "target": tgt_u,
                "forward_count": int(edge.forward_count or 0),
                "last_seen_at": edge.last_seen_at.isoformat() if edge.last_seen_at else None,
            }
        )
        degree[src_u] = degree.get(src_u, 0) + 1
        degree[tgt_u] = degree.get(tgt_u, 0) + 1

    node_usernames = set(degree.keys()) | monitored_usernames
    # Canales solo presentes en aristas (tabla channels)
    for ch in channels_by_id.values():
        u = normalize_username(ch.username)
        if u:
            node_usernames.add(u)

    title_by_user: Dict[str, str] = {}
    for ch in Channel.query.filter(Channel.username.in_(node_usernames)).all() if node_usernames else []:
        title_by_user[normalize_username(ch.username)] = ch.title or ch.username

    nodes: List[Dict[str, Any]] = []
    for username in sorted(node_usernames):
        mon = monitored_by_user.get(username)
        if mon and mon.discontinued and not include_discontinued:
            continue
        status = mon.status if mon else "discovered"
        discontinued = bool(mon.discontinued) if mon else False
        resolved = resolve_channel_row(username)
        msg_count = int(msg_counts.get(username, 0) or 0)
        if msg_count <= 0 and resolved:
            msg_count = int(msg_counts_by_id.get(resolved.id, 0) or 0)
        nodes.append(
            {
                "id": username,
                "username": username,
                "title": (mon.title if mon and mon.title else None)
                or title_by_user.get(username)
                or (resolved.title if resolved else None)
                or username,
                "status": status,
                "discontinued": discontinued,
                "monitored": mon is not None,
                "source": mon.source if mon else None,
                "last_scraped_at": mon.last_scraped_at.isoformat() if mon and mon.last_scraped_at else None,
                "degree": degree.get(username, 0),
                "message_count": msg_count,
            }
        )

    # Filtrar aristas cuyos extremos quedaron fuera (p.ej. discontinued)
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]

    active_count = sum(
        1 for n in nodes if n.get("monitored") and not n.get("discontinued") and n.get("status") == "active"
    )
    emitter_totals: Dict[str, int] = {}
    receiver_totals: Dict[str, int] = {}
    for e in edges:
        emitter_totals[e["source"]] = emitter_totals.get(e["source"], 0) + e["forward_count"]
        receiver_totals[e["target"]] = receiver_totals.get(e["target"], 0) + e["forward_count"]

    def _top(totals: Dict[str, int], limit: int = 5) -> List[Dict[str, Any]]:
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [{"username": u, "forward_count": c} for u, c in ranked]

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "active_count": active_count,
            "monitored_count": sum(1 for n in nodes if n.get("monitored")),
            "min_forwards": min_forwards,
            "top_emitters": _top(emitter_totals),
            "top_receivers": _top(receiver_totals),
        },
    }


def build_channel_stats_payload(username: str, days: Optional[int] = 30) -> Optional[Dict[str, Any]]:
    """Estadísticas agregadas + vecinos para un canal."""
    username = normalize_username(username)
    if not username:
        return None

    mon = MonitoredChannel.query.filter(
        func.lower(MonitoredChannel.username) == username
    ).first()
    channel = resolve_channel_row(username)
    if not channel and not mon:
        return None

    # Si hay mensajes bajo otro username pero mismo título, usar ese channel.id
    resolved_username = normalize_username(channel.username) if channel else username
    title = (
        (mon.title if mon and mon.title else None)
        or (channel.title if channel else None)
        or username
    )

    since = None
    days_window = None
    if days is not None:
        try:
            days_window = int(days)
        except (TypeError, ValueError):
            days_window = 30
        if days_window <= 0:
            days_window = None
        else:
            since = datetime.utcnow() - timedelta(days=days_window)

    stats = {
        "message_count": 0,
        "posts_per_day": 0.0,
        "avg_views": 0.0,
        "avg_forwards": 0.0,
        "avg_replies": 0.0,
        "avg_score": 0.0,
        "first_message_at": None,
        "last_message_at": None,
        "active_days": 0,
        "members_count": None,
        "days": days_window,
    }
    series_posts: List[Dict[str, Any]] = []

    if channel:
        date_expr = _message_date_expr()
        q = db.session.query(
            func.count(Message.id).label("message_count"),
            func.avg(func.coalesce(Message.views, 0)).label("avg_views"),
            func.avg(func.coalesce(Message.forwards, 0)).label("avg_forwards"),
            func.avg(func.coalesce(Message.replies, 0)).label("avg_replies"),
            func.avg(func.coalesce(Message.score, 0.0)).label("avg_score"),
            func.min(date_expr).label("first_at"),
            func.max(date_expr).label("last_at"),
            func.count(func.distinct(func.date(date_expr))).label("active_days"),
        ).filter(Message.channel_id == channel.id)
        if since is not None:
            q = q.filter(date_expr >= since)
        row = q.one()
        message_count = int(row.message_count or 0)
        active_days = int(row.active_days or 0)
        divisor = days_window if days_window else (active_days or 1)
        if not days_window and row.first_at and row.last_at:
            span = max((row.last_at.date() - row.first_at.date()).days + 1, 1)
            divisor = span
        stats.update(
            {
                "message_count": message_count,
                "posts_per_day": round(message_count / float(divisor or 1), 2),
                "avg_views": round(float(row.avg_views or 0), 1),
                "avg_forwards": round(float(row.avg_forwards or 0), 2),
                "avg_replies": round(float(row.avg_replies or 0), 2),
                "avg_score": round(float(row.avg_score or 0), 3),
                "first_message_at": row.first_at.isoformat() if row.first_at else None,
                "last_message_at": row.last_at.isoformat() if row.last_at else None,
                "active_days": active_days,
            }
        )

        series_q = (
            db.session.query(
                func.date(date_expr).label("day"),
                func.count(Message.id).label("count"),
                func.avg(func.coalesce(Message.views, 0)).label("avg_views"),
            )
            .filter(Message.channel_id == channel.id, date_expr.isnot(None))
        )
        if since is not None:
            series_q = series_q.filter(date_expr >= since)
        series_q = series_q.group_by(func.date(date_expr)).order_by(func.date(date_expr))
        series_posts = [
            {
                "date": str(r.day),
                "count": int(r.count or 0),
                "avg_views": round(float(r.avg_views or 0), 1),
            }
            for r in series_q.all()
        ]

    # Vecinos del grafo (por channel.id si existe; si no, vacío)
    inbound: List[Dict[str, Any]] = []
    outbound: List[Dict[str, Any]] = []
    if channel:
        in_edges = (
            ChannelEdge.query.filter_by(target_channel_id=channel.id)
            .order_by(ChannelEdge.forward_count.desc())
            .limit(25)
            .all()
        )
        out_edges = (
            ChannelEdge.query.filter_by(source_channel_id=channel.id)
            .order_by(ChannelEdge.forward_count.desc())
            .limit(25)
            .all()
        )
        src_ids = {e.source_channel_id for e in in_edges}
        tgt_ids = {e.target_channel_id for e in out_edges}
        related = {}
        ids = src_ids | tgt_ids
        if ids:
            for ch in Channel.query.filter(Channel.id.in_(ids)).all():
                related[ch.id] = ch
        for e in in_edges:
            ch = related.get(e.source_channel_id)
            if not ch:
                continue
            inbound.append(
                {
                    "username": normalize_username(ch.username),
                    "title": ch.title or ch.username,
                    "forward_count": int(e.forward_count or 0),
                    "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
                }
            )
        for e in out_edges:
            ch = related.get(e.target_channel_id)
            if not ch:
                continue
            outbound.append(
                {
                    "username": normalize_username(ch.username),
                    "title": ch.title or ch.username,
                    "forward_count": int(e.forward_count or 0),
                    "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
                }
            )

    return {
        "channel": {
            "username": username,
            "resolved_username": resolved_username,
            "title": title,
            "status": mon.status if mon else ("active" if channel else "unknown"),
            "discontinued": bool(mon.discontinued) if mon else False,
            "monitored": mon is not None and not bool(getattr(mon, "discontinued", False)),
            "source": mon.source if mon else None,
            "last_error": mon.last_error if mon else None,
            "last_scraped_at": mon.last_scraped_at.isoformat() if mon and mon.last_scraped_at else None,
            "telegram_url": f"https://t.me/{username}",
            "members_count": None,
        },
        "stats": stats,
        "neighbors": {"inbound": inbound, "outbound": outbound},
        "series": {
            "posts_per_day": [{"date": s["date"], "count": s["count"]} for s in series_posts],
            "avg_views_per_day": [{"date": s["date"], "avg_views": s["avg_views"]} for s in series_posts],
        },
    }
