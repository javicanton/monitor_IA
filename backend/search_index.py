# -*- coding: utf-8 -*-
"""
Índice de búsqueda full-text con SQLite FTS5 para mensajes.
Escalable con datasets grandes; el índice se mantiene en disco y se actualiza
cuando el dataset cambia.
"""
import json
import os
import sqlite3
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Base del backend; el índice vive en instance/telegram_search.db
_BASEDIR = os.path.abspath(os.path.dirname(__file__))
_INSTANCE_DIR = os.path.join(_BASEDIR, 'instance')
FTS_DB_PATH = os.path.join(_INSTANCE_DIR, 'telegram_search.db')

FTS_TABLE = 'messages_fts'
META_TABLE = 'search_meta'
# Tamaño del batch para inserts (mejor rendimiento en datasets grandes)
INSERT_BATCH_SIZE = 5000


def _ensure_instance_dir():
    os.makedirs(_INSTANCE_DIR, exist_ok=True)


def _get_connection() -> sqlite3.Connection:
    _ensure_instance_dir()
    conn = sqlite3.connect(FTS_DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def _ensure_fts_table(conn: sqlite3.Connection) -> None:
    """Crea la tabla virtual FTS5 si no existe."""
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
            message_id UNINDEXED,
            message_text,
            title,
            tokenize='unicode61'
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {META_TABLE} (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()


def _get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute(f"SELECT value FROM {META_TABLE} WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        f"INSERT INTO {META_TABLE}(key, value) VALUES(?, ?) "
        f"ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def _escape_fts_query(raw: str) -> str:
    """Escapa la query para FTS5: comillas y caracteres especiales."""
    if not raw:
        return ''
    # FTS5: las comillas dobles delimitan frases; escapamos
    s = (raw or '').replace('"', ' ').strip()
    # Eliminar caracteres que puedan romper la sintaxis de MATCH
    return ' '.join(s.split())


def rebuild_index_from_dataframe(df) -> int:
    """
    Reconstruye el índice FTS desde un DataFrame.
    El DataFrame debe tener columnas 'Message ID', 'Message Text' y opcionalmente 'Title'.
    Devuelve el número de filas indexadas.
    """
    import pandas as pd
    if df is None or df.empty:
        return 0
    required = ['Message ID', 'Message Text']
    for col in required:
        if col not in df.columns:
            logger.warning("search_index: DataFrame sin columna '%s', no se indexa", col)
            return 0

    conn = _get_connection()
    try:
        _ensure_fts_table(conn)
        conn.execute(f'DELETE FROM {FTS_TABLE}')
        conn.commit()

        df = df.copy()
        df['Message Text'] = df['Message Text'].astype(str).fillna('')
        df['Title'] = df['Title'].astype(str).fillna('') if 'Title' in df.columns else ''

        def _safe_message_id(val):
            """Acepta int, float o string numérico (p. ej. desde JSON)."""
            if pd.isna(val):
                return None
            try:
                return int(float(val))
            except (TypeError, ValueError):
                return None

        total = 0
        for start in range(0, len(df), INSERT_BATCH_SIZE):
            batch = df.iloc[start:start + INSERT_BATCH_SIZE]
            rows = []
            for _, row in batch.iterrows():
                mid = _safe_message_id(row.get('Message ID'))
                if mid is None:
                    continue
                rows.append((
                    mid,
                    (row['Message Text'] or '')[:1_000_000],
                    (row['Title'] or '')[:10_000]
                ))
            conn.executemany(
                f'INSERT INTO {FTS_TABLE}(message_id, message_text, title) VALUES (?, ?, ?)',
                rows
            )
            total += len(rows)
        conn.commit()
        logger.info("search_index: índice reconstruido con %d mensajes", total)
        return total
    finally:
        conn.close()


def ensure_index_synced_from_parquet(parquet_path: str, fingerprint: str = "") -> bool:
    """
    Reconstruye el índice desde Parquet si el fingerprint del dataset ha cambiado.
    """
    if not parquet_path or not os.path.exists(parquet_path):
        return False

    conn = _get_connection()
    try:
        _ensure_fts_table(conn)
        current_fingerprint = _get_meta(conn, "dataset_fingerprint")
    finally:
        conn.close()

    if current_fingerprint == fingerprint and get_indexed_count() > 0:
        return True

    import duckdb

    duck = duckdb.connect(database=":memory:")
    try:
        quoted = parquet_path.replace("\\", "\\\\").replace("'", "''")
        df = duck.execute(
            f"SELECT cast(\"Message ID\" as BIGINT) as \"Message ID\", "
            f"coalesce(\"Message Text\", '') as \"Message Text\", "
            f"coalesce(\"Title\", '') as \"Title\" "
            f"FROM read_parquet('{quoted}')"
        ).fetchdf()
    finally:
        duck.close()

    total = rebuild_index_from_dataframe(df)
    conn = _get_connection()
    try:
        _ensure_fts_table(conn)
        payload = json.dumps({"fingerprint": fingerprint, "rows": total}, ensure_ascii=True)
        _set_meta(conn, "dataset_fingerprint", fingerprint)
        _set_meta(conn, "dataset_info", payload)
    finally:
        conn.close()
    return True


def get_indexed_count() -> int:
    """Devuelve el número de filas en el índice FTS."""
    conn = _get_connection()
    try:
        r = conn.execute(f'SELECT COUNT(*) FROM {FTS_TABLE}').fetchone()
        return r[0] if r else 0
    finally:
        conn.close()


def search_message_ids(query: str) -> Optional[List[int]]:
    """
    Busca en el índice FTS y devuelve la lista de Message ID que coinciden.
    Si la query está vacía o hay error, devuelve None (significa: no filtrar por búsqueda).
    """
    q = _escape_fts_query(query)
    if not q:
        return None

    conn = _get_connection()
    try:
        _ensure_fts_table(conn)
        # FTS5 MATCH: admite AND, OR, NOT (ej: "clima AND aemet"); espacio = AND implícito
        try:
            cur = conn.execute(
                f'SELECT message_id FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ?',
                (q,)
            )
            ids = [row[0] for row in cur.fetchall()]
            if not ids and q and " " not in q and " AND " not in q.upper():
                try:
                    cur = conn.execute(
                        f'SELECT message_id FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ?',
                        (f"{q}*",),
                    )
                    ids = [row[0] for row in cur.fetchall()]
                except sqlite3.OperationalError:
                    pass
            logger.info("search_index: búsqueda '%s' -> %d resultados", q[:50], len(ids))
            return ids
        except sqlite3.OperationalError as e:
            if 'syntax error' in str(e).lower() or 'malformed' in str(e).lower():
                logger.warning("search_index: query inválida '%s', %s", q[:50], e)
                return []
            raise
    finally:
        conn.close()


def ensure_index_synced(df) -> bool:
    """
    Si el índice está vacío o desactualizado (menos filas que el DataFrame),
    lo reconstruye desde el DataFrame. Devuelve True si el índice está listo para buscar.
    """
    if df is None or df.empty:
        return True
    current_count = get_indexed_count()
    if current_count == 0 or current_count < len(df):
        rebuild_index_from_dataframe(df)
    return True
