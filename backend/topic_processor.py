import importlib.util
import json
import logging
import os
import re
import tempfile
import subprocess
import sys
from datetime import datetime, timedelta
from hashlib import md5

import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import func, or_, text

from config import Config
from s3_client import get_s3_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_TG_LINK_RE = re.compile(r"(?:t\.me|telegram\.me)/\S+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
# Ruido típico de captions / reenvíos (inglés)
_COPYRIGHT_BOILERPLATE_RE = re.compile(
    r"copyright\s+infringement|"
    r"displayed\s+on\s+(?:this\s+)?device|"
    r"couldn'?t\s+be\s+displayed|"
    r"this\s+content\s+isn'?t\s+available|"
    r"media\s+could\s+not\s+be\s+loaded|"
    r"galaxy\s+ai|"
    r"samsung\s+galaxy",
    re.IGNORECASE,
)
# CTAs de canal Telegram (español/inglés) que monopolizan clusters
_CHANNEL_CTA_RE = re.compile(
    r"\búnete\b|"
    r"\bunete\b|"
    r"\bsuscr[ií]bete\b|"
    r"\benlace\s+al\s+canal\b|"
    r"\bcanal\s+de\s+telegram\b|"
    r"\btelegram\s+channel\b|"
    r"\bjoin\s+(?:our|the)\s+channel\b|"
    r"\bfollow\s+(?:us|our\s+channel)\b|"
    r"\bs[ií]guenos\b|"
    r"\bs[ií]gueme\b|"
    r"\bcompart[ea]\b|"
    r"\binvita\s+a\s+(?:tus\s+)?amig",
    re.IGNORECASE,
)
# Promo corto típico: "si … españa … telegram/canal" (sin decir únete)
_PROMO_CHANNEL_RE = re.compile(r"\btelegram\b|\bcanal\b", re.IGNORECASE)
_PROMO_HOOK_RE = re.compile(
    r"\bespa[nñ]a\b|\benlace\b|\btrend\b|\bstellar\b|\bsemilla\b|"
    r"\bwhatsapp\b|\bgroup\b|\bgrupo\b",
    re.IGNORECASE,
)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)
_NON_WORD_RE = re.compile(r"[^a-z0-9áéíóúüñ\s]+", re.IGNORECASE)
# Tipos de media que suelen ser “solo archivo” sin narrativa si el caption es vacío/ruido
_MEDIA_ONLY_TYPES = {
    "photo",
    "video",
    "gif",
    "sticker",
    "voice",
    "audio",
    "document",
    "webpage",
}


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


def _seed_to_float(seed):
    digest = md5(str(seed or "monitoria").encode("utf-8")).hexdigest()
    # setseed espera float en [-1, 1]
    return (int(digest[:8], 16) / 0xFFFFFFFF) * 2 - 1


def _rows_to_dataframe(rows):
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
                "Media Type": getattr(row, "media_type", None),
            }
        )
    return pd.DataFrame(records)


def clean_topic_text(raw):
    """Quita URLs / enlaces t.me y normaliza espacios. Devuelve texto residual."""
    if raw is None:
        return ""
    text_val = str(raw).strip()
    if not text_val:
        return ""
    text_val = _URL_RE.sub(" ", text_val)
    text_val = _TG_LINK_RE.sub(" ", text_val)
    text_val = _WHITESPACE_RE.sub(" ", text_val).strip()
    return text_val


def is_boilerplate_topic_text(raw_or_cleaned):
    """
    Detecta plantillas que rompen BERTopic: copyright/device en inglés,
    CTAs de canal (únete / telegram / canal…), saludos vacíos.
    """
    cleaned = clean_topic_text(raw_or_cleaned)
    if not cleaned:
        return True
    low = cleaned.lower()
    alpha = sum(1 for ch in cleaned if ch.isalpha())

    if _COPYRIGHT_BOILERPLATE_RE.search(low):
        return True

    # CTA explícito
    if _CHANNEL_CTA_RE.search(low):
        if len(cleaned) < 280 or alpha < 100:
            return True

    # Promo corto "… España … Telegram/canal …" (el cluster si_españa_telegram)
    if len(cleaned) < 320 and _PROMO_CHANNEL_RE.search(low) and _PROMO_HOOK_RE.search(low):
        return True

    # Mención a telegram/canal en textos muy cortos (casi siempre promo)
    if len(cleaned) < 140 and _PROMO_CHANNEL_RE.search(low):
        return True

    # Pocas palabras significativas + telegram/canal → plantilla
    tokens = [w for w in _NON_WORD_RE.sub(" ", low).split() if len(w) > 2]
    if _PROMO_CHANNEL_RE.search(low) and len(set(tokens)) <= 12 and len(cleaned) < 400:
        return True

    # Saludos genéricos muy cortos
    if len(cleaned) < 80 and re.search(
        r"\bfeliz\s*(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b|"
        r"\bviva\s+espa[nñ]a\b|"
        r"\bbuenos\s+d[ií]as\b|"
        r"\bbuenas\s+noches\b",
        low,
    ):
        return True

    return False


def is_usable_topic_text(raw, min_text_len=None, min_alpha=None):
    """True si, tras limpiar URLs, queda texto narrativo suficiente (sin plantillas)."""
    min_text_len = Config.TOPICS_MIN_TEXT_LEN if min_text_len is None else min_text_len
    min_alpha = Config.TOPICS_MIN_ALPHA_CHARS if min_alpha is None else min_alpha
    cleaned = clean_topic_text(raw)
    if len(cleaned) < int(min_text_len):
        return False
    alpha_chars = sum(1 for ch in cleaned if ch.isalpha())
    if alpha_chars < int(min_alpha):
        return False
    # Evitar cadenas casi solo puntuación / menciones
    if alpha_chars / max(len(cleaned), 1) < 0.35:
        return False
    if getattr(Config, "TOPICS_EXCLUDE_BOILERPLATE", True) and is_boilerplate_topic_text(cleaned):
        return False
    return True


def _normalize_for_dedupe(text_val):
    """Huella estable: minúsculas, sin emoji/puntuación, primeras 20 palabras >2 chars."""
    t = str(text_val or "").lower()
    t = _EMOJI_RE.sub(" ", t)
    t = _URL_RE.sub(" ", t)
    t = _TG_LINK_RE.sub(" ", t)
    t = _NON_WORD_RE.sub(" ", t)
    tokens = [w for w in _WHITESPACE_RE.sub(" ", t).strip().split() if len(w) > 2]
    return " ".join(tokens[:20])


def _dedupe_docs_for_training(df, text_col="_topic_text"):
    """Deja una fila por huella normalizada (variantes de CTA no saturan el modelo)."""
    if df.empty or text_col not in df.columns:
        return df
    keys = df[text_col].map(_normalize_for_dedupe)
    # Descartar huellas vacías / casi vacías
    valid = keys.str.len() >= 8
    before = len(df)
    out = df.loc[valid].copy()
    keys = keys.loc[valid]
    out = out.loc[~keys.duplicated(keep="first")].copy()
    logger.info("Deduplicación train: %d -> %d docs únicos (near-hash)", before, len(out))
    return out


def _postgres_base_query(days_window=None, min_text_len=None, exclude_media_only=None):
    from models import Message, db

    min_text_len = Config.TOPICS_MIN_TEXT_LEN if min_text_len is None else min_text_len
    if exclude_media_only is None:
        exclude_media_only = Config.TOPICS_EXCLUDE_MEDIA_ONLY
    date_expr = func.coalesce(Message.date_sent, Message.creation_date)
    media_expr = func.lower(func.coalesce(Message.media_type, ""))
    text_len = func.length(func.trim(Message.message_text))

    q = (
        db.session.query(
            Message.id.label("pg_id"),
            Message.message_id.label("telegram_id"),
            Message.message_text.label("message_text"),
            date_expr.label("date_sent"),
            Message.media_type.label("media_type"),
        )
        .filter(Message.message_text.isnot(None))
        .filter(text_len >= int(min_text_len))
        # Excluir en SQL los que son claramente una sola URL
        .filter(~Message.message_text.op("~*")(r"^\s*https?://\S+\s*$"))
    )
    if exclude_media_only:
        # Excluir Photo/Video/... con caption corto; se mantienen si hay texto largo
        caption_min = max(int(min_text_len), 60)
        q = q.filter(
            or_(
                ~media_expr.in_(sorted(_MEDIA_ONLY_TYPES)),
                text_len >= caption_min,
            )
        )
    if days_window and days_window > 0:
        cutoff = datetime.utcnow() - timedelta(days=days_window)
        q = q.filter(date_expr >= cutoff)
    return q


def _load_messages_from_postgres(
    days_window=None,
    sample_size=None,
    min_text_len=None,
    seed=None,
    quality_filter=True,
):
    """Carga mensajes desde RDS. Con sample_size, muestreo aleatorio en SQL (no carga todo)."""
    from pg_upsert import create_app

    app = create_app()
    fetch_size = None
    if sample_size and sample_size > 0:
        overfetch = max(1.0, float(Config.TOPICS_SAMPLE_OVERFETCH or 1.0))
        fetch_size = int(sample_size * overfetch) if quality_filter else int(sample_size)

    with app.app_context():
        from models import db

        q = _postgres_base_query(days_window=days_window, min_text_len=min_text_len)
        if fetch_size:
            seed_val = _seed_to_float(seed if seed is not None else Config.TOPICS_SAMPLE_SEED)
            db.session.execute(text("SELECT setseed(:s)"), {"s": seed_val})
            q = q.order_by(func.random()).limit(int(fetch_size))
            logger.info(
                "Muestreo SQL: fetch=%s target=%s seed=%s min_text_len=%s",
                fetch_size,
                sample_size,
                seed if seed is not None else Config.TOPICS_SAMPLE_SEED,
                min_text_len if min_text_len is not None else Config.TOPICS_MIN_TEXT_LEN,
            )
        rows = q.all()
        df = _rows_to_dataframe(rows)
        logger.info("Mensajes cargados desde PostgreSQL: %d", len(df))

    if quality_filter and not df.empty:
        before = len(df)
        docs, _ = _prepare_docs(df, min_text_len=min_text_len)
        df = df.assign(_topic_text=docs)
        df = df[df["_topic_text"].str.len() > 0]
        logger.info("Filtro calidad texto: %d -> %d", before, len(df))
        if sample_size and sample_size > 0 and len(df) > sample_size:
            df = df.head(int(sample_size))
    return df.reset_index(drop=True)


def _iter_message_batches_from_postgres(
    after_pg_id=0,
    batch_size=None,
    days_window=None,
    min_text_len=None,
):
    """Genera lotes ordenados por messages.id para asignación al histórico."""
    from models import Message
    from pg_upsert import create_app

    batch_size = batch_size or Config.TOPICS_ASSIGN_BATCH_SIZE
    app = create_app()
    last_id = int(after_pg_id or 0)
    while True:
        with app.app_context():
            q = _postgres_base_query(days_window=days_window, min_text_len=min_text_len)
            q = (
                q.filter(Message.id > last_id)
                .order_by(Message.id.asc())
                .limit(int(batch_size))
            )
            rows = q.all()
            if not rows:
                return
            df = _rows_to_dataframe(rows)
            last_id = int(df["_pg_id"].max())
        yield df, last_id


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


def _prepare_docs(df, min_text_len=None, min_alpha=None):
    """Devuelve serie de textos limpios usable para topics ('' = descartar)."""
    text_col = _extract_text_column(df)
    if not text_col:
        return pd.Series([], dtype=str), text_col

    min_text_len = Config.TOPICS_MIN_TEXT_LEN if min_text_len is None else min_text_len
    min_alpha = Config.TOPICS_MIN_ALPHA_CHARS if min_alpha is None else min_alpha

    cleaned = df[text_col].fillna("").astype(str).map(clean_topic_text)
    usable = cleaned.map(
        lambda t: t
        if is_usable_topic_text(t, min_text_len=min_text_len, min_alpha=min_alpha)
        else ""
    )

    # Media sin caption narrativo (doble filtro por si SQL dejó pasar alguno)
    if Config.TOPICS_EXCLUDE_MEDIA_ONLY and "Media Type" in df.columns:
        media = df["Media Type"].fillna("").astype(str).str.lower()
        media_only = media.isin(_MEDIA_ONLY_TYPES)
        short = usable.str.len() < max(int(min_text_len), 60)
        usable = usable.where(~(media_only & short), "")

    return usable, text_col


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


def _load_assign_progress(s3_client):
    try:
        content = s3_client.get_file_content(Config.TOPICS_ASSIGN_PROGRESS_KEY)
        return json.loads(content)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            return {}
        raise
    except Exception:
        return {}


def _save_assign_progress(s3_client, progress):
    payload = json.dumps(progress, ensure_ascii=True)
    s3_client.s3_client.put_object(
        Bucket=Config.S3_BUCKET,
        Key=Config.TOPICS_ASSIGN_PROGRESS_KEY,
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


def _train_model_with_pytopicgram(docs, model_path, apply_sample_ratio=True):
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

        # Si ya muestreámos en SQL, no volver a muestrear en pytopicgram
        if (
            apply_sample_ratio
            and Config.TOPICS_SAMPLE_RATIO
            and 0 < Config.TOPICS_SAMPLE_RATIO < 1
        ):
            cmd.extend(["--sample_ratio", str(Config.TOPICS_SAMPLE_RATIO)])

        logger.info("Entrenando modelo con pytopicgram (%d docs)", len(docs))
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
        return s3_client.load_csv_from_s3(Config.TOPICS_ASSIGNMENTS_KEY, missing_ok=True)
    except TypeError:
        # Compatibilidad si s3_client aún no tiene missing_ok
        try:
            return s3_client.load_csv_from_s3(Config.TOPICS_ASSIGNMENTS_KEY)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404"}:
                return pd.DataFrame()
            raise
    except ClientError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _upload_assignments(s3_client, assignments_df):
    s3_client.upload_dataframe(assignments_df, Config.TOPICS_ASSIGNMENTS_KEY, format="csv")


def _save_assignments_to_postgres(target_df, topics):
    """Persiste asignaciones en message_topics (PostgreSQL) con bulk insert."""
    if "_pg_id" not in target_df.columns:
        logger.warning("Sin columna _pg_id; no se escriben topics en PostgreSQL")
        return 0

    from models import MessageTopic
    from pg_upsert import create_app

    app = create_app()
    written = 0
    with app.app_context():
        from models import db

        pg_ids = [int(x) for x in target_df["_pg_id"].tolist()]
        MessageTopic.query.filter(MessageTopic.message_id.in_(pg_ids)).delete(
            synchronize_session=False
        )

        mappings = []
        for pg_id, topic_id in zip(pg_ids, topics):
            try:
                topic_id = int(topic_id)
            except (TypeError, ValueError):
                continue
            if topic_id < 0:
                continue
            mappings.append({"message_id": int(pg_id), "topic_id": topic_id})

        if mappings:
            db.session.bulk_insert_mappings(MessageTopic, mappings)
            written = len(mappings)
        db.session.commit()
    logger.info("Asignaciones guardadas en PostgreSQL: %d filas", written)
    return written


def _ensure_pytopicgram():
    if importlib.util.find_spec("pytopicgram") is None:
        logger.error("pytopicgram no disponible en este contenedor")
        return False
    return True


def train_sample_topics(
    sample_size=None,
    days_window=None,
    min_text_len=None,
    seed=None,
):
    """
    Fase 1: entrena el modelo con una submuestra SQL y sube model + metadata a S3.
    Asigna topics solo a la submuestra (útil para validar en staging), no al histórico completo.
    """
    if not _ensure_pytopicgram():
        return {"status": "error", "error": "pytopicgram_not_installed"}

    if not os.environ.get("DATABASE_URL"):
        return {"status": "error", "error": "DATABASE_URL_required_for_train_sample"}

    sample_size = sample_size if sample_size is not None else Config.TOPICS_TRAIN_SAMPLE_SIZE
    days_window = days_window if days_window is not None else Config.TOPICS_DAYS_WINDOW
    min_text_len = min_text_len if min_text_len is not None else Config.TOPICS_MIN_TEXT_LEN
    seed = seed if seed is not None else Config.TOPICS_SAMPLE_SEED

    logger.info(
        "train-sample: size=%s days=%s min_text=%s seed=%s",
        sample_size,
        days_window or "sin límite",
        min_text_len,
        seed,
    )
    df = _load_messages_from_postgres(
        days_window=days_window,
        sample_size=sample_size,
        min_text_len=min_text_len,
        seed=seed,
    )
    if df.empty:
        return {"status": "empty", "mode": "train_sample"}

    docs_series, _ = _prepare_docs(df, min_text_len=min_text_len)
    df = df.assign(_topic_text=docs_series)
    df = df[df["_topic_text"].str.len() > 0]
    if df.empty:
        return {"status": "empty", "mode": "train_sample", "reason": "no_usable_text"}

    raw_usable = int(len(df))
    train_df = df
    if getattr(Config, "TOPICS_TRAIN_DEDUPE", True):
        train_df = _dedupe_docs_for_training(df, text_col="_topic_text")
    if train_df.empty:
        return {"status": "empty", "mode": "train_sample", "reason": "no_unique_text"}

    logger.info(
        "train-sample docs: usable=%s unique_for_train=%s boilerplate_filter=%s",
        raw_usable,
        len(train_df),
        getattr(Config, "TOPICS_EXCLUDE_BOILERPLATE", True),
    )

    s3_client = get_s3_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.pkl")
        _train_model_with_pytopicgram(
            train_df["_topic_text"].tolist(),
            model_path,
            apply_sample_ratio=False,
        )
        model = _load_topic_model(model_path)
        _upload_model(s3_client, model_path)
        _save_topics_metadata(s3_client, model)

        # Asignar a toda la submuestra usable (no solo a los únicos del train)
        topics, probs = _assign_topics(model, df["_topic_text"].tolist())
        if probs is None:
            probs = [None] * len(topics)

        assignments = pd.DataFrame(
            {
                "Message ID": df["Message ID"].astype(str),
                "topic_id": pd.Series(topics).astype(int),
                "topic_prob": pd.Series(probs).astype(float),
            }
        )
        _upload_assignments(s3_client, assignments)
        written = _save_assignments_to_postgres(df, topics)

        topic_info = _get_topic_info(model)
        n_topics = 0
        if isinstance(topic_info, list):
            n_topics = len(
                [
                    t
                    for t in topic_info
                    if int(t.get("Topic", t.get("topic_id", t.get("id", -1)))) >= 0
                ]
            )

    return {
        "status": "ok",
        "mode": "train_sample",
        "sample_size": int(raw_usable),
        "train_unique_docs": int(len(train_df)),
        "topics_found": int(n_topics),
        "postgres_rows": int(written),
        "days_window": days_window or None,
        "model_key": Config.TOPICS_MODEL_KEY,
        "meta_key": Config.TOPICS_META_KEY,
    }


def assign_all_topics(
    batch_size=None,
    days_window=None,
    min_text_len=None,
    reset_progress=False,
):
    """
    Fase 3: aplica el modelo ya entrenado a todo el histórico por lotes, con checkpoint en S3.
    """
    if not _ensure_pytopicgram():
        return {"status": "error", "error": "pytopicgram_not_installed"}

    if not os.environ.get("DATABASE_URL"):
        return {"status": "error", "error": "DATABASE_URL_required_for_assign_all"}

    batch_size = batch_size if batch_size is not None else Config.TOPICS_ASSIGN_BATCH_SIZE
    days_window = days_window if days_window is not None else Config.TOPICS_DAYS_WINDOW
    min_text_len = min_text_len if min_text_len is not None else Config.TOPICS_MIN_TEXT_LEN

    s3_client = get_s3_client()
    if not _model_exists(s3_client):
        return {
            "status": "error",
            "error": "model_not_found",
            "hint": "Ejecuta primero --train-sample",
        }

    progress = {} if reset_progress else _load_assign_progress(s3_client)
    after_pg_id = int(progress.get("last_pg_id") or 0)
    total_assigned = int(progress.get("total_assigned") or 0)
    batches = int(progress.get("batches") or 0)

    logger.info(
        "assign-all: batch_size=%s after_pg_id=%s days=%s",
        batch_size,
        after_pg_id,
        days_window or "sin límite",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "model.pkl")
        _download_model(s3_client, model_path)
        model = _load_topic_model(model_path)

        for batch_df, last_pg_id in _iter_message_batches_from_postgres(
            after_pg_id=after_pg_id,
            batch_size=batch_size,
            days_window=days_window,
            min_text_len=min_text_len,
        ):
            docs_series, _ = _prepare_docs(batch_df, min_text_len=min_text_len)
            batch_df = batch_df.assign(_topic_text=docs_series)
            usable = batch_df[batch_df["_topic_text"].str.len() > 0]
            if usable.empty:
                after_pg_id = last_pg_id
                batches += 1
                _save_assign_progress(
                    s3_client,
                    {
                        "last_pg_id": after_pg_id,
                        "total_assigned": total_assigned,
                        "batches": batches,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                )
                continue

            topics, _probs = _assign_topics(model, usable["_topic_text"].tolist())
            written = _save_assignments_to_postgres(usable, topics)
            total_assigned += written
            after_pg_id = last_pg_id
            batches += 1
            _save_assign_progress(
                s3_client,
                {
                    "last_pg_id": after_pg_id,
                    "total_assigned": total_assigned,
                    "batches": batches,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            logger.info(
                "assign-all lote %d: last_pg_id=%s escritos=%s acumulado=%s",
                batches,
                after_pg_id,
                written,
                total_assigned,
            )

        _save_topics_metadata(s3_client, model)
        _save_state(
            s3_client,
            {
                "last_processed_at": datetime.utcnow().isoformat(),
                "last_message_id": after_pg_id,
                "mode": "assign_all",
            },
        )

    return {
        "status": "ok",
        "mode": "assign_all",
        "batches": batches,
        "total_assigned": total_assigned,
        "last_pg_id": after_pg_id,
        "days_window": days_window or None,
    }


def process_topics(days_window=None):
    """Modo incremental diario: solo mensajes nuevos desde state.json."""
    if not _ensure_pytopicgram():
        return {"status": "error", "error": "pytopicgram_not_installed"}

    days_window = days_window if days_window is not None else Config.TOPICS_DAYS_WINDOW
    use_postgres = bool(os.environ.get("DATABASE_URL"))

    if use_postgres:
        logger.info("Cargando mensajes desde PostgreSQL (ventana: %s días)", days_window or "sin límite")
        # Incremental: no muestrear; filtrar por state después
        df = _load_messages_from_postgres(days_window=days_window, sample_size=None)
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
            train_docs = df["_topic_text"].tolist()
            if len(train_docs) > Config.TOPICS_TRAIN_SAMPLE_SIZE > 0:
                train_docs = (
                    pd.Series(train_docs)
                    .sample(
                        n=Config.TOPICS_TRAIN_SAMPLE_SIZE,
                        random_state=abs(hash(Config.TOPICS_SAMPLE_SEED)) % (2**32),
                    )
                    .tolist()
                )
            _train_model_with_pytopicgram(train_docs, model_path, apply_sample_ratio=False)
            model = _load_topic_model(model_path)
            _upload_model(s3_client, model_path)
            assign_full_dataset = True

        topics, probs = _assign_topics(model, new_df["_topic_text"].tolist())
        unassigned_ratio = (pd.Series(topics) == -1).mean() if len(topics) else 0

        if (
            len(new_df) >= Config.TOPICS_MIN_NEW_MESSAGES
            and unassigned_ratio >= Config.TOPICS_RETRAIN_THRESHOLD
            and Config.TOPICS_RESET_STATE
        ):
            logger.info("Reentrenando modelo por alto ratio de no asignados")
            train_docs = df["_topic_text"].tolist()
            if len(train_docs) > Config.TOPICS_TRAIN_SAMPLE_SIZE > 0:
                train_docs = (
                    pd.Series(train_docs)
                    .sample(
                        n=Config.TOPICS_TRAIN_SAMPLE_SIZE,
                        random_state=abs(hash(Config.TOPICS_SAMPLE_SEED)) % (2**32),
                    )
                    .tolist()
                )
            _train_model_with_pytopicgram(train_docs, model_path, apply_sample_ratio=False)
            model = _load_topic_model(model_path)
            _upload_model(s3_client, model_path)
            assign_full_dataset = True

        if assign_full_dataset:
            # En modo incremental no reasignar todo el DF en memoria si es enorme
            if use_postgres and len(df) > Config.TOPICS_TRAIN_SAMPLE_SIZE * 2:
                logger.info(
                    "Dataset grande (%d): solo asigna mensajes nuevos; "
                    "usa --assign-all para el histórico",
                    len(df),
                )
                target_df = new_df.copy()
                topics, probs = _assign_topics(model, target_df["_topic_text"].tolist())
            else:
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
        "mode": "incremental",
        "new_messages": int(len(new_df)),
        "retrained": bool(assign_full_dataset),
        "days_window": days_window or None,
        "postgres": use_postgres,
    }


if __name__ == "__main__":
    result = process_topics()
    logger.info(f"Resultado topics: {result}")
