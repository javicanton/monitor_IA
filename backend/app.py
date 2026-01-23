from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
from datetime import datetime, timedelta
import json
from s3_client import get_s3_client
from auth import auth_bp
from models import db
from config import Config
import boto3
from botocore.exceptions import ClientError
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MESSAGES_LIMIT = 48
S3_BUCKET = os.environ.get('S3_BUCKET', 'monitoria-data')
S3_KEY = 'telegram_messages.json'

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensiones
jwt = JWTManager(app)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "http://192.168.1.142:3000", "http://app.monitoria.org", "http://13.60.219.71", "http://13.60.219.71:80", "http://13.60.219.71:8080"],
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

def load_data():
    """Carga los datos desde S3 y maneja posibles errores."""
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
                return df
        except Exception as e:
            logger.warning(f"No se pudo cargar desde URL pública: {e}")
        
        # Intentar cargar desde S3 con credenciales
        s3_client = get_s3_client()
        
        # Verificar conexión con S3
        if not s3_client.check_connection():
            logger.warning("No se pudo conectar con S3, intentando cargar desde archivo local")
            return load_data_local()
        
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
            return load_data_local()
        
        logger.info(f"Cargando datos desde S3: {messages_file}")
        
        # Cargar datos según el formato del archivo
        if messages_file.endswith('.json'):
            data = s3_client.load_json_from_s3(messages_file)
            df = pd.DataFrame(data['messages'])
        elif messages_file.endswith('.csv'):
            df = s3_client.load_csv_from_s3(messages_file)
        else:
            logger.error(f"Formato de archivo no soportado: {messages_file}")
            return load_data_local()
        
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
        return df

    except Exception as e:
        logger.error(f"Error al cargar datos desde S3: {e}")
        logger.info("Intentando cargar desde archivo local como fallback")
        return load_data_local()

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
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        print(f"Error al guardar en S3: {e}")
        return False

@app.route('/')
def index():
    """Renderiza la página principal con los mensajes ordenados por puntuación."""
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
        # Obtener los filtros de la URL
        filters = {
            'dateStart': request.args.get('dateStart'),
            'dateEnd': request.args.get('dateEnd'),
            'channel': request.args.get('channel'),
            'scoreMin': request.args.get('scoreMin'),
            'scoreMax': request.args.get('scoreMax'),
            'mediaType': request.args.get('mediaType'),
            'sortBy': request.args.get('sortBy', 'score')
        }

        df = load_data()
        if df.empty:
            return ('', 204) # No Content

        # Aplicar los mismos filtros que en /filter_messages
        filtered_df = df.copy()

        # Filtro de Fecha (Rango)
        if 'Date Sent' in filtered_df.columns:
            try:
                filtered_df['Date Sent'] = pd.to_datetime(filtered_df['Date Sent']).dt.tz_localize(None)
                
                if filters['dateStart']:
                    date_start = pd.to_datetime(filters['dateStart']).normalize()
                    filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() >= date_start]
                
                if filters['dateEnd']:
                    date_end = pd.to_datetime(filters['dateEnd']).normalize() + pd.Timedelta(days=1)
                    filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() < date_end]
            except Exception as e:
                print(f"Error en filtro de fechas: {str(e)}")
                return ('', 204)

        # Filtro de Canal (uno o varios)
        if filters['channel'] and 'Title' in filtered_df.columns:
            channel_filter = filters['channel']
            if isinstance(channel_filter, str) and ',' in channel_filter:
                channel_filter = [c for c in channel_filter.split(',') if c]
            if isinstance(channel_filter, list):
                filtered_df = filtered_df[filtered_df['Title'].isin(channel_filter)]
            else:
                filtered_df = filtered_df[filtered_df['Title'] == channel_filter]

        # Filtro de Puntuación (Score) Mínima
        if filters['scoreMin'] and 'Score' in filtered_df.columns:
            try:
                score_min = float(filters['scoreMin'])
                filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
                filtered_df = filtered_df[filtered_df['Score'] >= score_min]
            except:
                pass

        # Filtro de Puntuación (Score) Máxima
        if filters['scoreMax'] and 'Score' in filtered_df.columns:
            try:
                score_max = float(filters['scoreMax'])
                filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
                filtered_df = filtered_df[filtered_df['Score'] <= score_max]
            except:
                pass

        # Filtro de Tipo de Media
        if filters['mediaType'] and 'Media Type' in filtered_df.columns:
            try:
                filtered_df['Media Type'] = filtered_df['Media Type'].astype(str).str.lower()
                filtered_df = filtered_df[filtered_df['Media Type'] == str(filters['mediaType']).lower()]
            except:
                pass

        # Ordenar
        if filters['sortBy'] == 'views' and 'Views' in filtered_df.columns:
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

        df = load_data()
        if df.empty:
            return jsonify(success=False, error="No hay datos disponibles o error al cargar"), 404

        # Verifica si la columna 'Message ID' existe
        if 'Message ID' not in df.columns:
            return jsonify(success=False, error="La columna 'Message ID' no existe en el archivo JSON"), 500

        # Verifica si el message_id existe en el DataFrame
        if message_id not in df['Message ID'].values:
            print(f"Advertencia: message_id {message_id} no encontrado en el DataFrame para etiquetar.")
            return jsonify(success=True, message="Message ID no encontrado, pero operación ignorada.")

        # Actualiza el DataFrame
        if 'Label' not in df.columns:
            df['Label'] = pd.NA

        df.loc[df['Message ID'] == message_id, 'Label'] = label

        # Guarda en S3
        if not save_data(df):
            return jsonify(success=False, error="Error al guardar cambios en S3"), 500

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
        df = load_data()
        if df.empty:
            return jsonify(success=False, error="No hay datos disponibles o error al cargar"), 404

        # Verifica si la columna 'Label' existe
        if 'Label' not in df.columns:
            return jsonify(success=False, error="No hay columna 'Label' para filtrar mensajes relevantes"), 404

        # Filtra los mensajes etiquetados como relevantes (Label == 1)
        # Maneja posibles NaNs o tipos incorrectos en 'Label'
        try:
            # Intentar convertir a numérico (float), luego comparar con 1.0
            relevant_df = df[pd.to_numeric(df['Label'], errors='coerce') == 1.0]
        except Exception as e:
             print(f"Error al filtrar relevantes por Label: {e}")
             return jsonify(success=False, error="Error al procesar la columna 'Label'"), 500

        if relevant_df.empty:
            return jsonify(success=True, message="No hay mensajes etiquetados como relevantes para exportar."), 200 # O 404 si prefieres error

        # Guarda en un nuevo CSV tanto localmente como en S3
        export_path = 'telegram_messages_relevant.csv'
        try:
            # Guardar localmente
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
        df = load_data()
        if df.empty or 'Title' not in df.columns:
            return jsonify(success=True, channels=[])
        channels = sorted(df['Title'].fillna('Desconocido').replace('', 'Desconocido').unique().tolist())
        return jsonify(success=True, channels=channels)
    except Exception as e:
        print(f"Error en /channels: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/filter_messages', methods=['POST'])
def filter_messages():
    """Filtra los mensajes según los criterios especificados."""
    try:
        filters = request.json
        if not filters:
            return jsonify(success=False, error="No se proporcionaron filtros"), 400

        df = load_data()
        if df.empty:
            return jsonify(success=True, messages=[], total_messages=0)

        # --- Aplicar filtros ---
        filtered_df = df.copy()

        # Filtro de Fecha (Rango)
        date_start_str = filters.get('dateStart')
        date_end_str = filters.get('dateEnd')
        if 'Date Sent' in filtered_df.columns:
            try:
                # Asegurarnos de que la columna Date Sent esté en el formato correcto
                filtered_df['Date Sent'] = pd.to_datetime(filtered_df['Date Sent']).dt.tz_localize(None)
                
                if date_start_str:
                    # Convertir la fecha de inicio a datetime sin zona horaria
                    date_start = pd.to_datetime(date_start_str).normalize()
                    filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() >= date_start]
                
                if date_end_str:
                    # Convertir la fecha de fin a datetime sin zona horaria y añadir un día
                    date_end = pd.to_datetime(date_end_str).normalize() + pd.Timedelta(days=1)
                    filtered_df = filtered_df[filtered_df['Date Sent'].dt.normalize() < date_end]
                
            except Exception as e:
                print(f"Error en filtro de fechas: {str(e)}")
                return jsonify(success=False, error=f"Error en filtro de fechas: {str(e)}"), 400

        # Filtro de Canal (usando Title)
        channel = filters.get('channel')
        if channel and 'Title' in filtered_df.columns:
            try:
                if isinstance(channel, list):
                    filtered_df = filtered_df[filtered_df['Title'].isin(channel)]
                    print(f"Filtrado por canales: {channel}")
                else:
                    filtered_df = filtered_df[filtered_df['Title'] == channel]
                    print(f"Filtrado por canal: {channel}")
            except Exception as e:
                print(f"Error en filtro de canal: {str(e)}")
                return jsonify(success=False, error=f"Error en filtro de canal: {str(e)}"), 400

        # Filtro de Puntuación (Score) Mínima
        score_min_str = filters.get('scoreMin')
        if score_min_str and 'Score' in filtered_df.columns:
            try:
                score_min = float(score_min_str)
                filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
                filtered_df = filtered_df[filtered_df['Score'] >= score_min]
                print(f"Filtrado por score mínimo: {score_min}")
            except Exception as e:
                print(f"Error en filtro de score mínimo: {str(e)}")
                return jsonify(success=False, error=f"Error en filtro de score mínimo: {str(e)}"), 400

        # Filtro de Puntuación (Score) Máxima
        score_max_str = filters.get('scoreMax')
        if score_max_str and 'Score' in filtered_df.columns:
            try:
                score_max = float(score_max_str)
                filtered_df['Score'] = pd.to_numeric(filtered_df['Score'], errors='coerce')
                filtered_df = filtered_df[filtered_df['Score'] <= score_max]
                print(f"Filtrado por score máximo: {score_max}")
            except Exception as e:
                print(f"Error en filtro de score máximo: {str(e)}")
                return jsonify(success=False, error=f"Error en filtro de score máximo: {str(e)}"), 400

        # Filtro de Tipo de Media
        media_type = filters.get('mediaType')
        if media_type and 'Media Type' in filtered_df.columns:
            try:
                filtered_df['Media Type'] = filtered_df['Media Type'].astype(str).str.lower()
                filtered_df = filtered_df[filtered_df['Media Type'] == str(media_type).lower()]
                print(f"Filtrado por tipo de media: {media_type}")
            except Exception as e:
                print(f"Error en filtro de tipo de media: {str(e)}")
                return jsonify(success=False, error=f"Error en filtro de tipo de media: {str(e)}"), 400

        # Ordenar y preparar resultados
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
            print(f"Ordenado por: {sort_by}")
        except Exception as e:
            print(f"Error al ordenar los datos: {e}")
            sorted_df = filtered_df

        # Paginación
        try:
            # Asegurarnos de que page y per_page sean números válidos
            page = filters.get('page')
            per_page = filters.get('per_page')
            
            # Convertir a enteros, usando valores por defecto si no son válidos
            try:
                page = int(page) if page is not None else 1
            except (ValueError, TypeError):
                page = 1
                
            try:
                per_page = int(per_page) if per_page is not None else 24
            except (ValueError, TypeError):
                per_page = 24
                
            # Asegurarnos de que los valores sean positivos
            page = max(1, page)
            per_page = max(1, min(per_page, 100))  # Limitar a 100 mensajes por página
            
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page

            # Seleccionar solo los mensajes de la página actual
            paginated_df = sorted_df.iloc[start_idx:end_idx]
            print(f"Paginación: página {page}, {per_page} mensajes por página")
        except Exception as e:
            print(f"Error en paginación: {str(e)}")
            return jsonify(success=False, error=f"Error en paginación: {str(e)}"), 400

        # Seleccionar columnas y convertir a dict
        try:
            required_columns = ['Embed', 'Score', 'Message ID', 'URL', 'Label']
            messages = []
            for _, row in paginated_df.iterrows():
                msg = {}
                for col in required_columns:
                    if col in row:
                        msg[col] = row[col] if pd.notna(row[col]) else None
                    else:
                        msg[col] = None
                messages.append(msg)
            print(f"Total de mensajes filtrados: {len(messages)}")
        except Exception as e:
            print(f"Error al preparar mensajes: {str(e)}")
            return jsonify(success=False, error=f"Error al preparar mensajes: {str(e)}"), 400

        return jsonify(success=True, messages=messages, total_messages=len(sorted_df))

    except Exception as e:
        print(f"Error crítico en /filter_messages: {e}")
        return jsonify(success=False, error=f"Error al procesar los filtros: {str(e)}"), 500

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

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Endpoint para obtener los mensajes para el frontend."""
    try:
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
    # Considera usar debug=True solo para desarrollo, False para producción
    app.run(host='0.0.0.0', port=5001, debug=True)
