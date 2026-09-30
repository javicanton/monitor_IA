"""Decoradores de autorización."""

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from auth.session import load_user_by_identity


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = load_user_by_identity(get_jwt_identity())
        if not user or user.role != 'admin':
            return jsonify({'error': 'Se requieren privilegios de administrador'}), 403
        return fn(*args, **kwargs)

    return wrapper


def allowed_email_required(fn):
    """Exige JWT válido y que el email siga en la allowlist."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = load_user_by_identity(get_jwt_identity())
        if not user:
            return jsonify({'error': 'No autorizado'}), 401
        return fn(*args, **kwargs)

    return wrapper
