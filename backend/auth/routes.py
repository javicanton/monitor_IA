"""Rutas HTTP de autenticación (magic link)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from auth.activity import log_activity
from auth.allowlist import is_email_allowed
from auth.decorators import admin_required
from auth.email_service import dev_return_link_enabled, send_magic_link_email
from auth.session import get_or_create_user, issue_access_token, load_user_by_identity, normalize_email
from models import UserActivity, db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

MAGIC_LINK_SALT = 'magic-link-login'
MAGIC_LINK_MAX_AGE = 15 * 60  # 15 minutos

# Tokens de un solo uso (en memoria; suficiente para una sola instancia)
_consumed_tokens: dict[str, datetime] = {}


def _serializer() -> URLSafeTimedSerializer:
    secret = current_app.config.get('SECRET_KEY') or 'your-secret-key'
    return URLSafeTimedSerializer(secret)


def _frontend_base_url() -> str:
    return (
        os.environ.get('AUTH_FRONTEND_URL')
        or os.environ.get('FRONTEND_URL')
        or 'http://localhost:3000'
    ).rstrip('/')


def _purge_consumed_tokens() -> None:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    stale = [k for k, ts in _consumed_tokens.items() if ts < cutoff]
    for key in stale:
        _consumed_tokens.pop(key, None)


def _token_fingerprint(token: str) -> str:
    # Huella corta para marcar consumo sin guardar el token completo
    import hashlib
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:32]


@auth_bp.route('/login-request', methods=['POST'])
def login_request():
    """Solicita un magic link. No revela si el email está o no autorizado."""
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get('email', ''))

    generic = {
        'message': (
            'Si tu correo está autorizado, recibirás un enlace de acceso '
            'en unos minutos.'
        )
    }

    if not email or '@' not in email:
        return jsonify({'error': 'Email no válido'}), 400

    # Misma respuesta genérica si no está en la allowlist
    if not is_email_allowed(email):
        logger.info('Login request rechazado (no allowlist): %s', email)
        return jsonify(generic), 200

    token = _serializer().dumps({'email': email}, salt=MAGIC_LINK_SALT)
    magic_url = f'{_frontend_base_url()}/auth/verify?token={quote(token, safe="")}'

    try:
        sent = send_magic_link_email(email, magic_url)
    except Exception:
        return jsonify({'error': 'No se pudo enviar el correo. Inténtalo más tarde.'}), 502

    payload = dict(generic)
    if not sent and dev_return_link_enabled():
        payload['dev_magic_link'] = magic_url
        logger.info('AUTH_DEV_RETURN_LINK activo: enlace incluido en la respuesta')

    return jsonify(payload), 200


@auth_bp.route('/verify-magic-link/<path:token>', methods=['GET', 'POST'])
def verify_magic_link(token):
    """Valida el magic link, crea/actualiza el usuario y emite JWT."""
    _purge_consumed_tokens()
    fp = _token_fingerprint(token)
    if fp in _consumed_tokens:
        return jsonify({'error': 'Este enlace ya fue utilizado'}), 400

    try:
        data = _serializer().loads(token, salt=MAGIC_LINK_SALT, max_age=MAGIC_LINK_MAX_AGE)
    except SignatureExpired:
        return jsonify({'error': 'El enlace ha caducado. Solicita uno nuevo.'}), 400
    except BadSignature:
        return jsonify({'error': 'Enlace no válido'}), 400

    email = normalize_email(data.get('email', '') if isinstance(data, dict) else '')
    if not email or not is_email_allowed(email):
        return jsonify({'error': 'Acceso no autorizado'}), 403

    try:
        user = get_or_create_user(email)
        if not user:
            return jsonify({'error': 'Acceso no autorizado'}), 403
        access_token = issue_access_token(user)
        _consumed_tokens[fp] = datetime.utcnow()
        log_activity('login', user=user, status_code=200, meta={'method': 'magic_link'})
        return jsonify({
            'access_token': access_token,
            'user': user.to_dict(),
        }), 200
    except Exception as exc:
        db.session.rollback()
        logger.exception('Error verificando magic link: %s', exc)
        return jsonify({'error': 'No se pudo completar el acceso'}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = load_user_by_identity(get_jwt_identity())
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    return jsonify(user.to_dict()), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required(optional=True)
def logout():
    # JWT stateless: el cliente elimina el token. La actividad la registra el after_request.
    return jsonify({'message': 'Sesión cerrada'}), 200


@auth_bp.route('/admin/activity', methods=['GET'])
@admin_required
def list_activity():
    """Lista actividad reciente (solo admin). Query: limit, email, action."""
    try:
        limit = min(int(request.args.get('limit', 100)), 500)
    except (TypeError, ValueError):
        limit = 100
    email = (request.args.get('email') or '').strip().lower()
    action = (request.args.get('action') or '').strip()

    q = UserActivity.query.order_by(UserActivity.created_at.desc())
    if email:
        q = q.filter(UserActivity.email == email)
    if action:
        q = q.filter(UserActivity.action == action)
    rows = q.limit(limit).all()
    return jsonify({
        'success': True,
        'count': len(rows),
        'activities': [r.to_dict() for r in rows],
    }), 200


# --- Endpoints legado desactivados (registro / password) ---

@auth_bp.route('/register', methods=['POST'])
def register_disabled():
    return jsonify({
        'error': 'El registro público está desactivado. Usa el acceso por magic link.'
    }), 403


@auth_bp.route('/login', methods=['POST'])
def login_disabled():
    return jsonify({
        'error': 'Usa POST /api/auth/login-request para solicitar un magic link.'
    }), 410


@auth_bp.route('/forgot-password', methods=['POST'])
@auth_bp.route('/reset-password/<token>', methods=['POST'])
def password_flow_disabled(token=None):
    return jsonify({
        'error': 'El acceso es por magic link; no hay contraseñas que recuperar.'
    }), 410
