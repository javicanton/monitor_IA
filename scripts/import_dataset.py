#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de ingesta: carga dataset Telegram (CSV / JSON / Parquet) en PostgreSQL.
Uso:
  export DATABASE_URL=postgresql://user:pass@host:5432/dbname
  python scripts/import_dataset.py [--path telegram_messages.csv] [--batch-size 2000]
No carga el dataset entero en memoria: procesa por lotes.
"""
from __future__ import annotations

import argparse
import os
import sys

# Asegurar que el backend esté en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: Definir DATABASE_URL (ej: postgresql://user:pass@localhost:5432/monitor_ia)")
    sys.exit(1)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

from flask import Flask
from models import db, Channel, Message, MessageTopic


def load_dataframe(path: str) -> pd.DataFrame:
    path_lower = path.lower()
    if path_lower.endswith(".parquet"):
        return pd.read_parquet(path)
    if path_lower.endswith(".csv"):
        return pd.read_csv(path, low_memory=False)
    if path_lower.endswith(".json"):
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        msgs = data.get("messages", data) if isinstance(data, dict) else data
        return pd.DataFrame(msgs)
    raise ValueError(f"Formato no soportado: {path}")


def run_import(path: str, batch_size: int = 2000, clear_first: bool = False) -> None:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        if clear_first:
            print("Eliminando tablas de mensajes/canales...")
            MessageTopic.query.delete()
            Message.query.delete()
            Channel.query.delete()
            db.session.commit()

        print(f"Leyendo dataset: {path}")
        df = load_dataframe(path)
        if df.empty:
            print("Dataset vacío.")
            return
        if "Username" not in df.columns or "Message ID" not in df.columns:
            print("El dataset debe tener columnas 'Username' y 'Message ID'.")
            return

        df["_username"] = df["Username"].fillna("").astype(str).str.strip().replace("", "Desconocido")
        df["_title"] = df["Title"].fillna("").astype(str).str.strip().replace("", "Desconocido") if "Title" in df.columns else df["_username"]

        channel_id_by_username = {}
        total = len(df)
        inserted = 0

        for start in range(0, total, batch_size):
            batch = df.iloc[start : start + batch_size]
            for _, row in batch.iterrows():
                username = row["_username"]
                title = row["_title"]
                if username not in channel_id_by_username:
                    ch = Channel.query.filter_by(username=username).first()
                    if not ch:
                        ch = Channel(username=username, title=title)
                        db.session.add(ch)
                        db.session.flush()
                    channel_id_by_username[username] = ch.id
                cid = channel_id_by_username[username]

                try:
                    message_id = int(pd.to_numeric(row["Message ID"], errors="coerce"))
                except (TypeError, ValueError):
                    continue
                if pd.isna(message_id):
                    continue

                def _dt(val):
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        return None
                    try:
                        t = pd.to_datetime(val)
                        if hasattr(t, "tz_localize") and t.tzinfo is not None:
                            t = t.tz_localize(None)
                        return t
                    except Exception:
                        return None

                date_sent = _dt(row.get("Date Sent"))
                creation_date = _dt(row.get("Creation Date"))
                edit_date = _dt(row.get("Edit Date"))
                views = int(pd.to_numeric(row.get("Views"), errors="coerce") or 0)
                forwards = int(pd.to_numeric(row.get("Forwards"), errors="coerce") or 0)
                replies = int(pd.to_numeric(row.get("Replies"), errors="coerce") or 0)
                score = float(pd.to_numeric(row.get("Score"), errors="coerce") or 0)
                label_val = row.get("Label")
                label = None
                if pd.notna(label_val):
                    try:
                        label = int(label_val)
                    except (TypeError, ValueError):
                        pass
                avg = row.get("Average Views")
                average_views = None
                if pd.notna(avg):
                    try:
                        average_views = float(avg)
                    except (TypeError, ValueError):
                        pass

                existing = Message.query.filter_by(message_id=message_id, channel_id=cid).first()
                if existing:
                    existing.message_text = str(row.get("Message Text", ""))[:500000] if pd.notna(row.get("Message Text")) else None
                    existing.date_sent = date_sent
                    existing.views = views
                    existing.forwards = forwards
                    existing.replies = replies
                    existing.url = str(row.get("URL", ""))[:2000] if pd.notna(row.get("URL")) else None
                    existing.embed = str(row.get("Embed", ""))[:50000] if pd.notna(row.get("Embed")) else None
                    existing.score = score
                    existing.label = label
                    existing.media_type = str(row.get("Media Type", ""))[:100] if pd.notna(row.get("Media Type")) else None
                    existing.creation_date = creation_date
                    existing.edit_date = edit_date
                    existing.average_views = average_views
                else:
                    msg = Message(
                        message_id=message_id,
                        channel_id=cid,
                        message_text=str(row.get("Message Text", ""))[:500000] if pd.notna(row.get("Message Text")) else None,
                        date_sent=date_sent,
                        views=views,
                        forwards=forwards,
                        replies=replies,
                        url=str(row.get("URL", ""))[:2000] if pd.notna(row.get("URL")) else None,
                        embed=str(row.get("Embed", ""))[:50000] if pd.notna(row.get("Embed")) else None,
                        score=score,
                        label=label,
                        media_type=str(row.get("Media Type", ""))[:100] if pd.notna(row.get("Media Type")) else None,
                        creation_date=creation_date,
                        edit_date=edit_date,
                        average_views=average_views,
                    )
                    db.session.add(msg)
                inserted += 1
            db.session.commit()
            print(f"  Procesadas {min(start + batch_size, total)} / {total} filas...")
        print(f"Listo: {len(channel_id_by_username)} canales, {inserted} mensajes.")


def main():
    parser = argparse.ArgumentParser(description="Importar dataset Telegram a PostgreSQL")
    parser.add_argument("--path", "-p", default="telegram_messages.csv", help="Ruta a CSV, JSON o Parquet")
    parser.add_argument("--batch-size", "-b", type=int, default=2000, help="Tamaño del lote")
    parser.add_argument("--clear", action="store_true", help="Vaciar tablas antes de importar")
    args = parser.parse_args()
    run_import(args.path, batch_size=args.batch_size, clear_first=args.clear)


if __name__ == "__main__":
    main()
