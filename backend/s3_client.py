import boto3
import pandas as pd
import json
import io
from botocore.exceptions import ClientError, NoCredentialsError
import os
from config import Config
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _build_boto3_s3_client():
    """
    Crea cliente S3 sin inyectar claves vacías (rompen la cadena de credenciales).
    Si no hay AWS_ACCESS_KEY_ID en el entorno, boto3 usará el rol IAM de la instancia
    cuando esté disponible (p. ej. EC2 sin Docker, o contenedor con hop limit IMDS >= 2).
    """
    kwargs = {"region_name": Config.AWS_REGION}
    access_key = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
    secret_key = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    session_token = (os.environ.get("AWS_SESSION_TOKEN") or "").strip()
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
        if session_token:
            kwargs["aws_session_token"] = session_token
    return boto3.client("s3", **kwargs)


class S3Client:
    def __init__(self):
        """Inicializa el cliente S3 con las credenciales de AWS."""
        try:
            self.s3_client = _build_boto3_s3_client()
            self.bucket_name = Config.S3_BUCKET
            logger.info(f"Cliente S3 inicializado para bucket: {self.bucket_name}")
        except NoCredentialsError:
            logger.error("No se encontraron credenciales de AWS")
            raise
        except Exception as e:
            logger.error(f"Error al inicializar cliente S3: {e}")
            raise

    def list_files(self, prefix=''):
        """Lista todos los archivos en el bucket S3 con un prefijo opcional."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                logger.info(f"Archivos encontrados en S3: {len(files)}")
                return files
            else:
                logger.info("No se encontraron archivos en el bucket")
                return []
                
        except ClientError as e:
            logger.error(f"Error al listar archivos en S3: {e}")
            raise

    def download_file(self, s3_key, local_path=None):
        """Descarga un archivo desde S3."""
        try:
            if local_path is None:
                local_path = s3_key.split('/')[-1]  # Usar solo el nombre del archivo
                
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Archivo descargado: {s3_key} -> {local_path}")
            return local_path
            
        except ClientError as e:
            logger.error(f"Error al descargar archivo {s3_key}: {e}")
            raise

    def get_file_content(self, s3_key):
        """Obtiene el contenido de un archivo desde S3 como string."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response['Body'].read().decode('utf-8')
            logger.info(f"Contenido obtenido del archivo: {s3_key}")
            return content
            
        except ClientError as e:
            logger.error(f"Error al obtener contenido del archivo {s3_key}: {e}")
            raise

    def load_csv_from_s3(self, s3_key):
        """Carga un archivo CSV desde S3 como DataFrame de pandas."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            df = pd.read_csv(io.BytesIO(response['Body'].read()))
            logger.info(f"CSV cargado desde S3: {s3_key}, filas: {len(df)}")
            return df
            
        except ClientError as e:
            logger.error(f"Error al cargar CSV {s3_key}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error al procesar CSV {s3_key}: {e}")
            raise

    def load_json_from_s3(self, s3_key):
        """Carga un archivo JSON desde S3."""
        try:
            content = self.get_file_content(s3_key)
            data = json.loads(content)
            logger.info(f"JSON cargado desde S3: {s3_key}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar JSON {s3_key}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error al cargar JSON {s3_key}: {e}")
            raise

    def upload_file(self, local_path, s3_key):
        """Sube un archivo local a S3."""
        try:
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key)
            logger.info(f"Archivo subido a S3: {local_path} -> {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Error al subir archivo {local_path}: {e}")
            raise

    def upload_dataframe(self, df, s3_key, format='csv'):
        """Sube un DataFrame a S3 en el formato especificado."""
        try:
            buffer = io.StringIO()
            
            if format.lower() == 'csv':
                df.to_csv(buffer, index=False)
            elif format.lower() == 'json':
                df.to_json(buffer, orient='records', indent=2)
            else:
                raise ValueError(f"Formato no soportado: {format}")
                
            buffer.seek(0)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=buffer.getvalue()
            )
            
            logger.info(f"DataFrame subido a S3: {s3_key} ({format})")
            return True
            
        except Exception as e:
            logger.error(f"Error al subir DataFrame a S3: {e}")
            raise

    def check_connection(self):
        """Verifica la conexión con S3."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info("Conexión con S3 exitosa")
            return True
        except ClientError as e:
            logger.error(f"Error de conexión con S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al verificar conexión S3: {e}")
            return False

# Función de utilidad para obtener el cliente S3
def get_s3_client():
    """Retorna una instancia del cliente S3."""
    return S3Client()
