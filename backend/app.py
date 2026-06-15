import os
from pathlib import Path
# Cargar .env antes de importar Config (raíz del repo o backend/)
for _dir in (Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent):
    _env = _dir / ".env"
    if _env.exists():
        from dotenv import load_dotenv
        load_dotenv(_env)
        break

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_mail import Mail, Message as MailMessage
from io import BytesIO
import zipfile
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from datetime import datetime, timedelta
import json
from s3_client import get_s3_client
from auth import auth_bp, admin_required
from models import Channel, ChannelEdge, MonitoredChannel, db
from channel_graph import normalize_username
from config import Config
import boto3
from botocore.exceptions import ClientError
import logging
from threading import Thread
from topic_processor import process_topics
from search_index import ensure_index_synced, search_message_ids
import re

# Store de mensajes: PostgreSQL si DATABASE_URL está definido, si no DuckDB+Parquet (solo analytics/offline)
def _get_data_store():
    if os.environ.get('DATABASE_URL'):
        from data_store_pg import DataStorePG
        return DataStorePG()
    from data_store import DataStore
    return DataStore()

data_store = _get_data_store()
USE_POSTGRES = bool(os.environ.get('DATABASE_URL'))

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MESSAGES_LIMIT = 48
S3_BUCKET = os.environ.get('S3_BUCKET', 'monitoria-data')
S3_KEY = 'telegram_messages.json'
CHANNEL_SUGGEST_EMAIL = os.environ.get('CHANNEL_SUGGEST_EMAIL', 'monitoria@unir.net')

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensiones
mail = Mail(app)
jwt = JWTManager(app)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://app.monitoria.org",
            "https://monitoria.org",
            "http://localhost:3001"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
db.init_app(app)

# Registrar blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')

# Crear tablas de base de datos
with app.app_context():
    db.create_all()

# Caché en memoria solo cuando no se usa PostgreSQL (path DuckDB/JSON)
_DATA_CACHE = None
_DATA_CACHE_TIME = 0
DATA_CACHE_TTL_SEC = int(os.environ.get('DATA_CACHE_TTL_SEC', '1800'))  # 30 min por defecto

def load_data():
    """Carga los datos desde S3 (o caché) y maneja posibles errores."""
    global _DATA_CACHE, _DATA_CACHE_TIME
    now = datetime.now().timestamp()
    if _DATA_CACHE is not None and (now - _DATA_CACHE_TIME) < DATA_CACHE_TTL_SEC:
        logger.info("Datos servidos desde caché (%d filas)", len(_DATA_CACHE))
        return _DATA_CACHE
    try:
        # Intentar cargar desde URL pública primero (más rápido)
        try:
            logger.info("Intentando cargar desde URL pública de S3")
            import requests
            response = requests.get('https://monitoria-data.s3.eu-north-1.amazonaws.com/telegram_messages.json', timeout=30)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data['messages'])
                logger.info(f"Datos cargados desde URL pública, filas: {len(df)}")
                _DATA_CACHE = df
                _DATA_CACHE_TIME = datetime.now().timestamp()
                return df
        except Exception as e:
            logger.warning(f"No se pudo cargar desde URL pública: {e}")
        
        # Intentar cargar desde S3 con credenciales
        s3_client = get_s3_client()
        
        # Verificar conexión con S3
        if not s3_client.check_connection():
            logger.warning("No se pudo conectar con S3, intentando cargar desde archivo local")
            df = load_data_local()
            if df is not None and not df.empty:
                _DATA_CACHE = df
                _DATA_CACHE_TIME = datetime.now().timestamp()
            return df
        
        # Listar archivos disponibles en S3
        files = s3_client.list_files()
        logger.info(f"Archivos disponibles en S3: {files}")
        
        # Buscar archivo de mensajes (prioridad: JSON, luego CSV)
        messages_file = None
        for file in files:
            if 'telegram_messages' in file.lower():
                if file.endswith('.json'):
                    messages_file = file
                    break
                elif file.endswith('.csv') and not messages_file:
                    messages_file = file
        
        if not messages_file:
            logger.warning("No se encontró archivo de mensajes en S3, intentando archivo local")
            df = load_data_local()
            if df is not None and not df.empty:
                _DATA_CACHE = df
                _DATA_CACHE_TIME = datetime.now().timestamp()
            return df
        
        logger.info(f"Cargando datos desde S3: {messages_file}")
        
        # Cargar datos según el formato del archivo
        if messages_file.endswith('.json'):
            data = s3_client.load_json_from_s3(messages_file)
            df = pd.DataFrame(data['messages'])
        elif messages_file.endswith('.csv'):
            df = s3_client.load_csv_from_s3(messages_file)
        else:
            logger.error(f"Formato de archivo no soportado: {messages_file}")
            df = load_data_local()
            if df is not None and not df.empty:
                _DATA_CACHE = df
                _DATA_CACHE_TIME = datetime.now().timestamp()
            return df
        
        # Verificar y limpiar la columna Title (usada como Channel)
        if 'Title' in df.columns:
            # Limpiar valores nulos o vacíos
            df['Title'] = df['Title'].fillna('Desconocido')
            df['Title'] = df['Title'].replace('', 'Desconocido')
        
        # Convertir columnas de fecha si existen
        date_columns = ['Date', 'Date Sent', 'Creation Date', 'Edit Date']
        for col in date_columns:
            if col in df.columns:
                try:
                    # Convertir a datetime y eliminar zona horaria
                    df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)
                except Exception as e:
                    logger.warning(f"Error al convertir la columna '{col}': {e}")
                    if col in df.columns:
                        del df[col]
        
        logger.info(f"Datos cargados desde S3 exitosamente: {len(df)} mensajes")
        _DATA_CACHE = df
        _DATA_CACHE_TIME = datetime.now().timestamp()
        return df

    except Exception as e:
        logger.error(f"Error al cargar datos desde S3: {e}")
        logger.info("Intentando cargar desde archivo local como fallback")
        df = load_data_local()
        if df is not None and not df.empty:
            _DATA_CACHE = df
            _DATA_CACHE_TIME = datetime.now().timestamp()
        return df

def load_data_local():
    """Carga los datos del archivo JSON local como fallback."""
    try:
        json_path = 'telegram_messages.json'
        if not os.path.exists(json_path):
            logger.warning(f"El archivo {json_path} no existe.")
            return pd.DataFrame()
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convertir los mensajes a DataFrame
        df = pd.DataFrame(data['messages'])
        
        # Verificar y limpiar la columna Title (usada como Channel)
        if 'Title' in df.columns:
            df['Title'] = df['Title'].fillna('Desconocido')
            df['Title'] = df['Title'].replace('', 'Desconocido')
        
        # Convertir columnas de fecha si existen
        date_columns = ['Date', 'Date Sent', 'Creation Date', 'Edit Date']
        for col in date_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)
                except Exception as e:
                    logger.warning(f"Error al convertir la columna '{col}': {e}")
                    if col in df.columns:
                        del df[col]
        
        logger.info(f"Datos cargados desde archivo local: {len(df)} mensajes")
        return df

    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar el archivo JSON: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error crítico al cargar el archivo JSON: {e}")
        return pd.DataFrame()


def load_topics_meta():
    """Carga los metadatos de topics desde S3."""
    try:
        s3_client = get_s3_client()
        data = s3_client.load_json_from_s3(Config.TOPICS_META_KEY)
        topics = data.get('topics', data if isinstance(data, list) else [])
    except Exception as e:
        logger.warning(f"No se pudieron cargar topics: {e}")
        return []

    custom_titles = load_topic_titles()
    normalized = []
    for topic in topics:
        topic_id = topic.get('Topic', topic.get('topic_id', topic.get('id')))
        if topic_id is None:
            continue
        try:
            topic_id = int(topic_id)
        except Exception:
            continue

        label = topic.get('Name') or topic.get('name')
        if not label:
            terms = topic.get('terms')
            if isinstance(terms, list) and terms:
                label = ", ".join([str(term) for term in terms[:4]])
        if not label:
            label = f"Topic {topic_id}"
        if topic_id == -1:
            label = "Sin asignar"
        custom_label = custom_titles.get(str(topic_id))
        if custom_label:
            label = custom_label

        normalized.append({
            "id": topic_id,
            "label": label,
            "count": topic.get('Count', topic.get('count'))
        })

    unique = {}
    for item in normalized:
        unique[item["id"]] = item
    return list(unique.values())


def load_topic_titles():
    """Carga los titulos personalizados de topics desde S3."""
    try:
        s3_client = get_s3_client()
        data = s3_client.load_json_from_s3(Config.TOPICS_TITLES_KEY)
    except Exception as e:
        logger.warning(f"No se pudieron cargar titulos de topics: {e}")
        return {}

    titles = {}
    if isinstance(data, dict):
        raw_titles = data.get('titles', data)
        if isinstance(raw_titles, dict):
            titles = raw_titles
    elif isinstance(data, list):
        for item in data:
            topic_id = item.get('id')
            title = item.get('title')
            if topic_id is None or not title:
                continue
            titles[str(topic_id)] = title

    return {str(k): v for k, v in titles.items() if v}


def save_topic_titles(titles):
    """Guarda los titulos personalizados en S3."""
    payload = json.dumps({"titles": titles}, ensure_ascii=True)
    s3_client = get_s3_client()
    s3_client.s3_client.put_object(
        Bucket=Config.S3_BUCKET,
        Key=Config.TOPICS_TITLES_KEY,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )


def load_topic_assignments():
    """Carga asignaciones de topics desde S3."""
    try:
        s3_client = get_s3_client()
        return s3_client.load_csv_from_s3(Config.TOPICS_ASSIGNMENTS_KEY)
    except Exception as e:
        logger.warning(f"No se pudieron cargar asignaciones de topics: {e}")
        return pd.DataFrame()


def attach_topic_assignments(df):
    """Adjunta topic_id a los mensajes si existe el archivo de asignaciones."""
    if df.empty or 'Message ID' not in df.columns:
        return df

    assignments = load_topic_assignments()
    if assignments.empty or 'Message ID' not in assignments.columns:
        return df

    if 'topic_id' not in assignments.columns:
        return df

    merged = df.copy()
    merged['Message ID'] = merged['Message ID'].astype(str)
    assignments['Message ID'] = assignments['Message ID'].astype(str)
    return merged.merge(assignments[['Message ID', 'topic_id']], on='Message ID', how='left')

# Base de datos de usuarios (en producción usar una base de datos real)
users_db = {}

@app.route('/health')
def health_check():
    """Endpoint para verificar el estado del servicio."""
    return jsonify({"status": "healthy"}), 200


def save_data(df):
    """Guarda los datos en S3."""
    try:
        # Convertir DataFrame a JSON
        json_data = json.dumps({'messages': df.to_dict(orient='records')})
        
        # Subir a S3
        s3_client = get_s3_client()
        s3_client.s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        print(f"Error al guardar en S3: {e}")
        return False


def _parse_pagination(filters):
    default_limit = 24
    default_offset = 0

    def parse_int(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    limit = parse_int(filters.get('limit'), None)
    offset = parse_int(filters.get('offset'), None)
    page = parse_int(filters.get('page'), 1)
    per_page = parse_int(filters.get('per_page'), default_limit)

    if limit is None and offset is None:
        page = max(1, page)
        per_page = max(1, min(per_page, 100))
        limit = per_page
        offset = (page - 1) * per_page
    else:
        if limit is None:
            limit = default_limit
        if offset is None:
            offset = default_offset
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

    return limit, offset


def _attach_topic_titles_to_df(df):
    if df is None or df.empty or 'topic_id' not in df.columns:
        return df
    try:
        normalized = df.copy()
        normalized['topic_id'] = pd.to_numeric(normalized['topic_id'], errors='coerce').astype('Int64')
        topic_labels = {item['id']: item['label'] for item in load_topics_meta()}
        normalized['topic_title'] = normalized['topic_id'].map(topic_labels)
        return normalized
    except Exception as e:
        print(f"Error al adjuntar topic_title: {e}")
        return df


def _messages_from_dataframe(df):
    required_columns = ['Embed', 'Score', 'Message ID', 'URL', 'Label', 'topic_id', 'topic_title']
    messages = []
    for _, row in df.iterrows():
        msg = {}
        for col in required_columns:
            if col in row:
                value = row[col]
                if hasattr(value, "item"):
                    try:
                        value = value.item()
                    except Exception:
                        pass
                msg[col] = value if pd.notna(value) else None
            else:
                msg[col] = None
        messages.append(msg)
    return messages

@app.route('/')
def index():
    """Renderiza la página principal con los mensajes ordenados por puntuación."""
    if USE_POSTGRES:
        paginated_df, _ = data_store.query_messages({}, limit=MESSAGES_LIMIT, offset=0)
        if paginated_df.empty:
            return render_template('index.html', messages=[], channels=[], min_date='', max_date='')
        messages = _messages_from_dataframe(_attach_topic_titles_to_df(paginated_df))
        channels = data_store.get_channels()
        min_date, max_date = data_store.get_date_bounds()
        min_date = min_date or ''
        max_date = max_date or ''
        return render_template('index.html', messages=messages, channels=channels, min_date=min_date, max_date=max_date)

    df = load_data()
    if df.empty:
        return render_template('index.html', messages=[], channels=[], min_date='', max_date='')

    # Preparar datos para la plantilla inicial
    sorted_df = df.sort_values(by='Score', ascending=False) if 'Score' in df.columns else df
    displayed_df = sorted_df.head(MESSAGES_LIMIT)
    messages = displayed_df[['Embed', 'Score', 'Message ID', 'URL', 'Label']].to_dict(orient='records') if not displayed_df.empty else []

    # Obtener datos para filtros (canales, fechas)
    channels = []
    if 'Title' in df.columns:
        channels = sorted(df['Title'].unique().tolist())
        print(f"\nCanales que se pasan a la plantilla: {channels}")
    
    min_date = df['Date'].min().strftime('%Y-%m-%d') if 'Date' in df.columns and not df['Date'].empty else ''
    max_date = df['Date'].max().strftime('%Y-%m-%d') if 'Date' in df.columns and not df['Date'].empty else ''

    return render_template('index.html', messages=messages, channels=channels, min_date=min_date, max_date=max_date)

@app.route('/load_more/<int:offset>', methods=['GET'])
def load_more(offset=0):
    """Carga más mensajes a partir de un offset dado."""
    try:
        filters = request.get_json(silent=True) or {}
        if not filters:
            filters = {
                'dateStart': request.args.get('dateStart'),
                'dateEnd': request.args.get('dateEnd'),
                'channel': request.args.get('channel'),
                'topics': request.args.get('topics'),
                'scoreMin': request.args.get('scoreMin'),
                'scoreMax': request.args.get('scoreMax'),
                'mediaType': request.args.get('mediaType'),
                'sortBy': request.args.get('sortBy', 'score'),
                'search': request.args.get('search') or request.args.get('q')
            }
        date_start_str = filters.get('dateStart')
        date_end_str = filters.get('dateEnd')

        if USE_POSTGRES:
            paginated_df, total = data_store.query_messages(filters, limit=24, offset=offset)
            if paginated_df.empty or offset >= total:
                return ('', 204)
            paginated_df = _attach_topic_titles_to_df(paginated_df)
            messages = []
            for _, row in paginated_df.iterrows():
                score = row.get('Score')
                messages.append({
                    'Embed': row.get('Embed', ''),
                    'Score': round(score, 2) if score is not None and isinstance(score, (int, float)) else 'N/A',
                    'Message ID': row.get('Message ID', ''),
                    'URL': row.get('URL', ''),
                    'Label': row.get('Label', None),
                })
            return render_template('message_cards_partial.html', messages=messages)

        df = load_data()
        if df.empty:
            return ('', 204) # No Content

        # Aplicar los mismos filtros que en /filter_messages
        filtered_df = df.copy()

        # Búsqueda en texto (FTS5 o fallback pandas)
        search_query = (filters.get('search') or filters.get('q') or '').strip()
        if search_query and 'Message Text' in df.columns:
            search_applied = False
            try:
                ensure_index_synced(df)
                ids = search_message_ids(search_query)
                if ids is not None:
                    filtered_df = df[df['Message ID'].isin(ids)].copy()
                    search_applied = True
            except Exception:
                pass
            if not search_applied:
                text_series = filtered_df['Message Text']
                title_series = filtered_df['Title'] if 'Title' in filtered_df.columns else None
                parsed = _parse_boolean_search(search_query)
                if parsed:
                    mask = _apply_boolean_search_mask(parsed, text_series, title_series)
                    filtered_df = filtered_df[mask].copy()
                else:
                    q_lower = search_query.lower()
                    text_series = filtered_df['Message Text'].astype(str).fillna('')
                    mask = text_series.str.lower().str.contains(re.escape(q_lower), na=False, regex=True)
                    if title_series is not None:
                        title_series = filtered_df['Title'].astype(str).fillna('')
                        mask = mask | title_series.str.lower().str.contains(re.escape(q_lower), na=False, regex=True)
                    filtered_df = filtered_df[mask].copy()

        # Filtro de Fecha (Rango)
        if 'Date Sent' in filtered_df.columns and (date_start_str or date_end_str):
            try:
                filtered_df['Date Sent'] = pd.to_datetime(filtered_df['Date Sent'], errors='coerce').dt.tz_localize(None)
                
                if date_start_str:
                    date_start = pd.to_datetime(date_start_str).normalize()
                    filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() >= date_start]
                
                if date_end_str:
                    date_end = pd.to_datetime(date_end_str).normalize() + pd.Timedelta(days=1)
                    filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() < date_end]
            except Exception as e:
                print(f"Error en filtro de fechas: {str(e)}")
                pass

        # Filtro de Canal (uno o varios)
        channel_filter = filters.get('channel')
        if channel_filter and 'Title' in filtered_df.columns:
            try:
                if isinstance(channel_filter, str) and ',' in channel_filter:
                    channel_filter = [c for c in channel_filter.split(',') if c]
                if isinstance(channel_filter, list):
                    filtered_df = filtered_df[filtered_df['Title'].isin(channel_filter)]
                else:
                    filtered_df = filtered_df[filtered_df['Title'] == channel_filter]
            except Exception as e:
                print(f"Error en filtro de canal: {str(e)}")
                pass
        else:
            exclude_channel = filters.get('excludeChannel')
            if exclude_channel and 'Title' in filtered_df.columns:
                try:
                    if isinstance(exclude_channel, list):
                        filtered_df = filtered_df[~filtered_df['Title'].isin(exclude_channel)]
                    else:
                        filtered_df = filtered_df[filtered_df['Title'] != exclude_channel]
                except Exception as e:
                    print(f"Error en filtro de exclusión de canal: {str(e)}")
                    pass

        # Filtro de Topics (uno o varios)
        topic_filter = filters.get('topics') or filters.get('topic')
        if topic_filter:
            try:
                filtered_df = attach_topic_assignments(filtered_df)
                topic_ids = []
                if isinstance(topic_filter, str):
                    topic_ids = [t for t in topic_filter.split(',') if t]
                elif isinstance(topic_filter, list):
                    topic_ids = topic_filter

                normalized = []
                for item in topic_ids:
                    if isinstance(item, dict) and 'id' in item:
                        item = item['id']
                    try:
                        normalized.append(int(item))
                    except Exception:
                        continue

                if normalized and 'topic_id' in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df['topic_id'].isin(normalized)]
            except Exception as e:
                print(f"Error en filtro de topics: {str(e)}")
                pass

        # Filtro de Puntuación (Score) Mínima
        score_min_str = filters.get('scoreMin')
        if score_min_str and 'Score' in filtered_df.columns:
            try:
                score_min = float(score_min_str)
                filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
                filtered_df = filtered_df[filtered_df['Score'] >= score_min]
            except:
                pass

        # Filtro de Puntuación (Score) Máxima
        score_max_str = filters.get('scoreMax')
        if score_max_str and 'Score' in filtered_df.columns:
            try:
                score_max = float(score_max_str)
                filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
                filtered_df = filtered_df[filtered_df['Score'] <= score_max]
            except:
                pass

        # Filtro de Tipo de Media (uno o varios)
        media_type = filters.get('mediaType')
        if media_type and 'Media Type' in filtered_df.columns:
            try:
                types = [media_type] if isinstance(media_type, str) else media_type
                if types:
                    filtered_df['Media Type'] = filtered_df['Media Type'].astype(str).str.lower()
                    types_lower = [str(t).lower() for t in types]
                    filtered_df = filtered_df[filtered_df['Media Type'].isin(types_lower)]
            except:
                pass

        # Ordenar
        sort_by = filters.get('sortBy', 'score')
        if sort_by == 'views' and 'Views' in filtered_df.columns:
            filtered_df['Views'] = pd.to_numeric(filtered_df['Views'], errors='coerce')
            sorted_df = filtered_df.sort_values(by='Views', ascending=False)
        elif 'Score' in filtered_df.columns:
            filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
            sorted_df = filtered_df.sort_values(by='Score', ascending=False)
        else:
            sorted_df = filtered_df

        # Asegúrate de que el índice no esté fuera de los límites
        if offset >= len(sorted_df):
            return ('', 204) # No hay más mensajes que cargar

        displayed_df = sorted_df.iloc[offset:offset+24]

        # Si displayed_df está vacío después de iloc
        if displayed_df.empty:
            return ('', 204)

        # Preparar mensajes
        messages = []
        for _, row in displayed_df.iterrows():
            msg = {}
            msg['Embed'] = row.get('Embed', '')
            score = row.get('Score')
            msg['Score'] = round(score, 2) if pd.notna(score) and isinstance(score, (int, float)) else 'N/A'
            msg['Message ID'] = row.get('Message ID', '')
            msg['URL'] = row.get('URL', '')
            msg['Label'] = row.get('Label', None)
            messages.append(msg)

        return render_template('message_cards_partial.html', messages=messages)

    except Exception as e:
        print(f"Error en load_more: {str(e)}")
        return ('', 204)

@app.route('/label', methods=['POST'])
def label_message():
    """Etiqueta un mensaje con un valor específico."""
    try:
        data = request.json
        if not data or 'message_id' not in data or 'label' not in data:
            return jsonify(success=False, error="Datos incompletos"), 400

        message_id = int(data['message_id'])
        label = int(data['label'])
        updated = data_store.update_label(message_id, label)
        if not updated:
            return jsonify(success=False, error="Message ID no encontrado"), 404

        if not USE_POSTGRES:
            global _DATA_CACHE, _DATA_CACHE_TIME
            _DATA_CACHE = None
            _DATA_CACHE_TIME = 0

        return jsonify(success=True)
    except ValueError as e:
        return jsonify(success=False, error=f"Error en los datos de entrada: {str(e)}"), 400
    except Exception as e:
        print(f"Error inesperado en /label: {e}")
        return jsonify(success=False, error=f"Error inesperado en el servidor: {str(e)}"), 500

@app.route('/export_relevants', methods=['GET'])
def export_relevants():
    """Exporta los mensajes etiquetados como relevantes a un nuevo archivo CSV."""
    try:
        relevant_df = data_store.export_filtered_dataframe({'label': 1, 'sortBy': 'score'})
        if relevant_df.empty:
            return jsonify(success=True, message="No hay mensajes etiquetados como relevantes para exportar."), 200

        export_path = 'telegram_messages_relevant.csv'
        try:
            relevant_df.to_csv(export_path, index=False, encoding='utf-8')
            logger.info(f"Mensajes relevantes exportados localmente a {export_path}")
            
            # Intentar guardar en S3
            try:
                s3_client = get_s3_client()
                if s3_client.check_connection():
                    s3_client.upload_dataframe(relevant_df, 'telegram_messages_relevant.csv', format='csv')
                    logger.info("Mensajes relevantes exportados a S3")
                    return jsonify(success=True, message=f"Exportado localmente y a S3")
                else:
                    logger.warning("No se pudo conectar con S3, solo se exportó localmente")
                    return jsonify(success=True, message=f"Exportado localmente a {export_path}")
            except Exception as s3_error:
                logger.warning(f"Error al exportar a S3: {s3_error}, solo se exportó localmente")
                return jsonify(success=True, message=f"Exportado localmente a {export_path}")
                
        except Exception as e:
            logger.error(f"Error al guardar el archivo CSV de relevantes: {e}")
            return jsonify(success=False, error=f"Error al guardar el archivo exportado: {str(e)}"), 500

    except Exception as e:
        print(f"Error inesperado en /export_relevants: {e}")
        return jsonify(success=False, error=f"Error inesperado en el servidor: {str(e)}"), 500

@app.route('/channels', methods=['GET'])
def get_channels():
    """Devuelve la lista de canales disponibles."""
    try:
        channels = data_store.get_channels()
        return jsonify(success=True, channels=channels)
    except Exception as e:
        print(f"Error en /channels: {e}")
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/channels/suggest', methods=['POST'])
def suggest_channel():
    """Propuesta pública de canal (sin login). Envía correo al equipo."""
    try:
        data = request.get_json(silent=True) or {}
        username = normalize_username(data.get('username') or data.get('channel') or '')
        note = (data.get('note') or data.get('comment') or '').strip()
        contact_email = (data.get('email') or '').strip()

        if not username:
            return jsonify(success=False, error='Indica el nombre de usuario del canal (sin @)'), 400

        subject = f'[Monitor IA] Propuesta de canal: @{username}'
        body_lines = [
            'Se ha recibido una propuesta para incluir un canal en la monitorización.',
            '',
            f'Canal: @{username}',
            f'URL: https://t.me/{username}',
        ]
        if note:
            body_lines.extend(['', f'Comentario: {note}'])
        if contact_email:
            body_lines.extend(['', f'Contacto: {contact_email}'])
        body_lines.extend(['', f'Fecha: {datetime.utcnow().isoformat()}Z'])
        body = '\n'.join(body_lines)

        try:
            msg = MailMessage(
                subject=subject,
                recipients=[CHANNEL_SUGGEST_EMAIL],
                body=body,
            )
            if contact_email:
                msg.reply_to = contact_email
            mail.send(msg)
            logger.info('Propuesta de canal enviada: %s → %s', username, CHANNEL_SUGGEST_EMAIL)
        except Exception as mail_err:
            logger.exception('No se pudo enviar el correo de propuesta de canal')
            return jsonify(
                success=False,
                error=f'No se pudo enviar el correo. Comprueba la configuración SMTP/SES. ({mail_err})',
            ), 503

        return jsonify(
            success=True,
            message='Propuesta enviada. El equipo la revisará pronto.',
        )
    except Exception as e:
        logger.exception('Error en /api/channels/suggest')
        return jsonify(success=False, error=str(e)), 500


def _build_channel_graph_csvs():
    """Genera CSV de nodos (monitored_channels) y aristas (channel_edges)."""
    nodes_buf = BytesIO()
    edges_buf = BytesIO()

    if USE_POSTGRES:
        monitored = MonitoredChannel.query.order_by(MonitoredChannel.username).all()
        nodes_df = pd.DataFrame(
            [
                {
                    'username': row.username,
                    'title': row.title or row.username,
                    'status': row.status,
                    'discontinued': row.discontinued,
                    'source': row.source,
                    'last_error': row.last_error or '',
                    'last_scraped_at': row.last_scraped_at.isoformat() if row.last_scraped_at else '',
                }
                for row in monitored
            ]
        )
        edge_rows = []
        for edge in ChannelEdge.query.all():
            source_ch = db.session.get(Channel, edge.source_channel_id)
            target_ch = db.session.get(Channel, edge.target_channel_id)
            if not source_ch or not target_ch:
                continue
            edge_rows.append(
                {
                    'source_username': source_ch.username,
                    'source_title': source_ch.title,
                    'target_username': target_ch.username,
                    'target_title': target_ch.title,
                    'forward_count': edge.forward_count,
                    'last_seen_at': edge.last_seen_at.isoformat() if edge.last_seen_at else '',
                }
            )
        edges_df = pd.DataFrame(edge_rows)
    else:
        nodes_df = pd.DataFrame(columns=[
            'username', 'title', 'status', 'discontinued', 'source', 'last_error', 'last_scraped_at'
        ])
        edges_df = pd.DataFrame(columns=[
            'source_username', 'source_title', 'target_username', 'target_title',
            'forward_count', 'last_seen_at',
        ])

    if nodes_df.empty:
        nodes_df = pd.DataFrame(columns=[
            'username', 'title', 'status', 'discontinued', 'source', 'last_error', 'last_scraped_at'
        ])
    if edges_df.empty:
        edges_df = pd.DataFrame(columns=[
            'source_username', 'source_title', 'target_username', 'target_title',
            'forward_count', 'last_seen_at',
        ])

    nodes_df.to_csv(nodes_buf, index=False, encoding='utf-8-sig')
    edges_df.to_csv(edges_buf, index=False, encoding='utf-8-sig')
    nodes_buf.seek(0)
    edges_buf.seek(0)
    return nodes_buf, edges_buf


@app.route('/download_channel_graph', methods=['GET'])
def download_channel_graph():
    """Descarga ZIP con nodos (monitored_channels) y aristas (channel_edges)."""
    try:
        nodes_buf, edges_buf = _build_channel_graph_csvs()
        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('monitored_channels.csv', nodes_buf.getvalue())
            zf.writestr('channel_edges.csv', edges_buf.getvalue())
        zip_buf.seek(0)
        filename = f'channel_graph_{datetime.now().strftime("%Y%m%d_%H%M")}.zip'
        return send_file(
            zip_buf,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        logger.exception('Error en download_channel_graph')
        return jsonify(success=False, error=str(e)), 500

@app.route('/topics', methods=['GET'])
def get_topics():
    """Devuelve la lista de topics disponibles."""
    try:
        topics = load_topics_meta()
        return jsonify(success=True, topics=topics)
    except Exception as e:
        print(f"Error en /topics: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/admin/topic_titles', methods=['GET'])
@jwt_required()
@admin_required
def get_topic_titles():
    """Devuelve los titulos personalizados de topics."""
    try:
        titles = load_topic_titles()
        return jsonify(success=True, titles=titles)
    except Exception as e:
        print(f"Error en /admin/topic_titles: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/admin/topic_titles', methods=['POST'])
@jwt_required()
@admin_required
def set_topic_titles():
    """Actualiza los titulos personalizados de topics."""
    try:
        data = request.get_json(silent=True) or {}
        titles = data.get('titles')

        if not titles:
            topic_id = data.get('topic_id')
            title = data.get('title')
            if topic_id is None or not title:
                return jsonify(success=False, error="Faltan datos de titulo"), 400
            titles = {str(topic_id): title}

        existing = load_topic_titles()
        for key, value in titles.items():
            if value:
                existing[str(key)] = value

        save_topic_titles(existing)
        return jsonify(success=True, titles=existing)
    except Exception as e:
        print(f"Error en /admin/topic_titles: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/admin/run_topics', methods=['POST'])
@jwt_required()
@admin_required
def run_topics():
    """Ejecuta el análisis de topics manualmente (solo admins)."""
    try:
        result = process_topics()
        return jsonify(success=True, result=result)
    except Exception as e:
        print(f"Error en /admin/run_topics: {e}")
        return jsonify(success=False, error=str(e)), 500

def _parse_boolean_search(query: str):
    """
    Parsea una consulta con operadores AND, OR, NOT (case insensitive).
    Devuelve una lista de "grupos OR"; cada grupo es una lista de (op, term) con op en ('AND', 'NOT').
    Ej: "clima AND aemet" -> [[('AND', 'clima'), ('AND', 'aemet')]]
    "a OR b AND c" -> [[('AND', 'a')], [('AND', 'b'), ('AND', 'c')]]
    """
    if not query or not query.strip():
        return None
    tokens = query.strip().split()
    if not tokens:
        return None
    # Dividir por OR (precedencia más baja)
    or_groups = []
    current = []
    for t in tokens:
        if t.upper() == 'OR':
            or_groups.append(current)
            current = []
        else:
            current.append(t)
    if current:
        or_groups.append(current)

    # Dentro de cada grupo, dividir por AND; cada segmento puede ser "NOT term" o "term"
    result = []
    for group in or_groups:
        and_segments = []
        i = 0
        while i < len(group):
            if group[i].upper() == 'AND':
                i += 1
                continue
            seg = []
            while i < len(group) and group[i].upper() != 'AND':
                seg.append(group[i])
                i += 1
            if not seg:
                continue
            if seg[0].upper() == 'NOT':
                term = ' '.join(seg[1:]).strip() if len(seg) > 1 else ''
                if term:
                    and_segments.append(('NOT', term))
            else:
                and_segments.append(('AND', ' '.join(seg).strip()))
        if and_segments:
            result.append(and_segments)
    return result if result else None


def _apply_boolean_search_mask(parsed, text_series, title_series=None):
    """
    Aplica la consulta booleana parseada a las series de texto/título.
    Devuelve una máscara pandas (True = fila cumple la búsqueda).
    """
    if not parsed:
        return pd.Series([False] * len(text_series))
    combined = None
    for or_group in parsed:
        group_mask = None
        for op, term in or_group:
            if not term:
                continue
            term_lower = term.lower()
            term_escaped = re.escape(term_lower)
            m_text = text_series.astype(str).fillna('').str.lower().str.contains(term_escaped, na=False, regex=True)
            if title_series is not None and len(title_series) == len(text_series):
                m_title = title_series.astype(str).fillna('').str.lower().str.contains(term_escaped, na=False, regex=True)
                term_mask = m_text | m_title
            else:
                term_mask = m_text
            if op == 'NOT':
                term_mask = ~term_mask
            if group_mask is None:
                group_mask = term_mask
            else:
                group_mask = group_mask & term_mask
        if group_mask is not None:
            if combined is None:
                combined = group_mask
            else:
                combined = combined | group_mask
    if combined is None:
        return pd.Series([False] * len(text_series))
    return combined


def _apply_message_filters(df, filters):
    """Aplica los mismos filtros que filter_messages. Devuelve (sorted_df, None) o (None, (response, status))."""
    date_start_str = filters.get('dateStart')
    date_end_str = filters.get('dateEnd')
    filtered_df = df.copy()

    # Búsqueda en texto
    search_query = (filters.get('search') or filters.get('q') or '').strip()
    if search_query and 'Message Text' in df.columns:
        search_applied = False
        try:
            ensure_index_synced(df)
            ids = search_message_ids(search_query)
            if ids is not None:
                filtered_df = df[df['Message ID'].isin(ids)].copy()
                search_applied = True
        except Exception as e:
            logger.warning("FTS no disponible (%s); usando búsqueda por texto en pandas", e)
        if not search_applied:
            try:
                text_series = filtered_df['Message Text']
                title_series = filtered_df['Title'] if 'Title' in filtered_df.columns else None
                parsed = _parse_boolean_search(search_query)
                if parsed:
                    mask = _apply_boolean_search_mask(parsed, text_series, title_series)
                    filtered_df = filtered_df[mask].copy()
                else:
                    q_lower = search_query.lower()
                    text_series = filtered_df['Message Text'].astype(str).fillna('')
                    mask = text_series.str.lower().str.contains(re.escape(q_lower), na=False, regex=True)
                    if title_series is not None:
                        title_series = filtered_df['Title'].astype(str).fillna('')
                        mask = mask | title_series.str.lower().str.contains(re.escape(q_lower), na=False, regex=True)
                    filtered_df = filtered_df[mask].copy()
            except Exception as e:
                logger.warning("Error en búsqueda por texto: %s", e)

    # Filtro de Fecha
    if 'Date Sent' in filtered_df.columns and (date_start_str or date_end_str):
        try:
            filtered_df['Date Sent'] = pd.to_datetime(filtered_df['Date Sent'], errors='coerce').dt.tz_localize(None)
            if date_start_str:
                date_start = pd.to_datetime(date_start_str).normalize()
                filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() >= date_start]
            if date_end_str:
                date_end = pd.to_datetime(date_end_str).normalize() + pd.Timedelta(days=1)
                filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() < date_end]
        except Exception as e:
            print(f"Error en filtro de fechas: {str(e)}")
            pass

    # Filtro de Canal
    channel = filters.get('channel')
    if channel and 'Title' in filtered_df.columns:
        try:
            if isinstance(channel, list):
                filtered_df = filtered_df[filtered_df['Title'].isin(channel)]
            else:
                filtered_df = filtered_df[filtered_df['Title'] == channel]
        except Exception as e:
            return (None, (jsonify(success=False, error=f"Error en filtro de canal: {str(e)}"), 400))
    else:
        exclude_channel = filters.get('excludeChannel')
        if exclude_channel and 'Title' in filtered_df.columns:
            try:
                if isinstance(exclude_channel, list):
                    filtered_df = filtered_df[~filtered_df['Title'].isin(exclude_channel)]
                else:
                    filtered_df = filtered_df[filtered_df['Title'] != exclude_channel]
            except Exception as e:
                return (None, (jsonify(success=False, error=f"Error en filtro de exclusión de canal: {str(e)}"), 400))

    # Filtro de Topics
    topic_filter = filters.get('topics') or filters.get('topic')
    if topic_filter:
        try:
            filtered_df = attach_topic_assignments(filtered_df)
            topic_ids = []
            if isinstance(topic_filter, str):
                topic_ids = [t for t in topic_filter.split(',') if t]
            elif isinstance(topic_filter, list):
                topic_ids = topic_filter
            normalized = []
            for item in topic_ids:
                if isinstance(item, dict) and 'id' in item:
                    item = item['id']
                try:
                    normalized.append(int(item))
                except Exception:
                    continue
            if normalized and 'topic_id' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['topic_id'].isin(normalized)]
        except Exception as e:
            return (None, (jsonify(success=False, error=f"Error en filtro de topics: {str(e)}"), 400))

    # Score mín/máx
    score_min_str = filters.get('scoreMin')
    if score_min_str and 'Score' in filtered_df.columns:
        try:
            score_min = float(score_min_str)
            filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
            filtered_df = filtered_df[filtered_df['Score'] >= score_min]
        except Exception as e:
            return (None, (jsonify(success=False, error=f"Error en filtro de score mínimo: {str(e)}"), 400))
    score_max_str = filters.get('scoreMax')
    if score_max_str and 'Score' in filtered_df.columns:
        try:
            score_max = float(score_max_str)
            filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
            filtered_df = filtered_df[filtered_df['Score'] <= score_max]
        except Exception as e:
            return (None, (jsonify(success=False, error=f"Error en filtro de score máximo: {str(e)}"), 400))

    # Tipo de media
    media_type = filters.get('mediaType')
    if media_type and 'Media Type' in filtered_df.columns:
        try:
            types = [media_type] if isinstance(media_type, str) else media_type
            if types:
                filtered_df['Media Type'] = filtered_df['Media Type'].astype(str).str.lower()
                types_lower = [str(t).lower() for t in types]
                filtered_df = filtered_df[filtered_df['Media Type'].isin(types_lower)]
        except Exception as e:
            return (None, (jsonify(success=False, error=f"Error en filtro de tipo de media: {str(e)}"), 400))

    # Ordenar
    sort_by = filters.get('sortBy', 'score')
    try:
        if sort_by == 'views' and 'Views' in filtered_df.columns:
            filtered_df['Views'] = pd.to_numeric(filtered_df['Views'], errors='coerce')
            sorted_df = filtered_df.sort_values(by='Views', ascending=False)
        elif 'Score' in filtered_df.columns:
            filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
            sorted_df = filtered_df.sort_values(by='Score', ascending=False)
        else:
            sorted_df = filtered_df
    except Exception as e:
        sorted_df = filtered_df
    return (sorted_df, None)


@app.route('/filter_messages', methods=['POST'])
def filter_messages():
    """Filtra los mensajes según los criterios especificados."""
    try:
        filters = request.get_json(silent=True) or {}
        limit, offset = _parse_pagination(filters)
        paginated_df, total_messages = data_store.query_messages(filters, limit=limit, offset=offset)
        paginated_df = _attach_topic_titles_to_df(paginated_df)
        messages = _messages_from_dataframe(paginated_df)
        print(f"Total de mensajes filtrados: {len(messages)}")
        return jsonify(success=True, messages=messages, total_messages=total_messages)

    except Exception as e:
        print(f"Error crítico en /filter_messages: {e}")
        return jsonify(success=False, error=f"Error al procesar los filtros: {str(e)}"), 500


@app.route('/download_filtered_messages', methods=['POST'])
def download_filtered_messages():
    """Devuelve los mensajes filtrados (mismos criterios que filter_messages) como CSV."""
    try:
        filters = request.get_json(silent=True) or {}
        sorted_df = data_store.export_filtered_dataframe(filters)
        if sorted_df.empty:
            return jsonify(success=False, error="No hay datos"), 404
        sorted_df = _attach_topic_titles_to_df(sorted_df)
        export_columns = [
            'Message ID', 'Message Text', 'Title', 'Date Sent', 'Views', 'Score', 'Label', 'URL',
            'Media Type', 'topic_id', 'topic_title'
        ]
        cols = [c for c in export_columns if c in sorted_df.columns]
        export_df = sorted_df[cols] if cols else sorted_df
        buf = BytesIO()
        export_df.to_csv(buf, index=False, encoding='utf-8-sig')
        buf.seek(0)
        filename = f'filtered_messages_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        return send_file(buf, mimetype='text/csv', as_attachment=True, download_name=filename)
    except Exception as e:
        logger.exception("Error en download_filtered_messages")
        return jsonify(success=False, error=str(e)), 500


# Nueva ruta para renderizar el parcial HTML
@app.route('/render_partial', methods=['POST'])
def render_partial():
    """Renderiza el fragmento HTML de los mensajes."""
    try:
        data = request.json
        # Verificar si data es None antes de llamar a get
        if data is None:
            messages = []
        else:
            messages = data.get('messages', [])
            
        # Asegúrate de que Score se maneje correctamente si es 'N/A' u otro string
        for msg in messages:
            if isinstance(msg.get('Score'), str):
                 # Puedes decidir mostrar el string o un valor por defecto
                 pass # Ya viene como 'N/A' desde filter_messages
            elif isinstance(msg.get('Score'), (int, float)):
                 msg['Score'] = round(msg['Score'], 2)
            else:
                 msg['Score'] = 'N/A' # Valor por defecto

        return render_template('message_cards_partial.html', messages=messages)
    except Exception as e:
        print(f"Error en /render_partial: {e}")
        # Devuelve un error HTML o un estado 500
        return "<p>Error rendering messages.</p>", 500

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Faltan campos requeridos'}), 400
        
    if username in users_db:
        return jsonify({'error': 'El usuario ya existe'}), 400
        
    users_db[username] = {
        'password': generate_password_hash(password)
    }
    
    return jsonify({'message': 'Usuario registrado exitosamente'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Faltan campos requeridos'}), 400
        
    user = users_db.get(username)
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Credenciales inválidas'}), 401
        
    access_token = create_access_token(identity=username)
    return jsonify({'access_token': access_token}), 200

@app.route('/messages_over_time', methods=['GET', 'POST'])
def messages_over_time():
    """Devuelve el número de mensajes por día para el gráfico. Acepta los mismos filtros que el listado (incluido rango de fechas)."""
    try:
        filters = request.get_json(silent=True) if request.method == 'POST' else {}
        data = data_store.messages_over_time(filters or {})
        return jsonify(success=True, data=data)
    except Exception as e:
        logger.exception("Error en /messages_over_time")
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Endpoint para obtener los mensajes para el frontend."""
    try:
        if USE_POSTGRES:
            messages = data_store.get_messages_list(limit=500)
            return jsonify(success=True, messages=messages)

        df = load_data()
        if df.empty:
            return jsonify(success=True, messages=[])

        # Seleccionar las columnas necesarias
        required_columns = ['Message ID', 'Message Text', 'Title', 'Views', 'Average Views', 'Label']
        messages = []
        
        for _, row in df.iterrows():
            msg = {}
            for col in required_columns:
                if col in row:
                    msg[col] = row[col] if pd.notna(row[col]) else None
                else:
                    msg[col] = None
            messages.append(msg)

        return jsonify(success=True, messages=messages)

    except Exception as e:
        print(f"Error en /api/messages: {e}")
        return jsonify(success=False, error=str(e)), 500

if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    if os.environ.get("TOPIC_WORKER_AUTOSTART", "").lower() in {"1", "true", "yes"}:
        try:
            from topic_worker import run_worker_loop
            worker_thread = Thread(
                target=run_worker_loop,
                args=(Config.TOPIC_POLL_INTERVAL_MIN,),
                daemon=True,
            )
            worker_thread.start()
            print("Worker de topics iniciado en background")
        except Exception as e:
            print(f"No se pudo iniciar el worker de topics: {e}")
    # Considera usar debug=True solo para desarrollo, False para producción
    app.run(host='0.0.0.0', port=5001, debug=True)
