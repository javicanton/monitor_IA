"""Envío de magic links por correo (Flask-Mail / SES)."""

from __future__ import annotations

import html
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
    Envía el magic link.

    Evita awstrack.me en la medida de lo posible:
    - HTML con ses:no-track (si el configuration set lo honra)
    - Cabecera X-SES-CONFIGURATION-SET si SES_CONFIGURATION_SET está definida
      (usa un configuration set CON click tracking desactivado)
    - URL también en texto plano para copiar/pegar
    """
    subject = 'Tu enlace de acceso a MonitorIA'
    safe_url = html.escape(magic_link_url, quote=True)
    body = (
        'Hola,\n\n'
        'Para iniciar sesión en MonitorIA, copia y pega ESTA URL completa '
        'en el navegador (caduca en 15 minutos y solo se puede usar una vez):\n\n'
        f'{magic_link_url}\n\n'
        'Importante: usa la URL que empieza por https://app.monitoria.org '
        '(o tu dominio), no la de awstrack.me.\n\n'
        'Si no solicitaste este acceso, ignora este mensaje.\n'
    )
    html_body = (
        '<p>Hola,</p>'
        '<p>Copia y pega esta URL en el navegador para iniciar sesión en MonitorIA '
        '(caduca en 15 minutos, un solo uso):</p>'
        f'<p style="word-break:break-all;font-family:monospace;font-size:14px">{safe_url}</p>'
        # sin <a href> → SES no puede envolver un hipervínculo HTML
        '<p>Si tu cliente convierte la URL en enlace y pasa por awstrack.me, '
        'copia la URL de arriba a mano.</p>'
        '<p>Si no solicitaste este acceso, ignora este mensaje.</p>'
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
            html=html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
        )
        # Configuration set SIN click/open tracking (crear en consola SES)
        config_set = (
            os.environ.get('SES_CONFIGURATION_SET')
            or os.environ.get('AWS_SES_CONFIGURATION_SET')
            or ''
        ).strip()
        if config_set:
            msg.extra_headers = {'X-SES-CONFIGURATION-SET': config_set}
        mail.send(msg)
        logger.info('Magic link enviado a %s (config_set=%s)', to_email, config_set or 'none')
        return True
    except Exception as exc:
        logger.exception('Error enviando magic link a %s: %s', to_email, exc)
        raise


def dev_return_link_enabled() -> bool:
    return os.environ.get('AUTH_DEV_RETURN_LINK', '').lower() in ('1', 'true', 'yes')
