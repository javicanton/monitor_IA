import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

import duckdb
import pandas as pd

from config import Config
from s3_client import get_s3_client

logger = logging.getLogger(__name__)


def _parse_s3_uri(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not value or not isinstance(value, str):
        return None, None
    if not value.startswith("s3://"):
        return None, value
    raw = value.replace("s3://", "", 1)
    if "/" not in raw:
        return raw, ""
    bucket, key = raw.split("/", 1)
    return bucket, key


class DataStore:
    def __init__(self):
        bucket_from_uri, key_from_uri = _parse_s3_uri(
            os.environ.get("DATASTORE_S3_PARQUET_KEY", "telegram_messages.parquet")
        )
        self.bucket = bucket_from_uri or Config.S3_BUCKET
        self.parquet_key = key_from_uri or "telegram_messages.parquet"

        cache_dir = os.environ.get("DATASTORE_CACHE_DIR")
        if not cache_dir:
            cache_dir = "/app/data/cache" if os.path.isdir("/app/data") else os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                "instance",
                "cache",
            )
        self.cache_dir = cache_dir
        self.messages_parquet_path = os.path.join(self.cache_dir, "telegram_messages.parquet")
        self.assignments_csv_path = os.path.join(self.cache_dir, "message_topics.csv")
        self.meta_path = os.path.join(self.cache_dir, "datastore_meta.json")
        self.lock = threading.Lock()

    def _ensure_cache_dir(self) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)

    def _read_meta(self) -> Dict:
        try:
            with open(self.meta_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _write_meta(self, meta: Dict) -> None:
        self._ensure_cache_dir()
        with open(self.meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=True, indent=2)

    def _quoted(self, path: str) -> str:
        return path.replace("\\", "\\\\").replace("'", "''")

    def _get_s3_client(self):
        s3_client = get_s3_client()
        s3_client.bucket_name = self.bucket
        return s3_client

    def _head_object(self, s3_key: str) -> Optional[Dict]:
        try:
            s3_client = self._get_s3_client()
            response = s3_client.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            return {
                "etag": str(response.get("ETag", "")).strip('"'),
                "size": int(response.get("ContentLength", 0)),
                "last_modified": response.get("LastModified").isoformat() if response.get("LastModified") else "",
            }
        except Exception as exc:
            message = str(exc)
            if "NoSuchKey" in message or "404" in message or "Not Found" in message:
                return None
            logger.warning("No se pudo consultar metadatos S3 para %s: %s", s3_key, exc)
            return None

    def _sync_optional_file(self, s3_key: str, local_path: str, meta: Dict, meta_key: str) -> None:
        head = self._head_object(s3_key)
        if not head:
            return
        local_meta = meta.get(meta_key, {})
        if os.path.exists(local_path) and local_meta == head:
            return
        self._ensure_cache_dir()
        s3_client = self._get_s3_client()
        s3_client.download_file(s3_key, local_path)
        meta[meta_key] = head

    def _public_json_url(self) -> str:
        json_key = os.environ.get("DATASTORE_S3_JSON_KEY", "telegram_messages.json")
        return os.environ.get(
            "S3_PUBLIC_JSON_URL",
            f"https://{self.bucket}.s3.{Config.AWS_REGION}.amazonaws.com/{json_key}",
        )

    def _load_from_public_json(self) -> Optional[pd.DataFrame]:
        """Misma vía que producción histórica: URL pública del JSON en S3."""
        url = self._public_json_url()
        try:
            import requests

            logger.info("Intentando cargar dataset desde URL pública: %s", url)
            response = requests.get(url, timeout=120)
            if response.status_code != 200:
                logger.warning("URL pública respondió %s", response.status_code)
                return None
            data = response.json()
            messages = data.get("messages", data) if isinstance(data, dict) else data
            df = pd.DataFrame(messages)
            if df.empty:
                return None
            logger.info("Dataset cargado desde URL pública (%d filas)", len(df))
            return df
        except Exception as exc:
            logger.warning("No se pudo cargar desde URL pública: %s", exc)
            return None

    def _build_parquet_from_json_or_csv(self, meta: Dict) -> None:
        """Genera parquet local desde URL pública, JSON o CSV en S3."""
        json_key = os.environ.get("DATASTORE_S3_JSON_KEY", "telegram_messages.json")
        csv_key = "telegram_messages.csv"
        df = self._load_from_public_json()
        source_meta = {"source": "public_url"} if df is not None else None

        if df is None:
            s3_client = self._get_s3_client()
            for key, loader in (
                (json_key, lambda k: pd.DataFrame(s3_client.load_json_from_s3(k).get("messages", []))),
                (csv_key, s3_client.load_csv_from_s3),
            ):
                try:
                    df = loader(key)
                    source_meta = self._head_object(key) or {"source": f"s3:{key}"}
                    logger.info("Dataset cargado desde S3:%s (%d filas) para generar parquet", key, len(df))
                    break
                except Exception as exc:
                    logger.warning("No se pudo leer %s vía API S3: %s", key, exc)

        if df is None or df.empty:
            raise FileNotFoundError(
                f"No se encontró {self.parquet_key} ni {json_key}/{csv_key} en S3 ni URL pública"
            )
        self._ensure_cache_dir()
        df.to_parquet(self.messages_parquet_path, index=False)
        meta["messages_parquet"] = source_meta or {"source": "json_fallback"}

    def ensure_local_parquet(self, force: bool = False) -> str:
        with self.lock:
            self._ensure_cache_dir()
            meta = self._read_meta()
            remote_meta = self._head_object(self.parquet_key)
            local_meta = meta.get("messages_parquet", {})
            if (
                not force
                and os.path.exists(self.messages_parquet_path)
                and (remote_meta is None or local_meta == remote_meta)
            ):
                self._sync_optional_file(
                    Config.TOPICS_ASSIGNMENTS_KEY, self.assignments_csv_path, meta, "topics_assignments"
                )
                self._write_meta(meta)
                return self.messages_parquet_path
            if remote_meta is not None:
                s3_client = self._get_s3_client()
                s3_client.download_file(self.parquet_key, self.messages_parquet_path)
                meta["messages_parquet"] = remote_meta
            else:
                logger.warning("Parquet %s no está en S3; usando JSON/CSV como fuente", self.parquet_key)
                self._build_parquet_from_json_or_csv(meta)
            self._sync_optional_file(
                Config.TOPICS_ASSIGNMENTS_KEY, self.assignments_csv_path, meta, "topics_assignments"
            )
            self._write_meta(meta)
            return self.messages_parquet_path

    def get_dataset_fingerprint(self) -> str:
        meta = self._read_meta().get("messages_parquet", {})
        return ":".join(
            [
                str(meta.get("etag", "")),
                str(meta.get("size", "")),
                str(meta.get("last_modified", "")),
            ]
        )

    def _connect(self):
        return duckdb.connect(database=":memory:")

    def _date_expr(self, alias: str = "m") -> str:
        return (
            f"coalesce("
            f"try_cast({alias}.\"Date Sent\" as TIMESTAMP), "
            f"try_cast({alias}.\"Date\" as TIMESTAMP), "
            f"try_cast({alias}.\"Creation Date\" as TIMESTAMP)"
            f")"
        )

    def _normalize_topic_filter(self, topic_filter) -> List[int]:
        topic_ids = []
        if isinstance(topic_filter, str):
            topic_ids = [item for item in topic_filter.split(",") if item]
        elif isinstance(topic_filter, list):
            topic_ids = topic_filter
        normalized = []
        for item in topic_ids:
            if isinstance(item, dict) and "id" in item:
                item = item["id"]
            try:
                normalized.append(int(item))
            except Exception:
                continue
        return normalized

    def _search_ids(self, filters) -> Optional[List[int]]:
        search_query = (filters.get("search") or filters.get("q") or "").strip()
        if not search_query:
            return None
        try:
            from search_index import ensure_index_synced_from_parquet, search_message_ids

            parquet_path = self.ensure_local_parquet()
            ensure_index_synced_from_parquet(parquet_path, self.get_dataset_fingerprint())
            ids = search_message_ids(search_query)
            if ids is not None:
                return ids
        except Exception as exc:
            logger.warning("Búsqueda FTS no disponible: %s", exc)
        return None

    def _build_from_clause(self, include_topics: bool) -> str:
        parquet_path = self._quoted(self.ensure_local_parquet())
        from_clause = f" FROM read_parquet('{parquet_path}') m"
        if include_topics and os.path.exists(self.assignments_csv_path):
            assignments_path = self._quoted(self.assignments_csv_path)
            from_clause += (
                f" LEFT JOIN read_csv_auto('{assignments_path}', header=true) a"
                f" ON cast(m.\"Message ID\" as VARCHAR) = cast(a.\"Message ID\" as VARCHAR)"
            )
        return from_clause

    def _build_where_clause(self, filters: Dict, search_ids: Optional[List[int]], include_topics: bool) -> Tuple[str, List]:
        clauses = []
        params: List = []

        if search_ids is not None:
            if not search_ids:
                clauses.append("1 = 0")
            else:
                placeholders = ", ".join(["?"] * len(search_ids))
                clauses.append(f"cast(m.\"Message ID\" as BIGINT) IN ({placeholders})")
                params.extend(search_ids)

        channel = filters.get("channel")
        if channel:
            if isinstance(channel, list):
                placeholders = ", ".join(["?"] * len(channel))
                clauses.append(f"m.\"Title\" IN ({placeholders})")
                params.extend(channel)
            else:
                clauses.append("m.\"Title\" = ?")
                params.append(channel)

        topic_filter = filters.get("topics") or filters.get("topic")
        topic_ids = self._normalize_topic_filter(topic_filter)
        if topic_filter and topic_ids:
            if include_topics:
                placeholders = ", ".join(["?"] * len(topic_ids))
                clauses.append(f"cast(a.topic_id as BIGINT) IN ({placeholders})")
                params.extend(topic_ids)
            else:
                clauses.append("1 = 0")

        score_min = filters.get("scoreMin")
        if score_min not in (None, ""):
            clauses.append("coalesce(try_cast(m.\"Score\" as DOUBLE), 0) >= ?")
            params.append(float(score_min))

        score_max = filters.get("scoreMax")
        if score_max not in (None, ""):
            clauses.append("coalesce(try_cast(m.\"Score\" as DOUBLE), 0) <= ?")
            params.append(float(score_max))

        label_value = filters.get("label")
        if label_value not in (None, ""):
            clauses.append("coalesce(try_cast(m.\"Label\" as BIGINT), -1) = ?")
            params.append(int(label_value))

        media_type = filters.get("mediaType")
        if media_type:
            media_values = [media_type] if isinstance(media_type, str) else media_type
            media_values = [str(item).lower() for item in media_values if item]
            if media_values:
                placeholders = ", ".join(["?"] * len(media_values))
                clauses.append(f"lower(coalesce(m.\"Media Type\", '')) IN ({placeholders})")
                params.extend(media_values)

        date_start = filters.get("dateStart")
        if date_start:
            clauses.append(f"date_trunc('day', {self._date_expr()}) >= date_trunc('day', cast(? as TIMESTAMP))")
            params.append(date_start)

        date_end = filters.get("dateEnd")
        if date_end:
            clauses.append(f"date_trunc('day', {self._date_expr()}) < date_trunc('day', cast(? as TIMESTAMP)) + INTERVAL 1 DAY")
            params.append(date_end)

        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def _sort_clause(self, filters: Dict) -> str:
        sort_by = filters.get("sortBy", "score")
        if sort_by == "views":
            return " ORDER BY coalesce(try_cast(m.\"Views\" as DOUBLE), 0) DESC, cast(m.\"Message ID\" as BIGINT) DESC"
        if sort_by == "date":
            return f" ORDER BY {self._date_expr()} DESC NULLS LAST, cast(m.\"Message ID\" as BIGINT) DESC"
        if sort_by == "channel":
            return " ORDER BY lower(coalesce(m.\"Title\", '')) ASC, cast(m.\"Message ID\" as BIGINT) DESC"
        return " ORDER BY coalesce(try_cast(m.\"Score\" as DOUBLE), 0) DESC, cast(m.\"Message ID\" as BIGINT) DESC"

    def _has_topic_join(self, filters: Dict) -> bool:
        topic_filter = filters.get("topics") or filters.get("topic")
        if bool(topic_filter):
            return os.path.exists(self.assignments_csv_path)
        return os.path.exists(self.assignments_csv_path)

    def query_messages(self, filters: Dict, limit: int, offset: int) -> Tuple[pd.DataFrame, int]:
        search_ids = self._search_ids(filters)
        topic_filter = filters.get("topics") or filters.get("topic")
        has_topic_join = self._has_topic_join(filters)
        from_clause = self._build_from_clause(has_topic_join)
        where_sql, params = self._build_where_clause(filters, search_ids, has_topic_join)
        sort_sql = self._sort_clause(filters)

        topic_select = "cast(a.topic_id as BIGINT) as topic_id" if has_topic_join else "NULL::BIGINT as topic_id"
        count_sql = (
            f"SELECT COUNT(DISTINCT cast(m.\"Message ID\" AS BIGINT)){from_clause}{where_sql}"
            if has_topic_join
            else f"SELECT COUNT(*){from_clause}{where_sql}"
        )
        query_sql = (
            "SELECT m.\"Embed\", coalesce(try_cast(m.\"Score\" as DOUBLE), 0) as \"Score\", "
            "cast(m.\"Message ID\" as BIGINT) as \"Message ID\", m.\"URL\", m.\"Label\", "
            f"{topic_select} "
            f"{from_clause}{where_sql}{sort_sql} LIMIT ? OFFSET ?"
        )

        con = self._connect()
        try:
            total = int(con.execute(count_sql, params).fetchone()[0])
            df = con.execute(query_sql, params + [limit, offset]).fetchdf()
            return df, total
        finally:
            con.close()

    def get_channels(self) -> List[str]:
        from_clause = self._build_from_clause(include_topics=False)
        sql = (
            f"SELECT m.\"Title\" as title, COUNT(*) as msg_count{from_clause} "
            f"WHERE m.\"Title\" IS NOT NULL AND trim(m.\"Title\") <> '' "
            f"GROUP BY m.\"Title\" "
            f"ORDER BY msg_count DESC, lower(m.\"Title\")"
        )
        con = self._connect()
        try:
            rows = con.execute(sql).fetchall()
            return [row[0] for row in rows if row and row[0]]
        finally:
            con.close()

    def messages_over_time(self, filters: Dict) -> List[Dict]:
        filters = {k: v for k, v in (filters or {}).items() if k not in ("dateStart", "dateEnd")}
        search_ids = self._search_ids(filters)
        has_topic_join = self._has_topic_join(filters)
        from_clause = self._build_from_clause(has_topic_join)
        where_sql, params = self._build_where_clause(filters, search_ids, has_topic_join)
        date_expr = self._date_expr()
        day_expr = f"CAST(date_trunc('day', {date_expr}) AS DATE)"

        sql_parts = [
            f"SELECT {day_expr} AS day,",
            " COUNT(DISTINCT cast(m.\"Message ID\" AS BIGINT)) AS count",
            from_clause,
        ]
        if where_sql:
            sql_parts.extend([where_sql, f"AND {date_expr} IS NOT NULL"])
        else:
            sql_parts.append(f"WHERE {date_expr} IS NOT NULL")
        sql_parts.append("GROUP BY day ORDER BY day")
        sql = " ".join(sql_parts)

        con = self._connect()
        try:
            rows = con.execute(sql, params).fetchall()
            return [
                {"date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]), "count": int(row[1])}
                for row in rows
                if row[0] is not None
            ]
        except Exception as exc:
            logger.exception("messages_over_time SQL falló (%s); usando pandas", exc)
            return self._messages_over_time_pandas(filters)
        finally:
            con.close()

    def _messages_over_time_pandas(self, filters: Dict) -> List[Dict]:
        """Fallback robusto: lee parquet y agrupa por día en pandas."""
        parquet_path = self.ensure_local_parquet()
        con = self._connect()
        try:
            df = con.execute(
                f"SELECT * FROM read_parquet('{self._quoted(parquet_path)}')"
            ).fetchdf()
        finally:
            con.close()
        if df.empty:
            return []

        filtered = df
        channel = filters.get("channel")
        if channel:
            titles = channel if isinstance(channel, list) else [channel]
            if "Title" in filtered.columns:
                filtered = filtered[filtered["Title"].isin(titles)]

        date_col = next((c for c in ("Date Sent", "Date", "Creation Date") if c in filtered.columns), None)
        if not date_col:
            return []

        dates = pd.to_datetime(filtered[date_col], errors="coerce", utc=True)
        if hasattr(dates.dt, "tz") and dates.dt.tz is not None:
            dates = dates.dt.tz_convert(None)
        filtered = filtered.assign(_day=dates.dt.normalize())
        filtered = filtered.dropna(subset=["_day"])
        if filtered.empty:
            return []

        counts = filtered.groupby("_day").size().reset_index(name="count")
        return [
            {"date": row["_day"].strftime("%Y-%m-%d"), "count": int(row["count"])}
            for _, row in counts.iterrows()
        ]

    def export_filtered_dataframe(self, filters: Dict) -> pd.DataFrame:
        search_ids = self._search_ids(filters)
        has_topic_join = self._has_topic_join(filters)
        from_clause = self._build_from_clause(has_topic_join)
        where_sql, params = self._build_where_clause(filters, search_ids, has_topic_join)
        topic_select = "cast(a.topic_id as BIGINT) as topic_id" if has_topic_join else "NULL::BIGINT as topic_id"
        sql = (
            "SELECT cast(m.\"Message ID\" as BIGINT) as \"Message ID\", m.\"Message Text\", m.\"Title\", "
            f"{self._date_expr()} as \"Date Sent\", coalesce(try_cast(m.\"Views\" as DOUBLE), 0) as \"Views\", "
            "coalesce(try_cast(m.\"Score\" as DOUBLE), 0) as \"Score\", m.\"Label\", m.\"URL\", "
            "m.\"Media Type\", "
            f"{topic_select} "
            f"{from_clause}{where_sql}{self._sort_clause(filters)}"
        )
        con = self._connect()
        try:
            return con.execute(sql, params).fetchdf()
        finally:
            con.close()

    def update_label(self, message_id: int, label: int) -> bool:
        parquet_path = self.ensure_local_parquet()
        tmp_path = f"{parquet_path}.tmp"
        con = self._connect()
        try:
            quoted = self._quoted(parquet_path)
            quoted_tmp = self._quoted(tmp_path)
            con.execute(f"CREATE TABLE messages AS SELECT * FROM read_parquet('{quoted}')")
            con.execute(
                "UPDATE messages SET \"Label\" = ? WHERE cast(\"Message ID\" as BIGINT) = ?",
                [label, message_id],
            )
            updated = con.execute(
                "SELECT COUNT(*) FROM messages WHERE cast(\"Message ID\" as BIGINT) = ?",
                [message_id],
            ).fetchone()[0]
            if not updated:
                return False
            con.execute(f"COPY messages TO '{quoted_tmp}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            os.replace(tmp_path, parquet_path)
            s3_client = self._get_s3_client()
            s3_client.upload_file(parquet_path, self.parquet_key)
            return True
        finally:
            con.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def get_search_source_dataframe(self) -> pd.DataFrame:
        parquet_path = self.ensure_local_parquet()
        con = self._connect()
        try:
            quoted = self._quoted(parquet_path)
            return con.execute(
                f"SELECT cast(\"Message ID\" as BIGINT) as \"Message ID\", "
                f"coalesce(\"Message Text\", '') as \"Message Text\", "
                f"coalesce(\"Title\", '') as \"Title\" "
                f"FROM read_parquet('{quoted}')"
            ).fetchdf()
        finally:
            con.close()

