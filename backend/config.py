import os
from datetime import timedelta

# PostgreSQL (AWS RDS compatible): usar DATABASE_URL.
# Ejemplo: postgresql://user:pass@host:5432/dbname
# Para desarrollo local: postgresql://localhost/monitor_ia
DATABASE_URL = os.environ.get('DATABASE_URL')

# Si no hay DATABASE_URL, se usa SQLite (solo para desarrollo sin PostgreSQL)
if DATABASE_URL:
    # RDS a veces devuelve URL con protocolo postgres://; SQLAlchemy necesita postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///telegram_app.db')

class Config:
    # Configuración básica de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
    
    # Base de datos: PostgreSQL vía DATABASE_URL o SQLite por defecto
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.environ.get("SQLALCHEMY_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("SQLALCHEMY_MAX_OVERFLOW", "10")),
    }
    
    # Configuración de JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # Configuración de correo electrónico (usando SES de AWS)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'email-smtp.eu-north-1.amazonaws.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('AWS_SES_ACCESS_KEY')
    MAIL_PASSWORD = os.environ.get('AWS_SES_SECRET_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Configuración de AWS
    AWS_REGION = os.environ.get('AWS_REGION', 'eu-north-1')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'monitoria-data')
    
    # Credenciales de AWS S3
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

    # DataStore (DuckDB + Parquet)
    DATASTORE_S3_PARQUET_KEY = os.environ.get('DATASTORE_S3_PARQUET_KEY', 'telegram_messages.parquet')
    DATASTORE_CACHE_DIR = os.environ.get('DATASTORE_CACHE_DIR', '/app/data/cache')
    DATASTORE_CACHE_TTL = int(os.environ.get('DATASTORE_CACHE_TTL', 1800))

    # Configuración de topics
    TOPIC_POLL_INTERVAL_MIN = int(os.environ.get('TOPIC_POLL_INTERVAL_MIN', 1440))
    TOPICS_S3_PREFIX = os.environ.get('TOPICS_S3_PREFIX', 'topics/')
    TOPICS_MODEL_KEY = os.environ.get('TOPICS_MODEL_KEY', 'topics/model.pkl')
    TOPICS_STATE_KEY = os.environ.get('TOPICS_STATE_KEY', 'topics/state.json')
    TOPICS_META_KEY = os.environ.get('TOPICS_META_KEY', 'topics/topics.json')
    TOPICS_ASSIGNMENTS_KEY = os.environ.get('TOPICS_ASSIGNMENTS_KEY', 'topics/message_topics.csv')
    TOPICS_SOURCE_KEY = os.environ.get('TOPICS_SOURCE_KEY', 'telegram_messages.json')
    TOPICS_TITLES_KEY = os.environ.get('TOPICS_TITLES_KEY', 'topics/topic_titles.json')
    TOPICS_RETRAIN_THRESHOLD = float(os.environ.get('TOPICS_RETRAIN_THRESHOLD', 0.3))
    TOPICS_MIN_NEW_MESSAGES = int(os.environ.get('TOPICS_MIN_NEW_MESSAGES', 10))
    TOPICS_OPENAI_KEY = os.environ.get('TOPICS_OPENAI_KEY')
    TOPICS_OPENAI_DOCS = int(os.environ.get('TOPICS_OPENAI_DOCS', 15))
    TOPICS_NUM_TOPICS = int(os.environ.get('TOPICS_NUM_TOPICS', 100))
    _TOPICS_SAMPLE_RATIO_RAW = os.environ.get('TOPICS_SAMPLE_RATIO')
    try:
        TOPICS_SAMPLE_RATIO = float(_TOPICS_SAMPLE_RATIO_RAW) if _TOPICS_SAMPLE_RATIO_RAW else None
    except (TypeError, ValueError):
        TOPICS_SAMPLE_RATIO = None
    # Ventana temporal: solo mensajes de los últimos N días (0 = sin límite). Pruebas: 7.
    TOPICS_DAYS_WINDOW = int(os.environ.get('TOPICS_DAYS_WINDOW', 0))
    # Si es true, ignora el estado incremental y reprocesa toda la ventana.
    TOPICS_RESET_STATE = os.environ.get('TOPICS_RESET_STATE', '').lower() in ('1', 'true', 'yes')
    
    # Configuración de CORS
    CORS_HEADERS = 'Content-Type'
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://app.monitoria.org,http://localhost:3000').split(',') 