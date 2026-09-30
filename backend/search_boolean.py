# -*- coding: utf-8 -*-
"""Parser y compilación de búsquedas booleanas (AND, OR, NOT)."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from sqlalchemy import and_, not_, or_

BooleanGroup = List[Tuple[str, str]]  # (op, term) con op en AND | NOT
BooleanQuery = List[BooleanGroup]


def has_boolean_operators(query: str) -> bool:
    return bool(re.search(r"\b(AND|OR|NOT)\b", query or "", re.IGNORECASE))


def parse_boolean_search(query: str) -> Optional[BooleanQuery]:
    """
    Parsea AND, OR, NOT (sin distinguir mayúsculas).
    Devuelve grupos unidos por OR; dentro de cada grupo los términos se unen con AND.
  """
    raw = (query or "").strip()
    if not raw:
        return None

    parts = re.split(r"\s+(AND|OR|NOT)\s+", raw, flags=re.IGNORECASE)
    tokens: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.upper() in ("AND", "OR", "NOT"):
            tokens.append(part.upper())
        else:
            tokens.append(part)

    if not tokens:
        return None

    or_groups: BooleanQuery = []
    current_and: BooleanGroup = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "OR":
            if current_and:
                or_groups.append(current_and)
                current_and = []
            i += 1
            continue
        if token == "NOT":
            i += 1
            if i < len(tokens) and tokens[i] not in ("AND", "OR", "NOT"):
                current_and.append(("NOT", tokens[i]))
                i += 1
            continue
        if token == "AND":
            i += 1
            continue
        current_and.append(("AND", token))
        i += 1
    if current_and:
        or_groups.append(current_and)
    return or_groups if or_groups else None


def _sanitize_tsquery_term(term: str) -> Optional[str]:
    words = []
    for word in (term or "").split():
        cleaned = re.sub(r"[&|!:()<>'\"\\]", "", word).strip()
        if cleaned:
            words.append(cleaned)
    if not words:
        return None
    if len(words) == 1:
        return words[0]
    return " & ".join(words)


def parsed_to_tsquery(parsed: BooleanQuery) -> Optional[str]:
    """Convierte la consulta parseada a sintaxis to_tsquery (&, |, !)."""
    or_parts: List[str] = []
    for group in parsed:
        and_parts: List[str] = []
        for op, term in group:
            sanitized = _sanitize_tsquery_term(term)
            if not sanitized:
                continue
            if op == "NOT":
                and_parts.append(f"!({sanitized})")
            else:
                and_parts.append(f"({sanitized})")
        if not and_parts:
            continue
        or_parts.append(and_parts[0] if len(and_parts) == 1 else " & ".join(and_parts))
    if not or_parts:
        return None
    return or_parts[0] if len(or_parts) == 1 else " | ".join(or_parts)


def prepare_fts5_match_query(query: str) -> str:
    """Prepara query para SQLite FTS5 MATCH (AND/OR/NOT en mayúsculas)."""
    if not has_boolean_operators(query):
        return " ".join((query or "").replace('"', " ").split())
    tokens = query.split()
    out: List[str] = []
    for token in tokens:
        upper = token.upper()
        if upper in ("AND", "OR", "NOT"):
            out.append(upper)
        else:
            out.append(token.replace('"', " "))
    return " ".join(out)


def apply_boolean_sqlalchemy_filter(q, parsed: BooleanQuery, text_field, url_field):
    """Aplica la consulta booleana con ILIKE sobre texto y URL (fallback)."""

    def term_expr(term: str):
        pattern = f"%{term}%"
        return or_(text_field.ilike(pattern), url_field.ilike(pattern))

    or_exprs = []
    for group in parsed:
        and_exprs = []
        for op, term in group:
            if not term:
                continue
            expr = term_expr(term)
            and_exprs.append(not_(expr) if op == "NOT" else expr)
        if and_exprs:
            or_exprs.append(and_(*and_exprs) if len(and_exprs) > 1 else and_exprs[0])
    if not or_exprs:
        return q
    return q.filter(or_(*or_exprs) if len(or_exprs) > 1 else or_exprs[0])
