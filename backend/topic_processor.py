import importlib.util
import json
import logging
import os
import tempfile
import subprocess
import sys
from datetime import datetime

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


def process_topics():
    if importlib.util.find_spec("pytopicgram") is None:
        logger.error("pytopicgram no disponible en este contenedor")
        return {"status": "error", "error": "pytopicgram_not_installed"}
    s3_client = get_s3_client()
    df = _load_messages_df(s3_client)
    if df.empty:
        logger.info("No hay mensajes para procesar")
        return {"status": "empty"}

    docs_series, _ = _prepare_docs(df)
    df = df.assign(_topic_text=docs_series)
    df = df[df["_topic_text"].str.len() > 0]

    state = _load_state(s3_client)
    new_df = _filter_new_messages(df, state)

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
        _save_topics_metadata(s3_client, model)
        _save_state(s3_client, _state_from_df(df))

    return {
        "status": "ok",
        "new_messages": int(len(new_df)),
        "retrained": bool(assign_full_dataset),
    }


if __name__ == "__main__":
    result = process_topics()
    logger.info(f"Resultado topics: {result}")
