"""Registro de actividad de usuarios (logins + acciones API clave)."""

from __future__ import annotations

import logging
from typing import Any

from flask import Request, g, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from auth.session import load_user_by_identity
from models import User, UserActivity, db

logger = logging.getLogger(__name__)

# Acciones a registrar (método + path en el backend, tras el proxy /api → /).
_TRACKED_EXACT = {
    ('POST', '/filter_messages'): 'filter_messages',
    ('POST', '/label'): 'label_message',
    ('GET', '/export_relevants'): 'export_relevants',
    ('POST', '/download_filtered_messages'): 'download_filtered_messages',
    ('GET', '/download_channel_graph'): 'download_channel_graph',
    ('GET', '/messages_over_time'): 'messages_over_time',
    ('POST', '/messages_over_time'): 'messages_over_time',
    ('POST', '/admin/run_topics'): 'admin_run_topics',
    ('POST', '/admin/topic_titles'): 'admin_set_topic_titles',
    ('POST', '/auth/logout'): 'logout',
    ('POST', '/api/auth/logout'): 'logout',
}


def _client_ip(req: Request | None = None) -> str | None:
    req = req or request
    forwarded = (req.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return forwarded or req.remote_addr


def _truncate_ua(req: Request | None = None) -> str | None:
    req = req or request
    ua = req.headers.get('User-Agent') or ''
    return ua[:255] if ua else None


def _filter_meta_from_request(req: Request) -> dict[str, Any] | None:
    """Resume filtros/búsqueda sin guardar payloads enormes."""
    try:
        data = req.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return None
    meta: dict[str, Any] = {}
    search = data.get('search')
    if isinstance(search, str) and search.strip():
        meta['search'] = search.strip()[:200]
    for key in (
        'dateStart', 'dateEnd', 'channel', 'excludeChannel',
        'scoreMin', 'scoreMax', 'mediaType', 'sortBy', 'topic', 'label',
    ):
        if key in data and data[key] not in (None, '', [], {}):
            val = data[key]
            if isinstance(val, list):
                meta[key] = val[:20]
            elif isinstance(val, str):
                meta[key] = val[:100]
            else:
                meta[key] = val
    return meta or None


def resolve_action(method: str, path: str) -> str | None:
    method = (method or '').upper()
    path = path or ''
    if len(path) > 1 and path.endswith('/'):
        path = path.rstrip('/')

    exact = _TRACKED_EXACT.get((method, path))
    if exact:
        return exact

    if method == 'GET' and (
        path.startswith('/load_more/') or path.startswith('/api/load_more/')
    ):
        return 'load_more'

    return None


def log_activity(
    action: str,
    *,
    user: User | None = None,
    email: str | None = None,
    path: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
    meta: dict | None = None,
    req: Request | None = None,
) -> None:
    """Persiste un evento. Nunca lanza al caller."""
    try:
        req = req or request
        row = UserActivity(
            user_id=user.id if user else None,
            email=(email or (user.email if user else None)),
            action=action,
            path=path or (req.path if req else None),
            method=method or (req.method if req else None),
            status_code=status_code,
            ip=_client_ip(req) if req else None,
            user_agent=_truncate_ua(req) if req else None,
            meta=meta,
        )
        db.session.add(row)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning('No se pudo registrar actividad (%s): %s', action, exc)


def register_activity_tracking(app) -> None:
    """Hooks Flask para registrar acciones API clave."""

    @app.before_request
    def _capture_activity_meta():
        action = resolve_action(request.method, request.path)
        if action in ('filter_messages', 'download_filtered_messages', 'messages_over_time'):
            g.activity_meta = _filter_meta_from_request(request)
        elif action == 'label_message':
            data = request.get_json(silent=True) or {}
            g.activity_meta = {
                'message_id': data.get('message_id'),
                'label': data.get('label'),
            }
        elif action == 'load_more':
            g.activity_meta = {'offset': request.view_args.get('offset') if request.view_args else None}

    @app.after_request
    def _log_tracked_request(response):
        try:
            action = resolve_action(request.method, request.path)
            if not action:
                return response

            user = None
            try:
                verify_jwt_in_request(optional=True)
                user = load_user_by_identity(get_jwt_identity())
            except Exception:
                user = None

            if action == 'logout':
                log_activity(
                    'logout',
                    user=user,
                    status_code=response.status_code,
                )
                return response

            if response.status_code >= 400 or not user:
                return response

            log_activity(
                action,
                user=user,
                status_code=response.status_code,
                meta=getattr(g, 'activity_meta', None),
            )
        except Exception as exc:
            logger.debug('activity after_request skip: %s', exc)
        return response
