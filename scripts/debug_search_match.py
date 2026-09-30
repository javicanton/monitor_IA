#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnóstico: por qué un mensaje aparece en una búsqueda de texto."""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _snippet(text: str, term: str, width: int = 60) -> str:
    if not text:
        return ""
    match = re.search(re.escape(term), text, re.IGNORECASE)
    if not match:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, match.start() - 20)
    end = min(len(text), match.end() + 20)
    return "…" + text[start:end] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico de coincidencias de búsqueda")
    parser.add_argument("query", help="Término buscado, p. ej. clima")
    parser.add_argument("--url", action="append", default=[], help="URL del mensaje (repetible)")
    parser.add_argument("--message-id", type=int, action="append", default=[], help="Message ID Telegram")
    parser.add_argument("--channel", action="append", default=[], help="Username del canal")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL no definido", file=sys.stderr)
        return 1

    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    term = args.query.strip()
    patterns = []
    params: dict = {"q": term, "like": f"%{term}%"}

    if args.url:
        for i, url in enumerate(args.url):
            key = f"url{i}"
            patterns.append(f"m.url ILIKE :{key}")
            params[key] = f"%{url.split('/')[-1]}%"
    if args.message_id and args.channel:
        for i, (mid, ch) in enumerate(zip(args.message_id, args.channel)):
            patterns.append(f"(m.message_id = :mid{i} AND c.username = :ch{i})")
            params[f"mid{i}"] = mid
            params[f"ch{i}"] = ch.lstrip("@")
    elif args.message_id:
        for i, mid in enumerate(args.message_id):
            patterns.append(f"m.message_id = :mid{i}")
            params[f"mid{i}"] = mid

    where = " OR ".join(patterns) if patterns else "TRUE"

    sql = text(
        f"""
        SELECT m.id AS row_id, m.message_id, c.username, c.title AS channel_title,
               m.url,
               left(m.message_text, 400) AS text_preview,
               m.message_text ILIKE :like AS ilike_text,
               m.url ILIKE :like AS ilike_url,
               to_tsvector('spanish', coalesce(m.message_text,'') || ' ' || coalesce(m.url,''))
                 @@ plainto_tsquery('spanish', :q) AS fts_match
        FROM messages m
        JOIN channels c ON c.id = m.channel_id
        WHERE {where}
        ORDER BY m.message_id, c.username
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        if not rows:
            print("No se encontraron mensajes con esos criterios.")
            return 0

        fts_hits = conn.execute(
            text(
                """
                SELECT m.id, m.message_id, c.username
                FROM messages m
                JOIN channels c ON c.id = m.channel_id
                WHERE to_tsvector('spanish', coalesce(m.message_text,'') || ' ' || coalesce(m.url,''))
                      @@ plainto_tsquery('spanish', :q)
                """
            ),
            {"q": term},
        ).fetchall()
        fts_keys = {(r.message_id, r.username) for r in fts_hits}
        print(f"Búsqueda FTS «{term}»: {len(fts_keys)} pares (message_id, canal) únicos\n")

        for row in rows:
            d = dict(row._mapping)
            key = (d["message_id"], d["username"])
            print("=" * 72)
            print(f"Canal: @{d['username']} ({d['channel_title']})")
            print(f"Message ID Telegram: {d['message_id']}  |  Fila BD: {d['row_id']}")
            print(f"URL: {d['url']}")
            print(f"ILIKE texto: {d['ilike_text']}  |  ILIKE url: {d['ilike_url']}  |  FTS: {d['fts_match']}")
            if d["ilike_text"]:
                full = conn.execute(
                    text("SELECT message_text FROM messages WHERE id = :id"),
                    {"id": d["row_id"]},
                ).scalar()
                print(f"Fragmento con «{term}» en texto: {_snippet(full or '', term)}")
            elif d["fts_match"] and not d["ilike_text"] and not d["ilike_url"]:
                print("Coincide por FTS (stemming español), sin substring literal «{term}».")
            elif key in fts_keys and not d["fts_match"]:
                print(
                    "⚠️  Este mensaje NO coincide en FTS, pero comparte message_id con otro canal "
                    "que sí (bug antiguo: filtrar solo por message_id)."
                )
            else:
                print(f"Vista previa texto: {d['text_preview']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
