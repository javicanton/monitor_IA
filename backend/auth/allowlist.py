"""Lista de correos autorizados a acceder a la aplicación."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_FILE = Path(__file__).resolve().parent.parent / 'allowed_emails.txt'

# Caché en memoria; se invalida si cambia el archivo o ALLOWED_EMAILS
_cache: dict[str, str] | None = None
_cache_mtime: float | None = None
_cache_env_key: str | None = None


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


def allowlist_file_path() -> Path:
    return Path(os.environ.get('ALLOWED_EMAILS_FILE', str(_DEFAULT_FILE)))


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


def _file_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime if path.is_file() else None
    except OSError:
        return None


def get_allowlist() -> dict[str, str]:
    """
    Devuelve {email_normalizado: role}.

    Fuentes (se fusionan):
    1. Variable ALLOWED_EMAILS (coma-separada; opcional email:role)
    2. Archivo allowed_emails.txt en backend/ (o ALLOWED_EMAILS_FILE)

    Si un email está en ambas, gana el archivo (permite invitaciones admin
    sin tocar el .env).
    """
    global _cache, _cache_mtime, _cache_env_key

    path = allowlist_file_path()
    mtime = _file_mtime(path)
    env_raw = os.environ.get('ALLOWED_EMAILS', '')

    if (
        _cache is not None
        and _cache_mtime == mtime
        and _cache_env_key == env_raw
    ):
        return _cache

    entries = dict(_entries_from_env())
    file_entries = _entries_from_file(path)
    entries.update(file_entries)

    if entries:
        logger.info(
            'Allowlist cargada: %d correos (env=%d, file=%d, path=%s)',
            len(entries),
            len(_entries_from_env()),
            len(file_entries),
            path,
        )
    else:
        logger.warning(
            'Allowlist vacía: define ALLOWED_EMAILS o crea %s',
            path,
        )

    _cache = entries
    _cache_mtime = mtime
    _cache_env_key = env_raw
    return entries


def clear_allowlist_cache() -> None:
    global _cache, _cache_mtime, _cache_env_key
    _cache = None
    _cache_mtime = None
    _cache_env_key = None


def is_email_allowed(email: str) -> bool:
    return _normalize_email(email) in get_allowlist()


def get_role_for_email(email: str) -> str:
    return get_allowlist().get(_normalize_email(email), 'user')


def add_email_to_allowlist(email: str, role: str = 'user') -> dict:
    """
    Añade (o actualiza) un email en el archivo de allowlist.

    - Persiste en disco (ALLOWED_EMAILS_FILE / allowed_emails.txt)
    - Invalida la caché
    - Si ya existía con el mismo rol, no reescribe el archivo

    Devuelve: {email, role, created: bool, path: str}
    """
    email = _normalize_email(email)
    if not email or '@' not in email:
        raise ValueError('Email no válido')

    role = (role or 'user').strip().lower()
    if role not in ('user', 'admin'):
        role = 'user'

    current = get_allowlist()
    already = email in current and current[email] == role
    if already:
        return {
            'email': email,
            'role': role,
            'created': False,
            'path': str(allowlist_file_path()),
        }

    path = allowlist_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Si ya está en el archivo con otro rol, reescribir líneas; si no, append
    file_entries = _entries_from_file(path)
    if email in file_entries:
        lines_out: list[str] = []
        try:
            for line in path.read_text(encoding='utf-8').splitlines():
                parsed = _parse_line(line)
                if parsed and parsed[0] == email:
                    lines_out.append(f'{email} {role}' if role != 'user' else email)
                else:
                    lines_out.append(line)
            path.write_text('\n'.join(lines_out) + '\n', encoding='utf-8')
        except OSError as exc:
            logger.error('No se pudo actualizar allowlist %s: %s', path, exc)
            raise
    else:
        try:
            needs_newline = False
            if path.is_file() and path.stat().st_size > 0:
                with path.open('rb') as rb:
                    rb.seek(-1, 2)
                    needs_newline = rb.read(1) != b'\n'
            line = f'{email} {role}' if role != 'user' else email
            with path.open('a', encoding='utf-8') as fh:
                if needs_newline:
                    fh.write('\n')
                fh.write(line + '\n')
        except OSError as exc:
            logger.error('No se pudo escribir allowlist %s: %s', path, exc)
            raise

    clear_allowlist_cache()
    logger.info('Allowlist: %s → %s (%s)', email, role, path)
    return {
        'email': email,
        'role': role,
        'created': email not in current,
        'path': str(path),
    }
