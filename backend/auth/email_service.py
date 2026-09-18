"""Envío de magic links por correo (Flask-Mail / SES)."""

from __future__ import annotations

import logging
import os

from flask import current_app
from flask_mail import Message

logger = logging.getLogger(__name__)


def _mail_configured() -> bool:
    return bool(
        current_app.config.get('MAIL_USERNAME')
        and current_app.config.get('MAIL_PASSWORD')
        and current_app.config.get('MAIL_DEFAULT_SENDER')
    )


def send_magic_link_email(to_email: str, magic_link_url: str) -> bool:
    """
    Envía el magic link. Si el correo no está configurado, registra el enlace
    en logs (útil en desarrollo) y no lanza error.
    """
    subject = 'Tu enlace de acceso a MonitorIA'
    body = (
        'Hola,\n\n'
        'Usa este enlace para iniciar sesión en MonitorIA '
        '(caduca en 15 minutos y solo se puede usar una vez):\n\n'
        f'{magic_link_url}\n\n'
        'Si no solicitaste este acceso, ignora este mensaje.\n'
    )

    if not _mail_configured():
        logger.warning(
            'Correo no configurado; magic link para %s: %s',
            to_email,
            magic_link_url,
        )
        return False

    try:
        mail = current_app.extensions.get('mail')
        if mail is None:
            logger.error('Extensión flask-mail no inicializada')
            return False
        msg = Message(
            subject=subject,
            recipients=[to_email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
        )
        mail.send(msg)
        logger.info('Magic link enviado a %s', to_email)
        return True
    except Exception as exc:
        logger.exception('Error enviando magic link a %s: %s', to_email, exc)
        raise


def dev_return_link_enabled() -> bool:
    return os.environ.get('AUTH_DEV_RETURN_LINK', '').lower() in ('1', 'true', 'yes')
