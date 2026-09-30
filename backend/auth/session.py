"""Creación de tokens JWT y resolución de usuarios."""

from __future__ import annotations

from datetime import datetime

from flask_jwt_extended import create_access_token

from auth.allowlist import get_role_for_email, is_email_allowed
from models import User, db


def normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def get_or_create_user(email: str, name: str | None = None) -> User | None:
    """Obtiene o crea un usuario si el email está en la allowlist."""
    email = normalize_email(email)
    if not is_email_allowed(email):
        return None

    role = get_role_for_email(email)
    user = User.query.filter_by(email=email).first()
    if user:
        user.role = role
        user.is_active = True
        user.email_verified = True
        if name and not user.name:
            user.name = name
        return user

    display_name = name or email.split('@')[0]
    user = User(
        email=email,
        name=display_name,
        role=role,
        password=None,
    )
    user.is_active = True
    user.email_verified = True
    db.session.add(user)
    return user


def issue_access_token(user: User) -> str:
    user.last_login = datetime.utcnow()
    db.session.commit()
    # flask-jwt-extended v4+ recomienda identity como string
    return create_access_token(identity=str(user.id))


def load_user_by_identity(identity) -> User | None:
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return None
    if not is_email_allowed(user.email):
        return None
    return user
