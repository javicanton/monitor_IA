#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de ingesta: carga dataset Telegram (CSV / JSON / Parquet) en PostgreSQL.
Uso:
  export DATABASE_URL=postgresql://user:pass@host:5432/dbname
  python scripts/init_postgres.py
  python scripts/import_dataset.py [--path telegram_messages.csv] [--batch-size 500]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("DATABASE_URL"):
    print("ERROR: Definir DATABASE_URL (ej: postgresql://user:pass@localhost:5432/monitor_ia)")
    sys.exit(1)

from models import Channel, Message, MessageTopic, db
from pg_upsert import clear_channel_cache, create_app, upsert_dataframe


def load_dataframe(path: str) -> pd.DataFrame:
    path_lower = path.lower()
    if path_lower.endswith(".parquet"):
        return pd.read_parquet(path)
    if path_lower.endswith(".csv"):
        return pd.read_csv(path, low_memory=False)
    if path_lower.endswith(".json"):
        import json

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        msgs = data.get("messages", data) if isinstance(data, dict) else data
        return pd.DataFrame(msgs)
    raise ValueError(f"Formato no soportado: {path}")


def run_import(path: str, batch_size: int = 500, clear_first: bool = False) -> None:
    app = create_app()
    with app.app_context():
        if clear_first:
            print("Eliminando tablas de mensajes/canales...")
            MessageTopic.query.delete()
            Message.query.delete()
            Channel.query.delete()
            db.session.commit()
            clear_channel_cache()

        print(f"Leyendo dataset: {path}")
        df = load_dataframe(path)
        if df.empty:
            print("Dataset vacío.")
            return

        stats = upsert_dataframe(df, batch_size=batch_size, preserve_labels=True)
        print(
            f"Listo: {stats['channels']} canales, "
            f"{stats['inserted']} nuevos, {stats['updated']} actualizados."
        )


def main():
    parser = argparse.ArgumentParser(description="Importar dataset Telegram a PostgreSQL")
    parser.add_argument("--path", "-p", default="telegram_messages.csv", help="Ruta a CSV, JSON o Parquet")
    parser.add_argument("--batch-size", "-b", type=int, default=500, help="Tamaño del lote")
    parser.add_argument("--clear", action="store_true", help="Vaciar tablas antes de importar")
    args = parser.parse_args()
    run_import(args.path, batch_size=args.batch_size, clear_first=args.clear)


if __name__ == "__main__":
    main()
