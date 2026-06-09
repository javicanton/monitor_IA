#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inicializa PostgreSQL: tablas SQLAlchemy + índices para consultas y búsqueda.
Uso:
  export DATABASE_URL=postgresql://user:pass@host:5432/monitor_ia?sslmode=require
  python scripts/init_postgres.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: Definir DATABASE_URL")
    sys.exit(1)

from flask import Flask
from sqlalchemy import text

from config import Config
from models import Channel, Message, MessageTopic, User, db

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages (message_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages (channel_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_date_sent ON messages (date_sent)",
    "CREATE INDEX IF NOT EXISTS idx_messages_score_desc ON messages (score DESC NULLS LAST)",
    "CREATE INDEX IF NOT EXISTS idx_messages_views_desc ON messages (views DESC NULLS LAST)",
    "CREATE INDEX IF NOT EXISTS idx_messages_label ON messages (label)",
    "CREATE INDEX IF NOT EXISTS idx_channels_title_lower ON channels (lower(title))",
    "CREATE INDEX IF NOT EXISTS idx_message_topics_topic_id ON message_topics (topic_id)",
    """
    CREATE INDEX IF NOT EXISTS idx_messages_fts_spanish
    ON messages USING gin (to_tsvector('spanish', coalesce(message_text, '')))
    """,
]


def main() -> None:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        print("Creando tablas (channels, messages, message_topics, user)...")
        db.create_all()
        for statement in INDEX_STATEMENTS:
            db.session.execute(text(statement))
        db.session.commit()
        counts = {
            "channels": Channel.query.count(),
            "messages": Message.query.count(),
            "message_topics": MessageTopic.query.count(),
            "users": User.query.count(),
        }
        print("Listo. Filas actuales:", counts)
        print("Siguiente paso: python scripts/import_dataset.py --path <dataset>")


if __name__ == "__main__":
    main()
