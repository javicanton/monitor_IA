"""Lista de correos autorizados a acceder a la aplicación."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_FILE = Path(__file__).resolve().parent.parent / 'allowed_emails.txt'


def _normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def _parse_line(line: str) -> tuple[str, str] | None:
    """Parsea 'email' o 'email role'. Ignora vacíos y comentarios."""
    raw = line.split('#', 1)[0].strip()
    if not raw:
        return None
    parts = raw.split()
    email = _normalize_email(parts[0])
    if not email or '@' not in email:
        return None
    role = parts[1].strip().lower() if len(parts) > 1 else 'user'
    if role not in ('user', 'admin'):
        role = 'user'
    return email, role


def _entries_from_env() -> dict[str, str]:
    raw = os.environ.get('ALLOWED_EMAILS', '')
    if not raw.strip():
        return {}
    entries: dict[str, str] = {}
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        if ':' in item:
            email_part, role_part = item.rsplit(':', 1)
            parsed = _parse_line(f'{email_part} {role_part}')
        else:
            parsed = _parse_line(item)
        if parsed:
            entries[parsed[0]] = parsed[1]
    return entries


def _entries_from_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    entries: dict[str, str] = {}
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            parsed = _parse_line(line)
            if parsed:
                entries[parsed[0]] = parsed[1]
    except OSError as exc:
        logger.warning('No se pudo leer allowlist %s: %s', path, exc)
    return entries


@lru_cache(maxsize=1)
def get_allowlist() -> dict[str, str]:
    """
    Devuelve {email_normalizado: role}.

    Prioridad:
    1. Variable ALLOWED_EMAILS (coma-separada; opcional email:role)
    2. Archivo allowed_emails.txt en backend/
    """
    env_entries = _entries_from_env()
    if env_entries:
        logger.info('Allowlist cargada desde ALLOWED_EMAILS (%d correos)', len(env_entries))
        return env_entries

    file_path = Path(os.environ.get('ALLOWED_EMAILS_FILE', str(_DEFAULT_FILE)))
    file_entries = _entries_from_file(file_path)
    if file_entries:
        logger.info('Allowlist cargada desde %s (%d correos)', file_path, len(file_entries))
        return file_entries

    logger.warning(
        'Allowlist vacía: define ALLOWED_EMAILS o crea %s',
        _DEFAULT_FILE,
    )
    return {}


def clear_allowlist_cache() -> None:
    get_allowlist.cache_clear()


def is_email_allowed(email: str) -> bool:
    return _normalize_email(email) in get_allowlist()


def get_role_for_email(email: str) -> str:
    return get_allowlist().get(_normalize_email(email), 'user')
