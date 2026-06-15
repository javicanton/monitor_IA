import importlib.util
import json
import logging
import os
import tempfile
import subprocess
import sys
from datetime import datetime, timedelta

import pandas as pd
from botocore.exceptions import ClientError

from config import Config
from s3_client import get_s3_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _safe_datetime(value):
    if not value:
        return None
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def _message_date_column(df):
    for col in ["Date Sent", "Date", "date_sent"]:
        if col in df.columns:
            return col
    return None


def _filter_by_days(df, days_window):
    if not days_window or days_window <= 0 or df.empty:
        return df
    date_col = _message_date_column(df)
    if not date_col:
        logger.warning("TOPICS_DAYS_WINDOW activo pero no hay columna de fecha; sin filtrar")
        return df
    cutoff = datetime.utcnow() - timedelta(days=days_window)
    dates = pd.to_datetime(df[date_col], errors="coerce", utc=True)
    cutoff_ts = pd.Timestamp(cutoff, tz="UTC")
    filtered = df[dates >= cutoff_ts]
    logger.info(
        "Ventana de %d días: %d -> %d mensajes",
        days_window,
        len(df),
        len(filtered),
    )
    return filtered


def _load_messages_from_postgres(days_window=None):
    from sqlalchemy import func

    from models import Message
    from pg_upsert import create_app

    app = create_app()
    with app.app_context():
        from models import db

        date_expr = func.coalesce(Message.date_sent, Message.creation_date)
        q = db.session.query(
            Message.id.label("pg_id"),
            Message.message_id.label("telegram_id"),
            Message.message_text.label("message_text"),
            date_expr.label("date_sent"),
        ).filter(Message.message_text.isnot(None))

        if days_window and days_window > 0:
            cutoff = datetime.utcnow() - timedelta(days=days_window)
            q = q.filter(date_expr >= cutoff)

        rows = q.all()
        if not rows:
            return pd.DataFrame()

        records = []
        for row in rows:
            records.append(
                {
                    "_pg_id": row.pg_id,
                    "Message ID": row.telegram_id,
                    "Message Text": row.message_text,
                    "Date Sent": row.date_sent,
                }
            )
        return pd.DataFrame(records)


def _load_messages_df(s3_client):
    data = s3_client.load_json_from_s3(Config.TOPICS_SOURCE_KEY)
    messages = data.get("messages", data)
    df = pd.DataFrame(messages)
    return df


def _extract_text_column(df):
    candidates = [
        "Message Text",
        "message_text",
        "text",
        "message",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _prepare_docs(df):
    text_col = _extract_text_column(df)
    if not text_col:
        return pd.Series([], dtype=str), text_col

    series = df[text_col].fillna("").astype(str).str.strip()
    return series, text_col


def _load_state(s3_client):
    try:
        content = s3_client.get_file_content(Config.TOPICS_STATE_KEY)
        return json.loads(content)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            return {}
        raise
    except Exception:
        return {}


def _save_state(s3_client, state):
    payload = json.dumps(state, ensure_ascii=True)
    s3_client.s3_client.put_object(
        Bucket=Config.S3_BUCKET,
        Key=Config.TOPICS_STATE_KEY,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )


def _filter_new_messages(df, state):
    last_id = state.get("last_message_id")
    last_date_raw = state.get("last_message_date")
    last_date = _safe_datetime(last_date_raw)

    if "Message ID" in df.columns and last_id is not None:
        ids = pd.to_numeric(df["Message ID"], errors="coerce")
        return df[ids > float(last_id)]

    date_col = None
    for col in ["Date Sent", "Date"]:
        if col in df.columns:
            date_col = col
            break

    if date_col and last_date:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        return df[dates > last_date]

    return df


def _state_from_df(df):
    state = {"last_processed_at": datetime.utcnow().isoformat()}

    if "Message ID" in df.columns:
        ids = pd.to_numeric(df["Message ID"], errors="coerce")
        if not ids.dropna().empty:
            state["last_message_id"] = int(ids.max())

    for col in ["Date Sent", "Date"]:
        if col in df.columns:
            dates = pd.to_datetime(df[col], errors="coerce")
            if not dates.dropna().empty:
                state["last_message_date"] = dates.max().isoformat()
                break

    return state


def _model_exists(s3_client):
    try:
        files = s3_client.list_files(prefix=Config.TOPICS_S3_PREFIX)
        return Config.TOPICS_MODEL_KEY in files
    except Exception:
        return False


def _download_model(s3_client, local_path):
    s3_client.download_file(Config.TOPICS_MODEL_KEY, local_path)


def _upload_model(s3_client, local_path):
    s3_client.upload_file(local_path, Config.TOPICS_MODEL_KEY)


def _train_model_with_pytopicgram(docs, model_path):
    with tempfile.TemporaryDirectory() as tmpdir:
        input_csv = os.path.join(tmpdir, "messages.csv")
        df = pd.DataFrame({"message_text": docs})
        df.to_csv(input_csv, index=False)

        cmd = [
            sys.executable,
            "-m",
            "pytopicgram.extractor",
            "--file",
            input_csv,
            "--column",
            "message_text",
            "--output",
            model_path,
        ]

        if Config.TOPICS_NUM_TOPICS and Config.TOPICS_NUM_TOPICS > 0:
            cmd.extend(["--num_topics", str(Config.TOPICS_NUM_TOPICS)])

        if Config.TOPICS_OPENAI_KEY:
            cmd.extend(["--openai_key", Config.TOPICS_OPENAI_KEY])
            cmd.extend(["--n_docs_openai", str(Config.TOPICS_OPENAI_DOCS)])

        if Config.TOPICS_SAMPLE_RATIO and 0 < Config.TOPICS_SAMPLE_RATIO < 1:
            cmd.extend(["--sample_ratio", str(Config.TOPICS_SAMPLE_RATIO)])

        logger.info("Entrenando modelo con pytopicgram")
        subprocess.run(cmd, check=True)


def _load_topic_model(model_path):
    from bertopic import BERTopic
    return BERTopic.load(model_path)


def _get_topic_info(model):
    if hasattr(model, "get_topic_info"):
        info = model.get_topic_info()
        if isinstance(info, pd.DataFrame):
            return info.to_dict(orient="records")
        return info
    if hasattr(model, "get_topics"):
        topics = model.get_topics()
        if isinstance(topics, dict):
            return [
                {"topic_id": key, "terms": value}
                for key, value in topics.items()
            ]
    return []


def _assign_topics(model, docs):
    if not hasattr(model, "transform"):
        raise ValueError("El modelo no soporta transform()")
    topics, probs = model.transform(docs)
    return topics, probs


def _save_topics_metadata(s3_client, model):
    topics = _get_topic_info(model)
    payload = json.dumps({"topics": topics}, ensure_ascii=True)
    s3_client.s3_client.put_object(
        Bucket=Config.S3_BUCKET,
        Key=Config.TOPICS_META_KEY,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )


def _load_existing_assignments(s3_client):
    try:
        return s3_client.load_csv_from_s3(Config.TOPICS_ASSIGNMENTS_KEY)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            return pd.DataFrame()
        raise
    except Exception:
        return pd.DataFrame()


def _upload_assignments(s3_client, assignments_df):
    s3_client.upload_dataframe(assignments_df, Config.TOPICS_ASSIGNMENTS_KEY, format="csv")


def _save_assignments_to_postgres(target_df, topics):
    """Persiste asignaciones en message_topics (PostgreSQL)."""
    if "_pg_id" not in target_df.columns:
        logger.warning("Sin columna _pg_id; no se escriben topics en PostgreSQL")
        return 0

    from models import MessageTopic
    from pg_upsert import create_app

    app = create_app()
    written = 0
    with app.app_context():
        from models import db

        pg_ids = target_df["_pg_id"].tolist()
        MessageTopic.query.filter(MessageTopic.message_id.in_(pg_ids)).delete(
            synchronize_session=False
        )

        for pg_id, topic_id in zip(pg_ids, topics):
            try:
                topic_id = int(topic_id)
            except (TypeError, ValueError):
                continue
            if topic_id < 0:
                continue
            db.session.add(MessageTopic(message_id=int(pg_id), topic_id=topic_id))
            written += 1

        db.session.commit()
    logger.info("Asignaciones guardadas en PostgreSQL: %d filas", written)
    return written


def process_topics(days_window=None):
    if importlib.util.find_spec("pytopicgram") is None:
        logger.error("pytopicgram no disponible en este contenedor")
        return {"status": "error", "error": "pytopicgram_not_installed"}

    days_window = days_window if days_window is not None else Config.TOPICS_DAYS_WINDOW
    use_postgres = bool(os.environ.get("DATABASE_URL"))

    if use_postgres:
        logger.info("Cargando mensajes desde PostgreSQL (ventana: %s días)", days_window or "sin límite")
        df = _load_messages_from_postgres(days_window)
        s3_client = get_s3_client()
    else:
        s3_client = get_s3_client()
        df = _load_messages_df(s3_client)
        df = _filter_by_days(df, days_window)

    if df.empty:
        logger.info("No hay mensajes para procesar")
        return {"status": "empty"}

    docs_series, _ = _prepare_docs(df)
    df = df.assign(_topic_text=docs_series)
    df = df[df["_topic_text"].str.len() > 0]

    state = {} if Config.TOPICS_RESET_STATE else _load_state(s3_client)
    new_df = df if Config.TOPICS_RESET_STATE else _filter_new_messages(df, state)

    if new_df.empty:
        logger.info("No hay mensajes nuevos")
        return {"status": "no_new_messages"}

    model = None
    assign_full_dataset = False
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.pkl")
        if _model_exists(s3_client):
            try:
                _download_model(s3_client, model_path)
                model = _load_topic_model(model_path)
            except Exception as e:
                logger.warning(f"No se pudo cargar el modelo existente: {e}")
                model = None

        if model is None:
            _train_model_with_pytopicgram(df["_topic_text"].tolist(), model_path)
            model = _load_topic_model(model_path)
            _upload_model(s3_client, model_path)
            assign_full_dataset = True

        topics, probs = _assign_topics(model, new_df["_topic_text"].tolist())
        unassigned_ratio = (pd.Series(topics) == -1).mean() if len(topics) else 0

        if (
            len(new_df) >= Config.TOPICS_MIN_NEW_MESSAGES
            and unassigned_ratio >= Config.TOPICS_RETRAIN_THRESHOLD
        ):
            logger.info("Reentrenando modelo por alto ratio de no asignados")
            _train_model_with_pytopicgram(df["_topic_text"].tolist(), model_path)
            model = _load_topic_model(model_path)
            _upload_model(s3_client, model_path)
            assign_full_dataset = True

        if assign_full_dataset:
            topics, probs = _assign_topics(model, df["_topic_text"].tolist())
            target_df = df.copy()
        else:
            target_df = new_df.copy()

        if probs is None:
            probs = [None] * len(topics)

        assignments = pd.DataFrame(
            {
                "Message ID": target_df.get("Message ID", target_df.index).astype(str),
                "topic_id": pd.Series(topics).astype(int),
                "topic_prob": pd.Series(probs).astype(float),
            }
        )

        existing = _load_existing_assignments(s3_client)
        if not existing.empty and not assign_full_dataset:
            assignments = pd.concat([existing, assignments], ignore_index=True)

        assignments = assignments.drop_duplicates(subset=["Message ID"], keep="last")
        _upload_assignments(s3_client, assignments)
        if use_postgres:
            _save_assignments_to_postgres(target_df, topics)
        _save_topics_metadata(s3_client, model)
        _save_state(s3_client, _state_from_df(df))

    return {
        "status": "ok",
        "new_messages": int(len(new_df)),
        "retrained": bool(assign_full_dataset),
        "days_window": days_window or None,
        "postgres": use_postgres,
    }


if __name__ == "__main__":
    result = process_topics()
    logger.info(f"Resultado topics: {result}")
