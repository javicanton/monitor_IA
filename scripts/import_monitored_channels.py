#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importa canales monitorizados desde CSV (local o S3) a monitored_channels.

Formato CSV: una columna por línea con el username (sin @). Líneas con # se ignoran.
Opcionalmente columnas: username,title,discontinued,status

Uso:
  python scripts/import_monitored_channels.py
  python scripts/import_monitored_channels.py --path telegram_channels.csv
  python scripts/import_monitored_channels.py --s3-key telegram_channels.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: Definir DATABASE_URL")
    sys.exit(1)

from flask import Flask
from sqlalchemy import text

from channel_graph import normalize_username
from config import Config
from models import MonitoredChannel, db


def _parse_bool(value) -> bool:
    if value is None or value == "":
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "si", "sí", "error")


def _load_rows_from_csv(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not row[0].strip() or row[0].strip().startswith("#"):
                continue
            if len(row) == 1:
                username = normalize_username(row[0])
                if username:
                    rows.append({
                        "username": username,
                        "title": username,
                        "discontinued": False,
                        "status": "active",
                        "_from_extended_csv": False,
                    })
            else:
                username = normalize_username(row[0])
                if not username:
                    continue
                title = (row[1] if len(row) > 1 else username) or username
                discontinued = _parse_bool(row[2]) if len(row) > 2 else False
                status = (row[3] if len(row) > 3 else ("error" if discontinued else "active")).strip().lower()
                rows.append(
                    {
                        "username": username,
                        "title": title,
                        "discontinued": discontinued,
                        "status": status if status in ("active", "error", "disabled") else "active",
                        "_from_extended_csv": True,
                    }
                )
    return rows


def _load_rows_from_s3(s3_key: str) -> list[dict]:
    from s3_client import get_s3_client

    content = get_s3_client().get_file_content(s3_key)
    rows = []
    reader = csv.reader(io.StringIO(content))
    for row in reader:
        if not row or not row[0].strip() or row[0].strip().startswith("#"):
            continue
        username = normalize_username(row[0])
        if username:
            rows.append({
                "username": username,
                "title": username,
                "discontinued": False,
                "status": "active",
                "_from_extended_csv": False,
            })
    return rows


def upsert_monitored(rows: list[dict], preserve_errors: bool = True) -> dict:
    inserted = updated = preserved = 0
    now = datetime.utcnow()
    for item in rows:
        username = item["username"]
        row = MonitoredChannel.query.filter_by(username=username).first()
        if row:
            row.title = item.get("title") or row.title or username
            # CSV simple (solo username): no reactivar canales ya marcados como error/descontinuados
            if (
                preserve_errors
                and row.discontinued
                and not item.get("_from_extended_csv")
            ):
                row.updated_at = now
                preserved += 1
                updated += 1
                continue
            row.discontinued = bool(item.get("discontinued", False))
            row.status = item.get("status") or ("error" if row.discontinued else "active")
            row.updated_at = now
            updated += 1
        else:
            discontinued = bool(item.get("discontinued", False))
            db.session.add(
                MonitoredChannel(
                    username=username,
                    title=item.get("title") or username,
                    status=item.get("status") or ("error" if discontinued else "active"),
                    discontinued=discontinued,
                    source="csv_import",
                )
            )
            inserted += 1
    db.session.commit()
    return {"inserted": inserted, "updated": updated, "preserved": preserved, "total": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Importar canales monitorizados a PostgreSQL")
    parser.add_argument("--path", help="Ruta local al CSV")
    parser.add_argument("--s3-key", default="telegram_channels.csv", help="Key S3 del CSV")
    parser.add_argument(
        "--reactivate-errors",
        action="store_true",
        help="Reactivar canales descontinuados al importar CSV simple (por defecto se conservan)",
    )
    args = parser.parse_args()

    if args.path:
        if not os.path.exists(args.path):
            print(f"ERROR: No existe {args.path}")
            sys.exit(1)
        rows = _load_rows_from_csv(args.path)
    else:
        try:
            rows = _load_rows_from_s3(args.s3_key)
        except Exception as exc:
            local = os.path.join(os.path.dirname(__file__), "..", "backend", "telegram_channels.csv")
            if os.path.exists(local):
                rows = _load_rows_from_csv(local)
            else:
                print(f"ERROR al cargar desde S3: {exc}")
                sys.exit(1)

    if not rows:
        print("No hay canales para importar.")
        sys.exit(0)

    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        stats = upsert_monitored(rows, preserve_errors=not args.reactivate_errors)
        count = MonitoredChannel.query.count()
        active = MonitoredChannel.query.filter_by(status="active", discontinued=False).count()
        discontinued = MonitoredChannel.query.filter_by(discontinued=True).count()
        print(
            f"Importados: {stats['inserted']} nuevos, {stats['updated']} actualizados"
            + (f", {stats['preserved']} descontinuados conservados" if stats.get("preserved") else "")
        )
        print(f"Total monitored_channels: {count} ({active} activos, {discontinued} descontinuados)")


if __name__ == "__main__":
    main()
