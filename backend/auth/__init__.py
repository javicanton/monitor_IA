"""Autenticación: magic link + allowlist (OAuth preparado para fase 2)."""

from auth.decorators import admin_required, allowed_email_required
from auth.routes import auth_bp

__all__ = [
    'auth_bp',
    'admin_required',
    'allowed_email_required',
]
