## Telegram Scraper
# Import libraries
import argparse
import subprocess
import sys
import importlib.util
import csv
import io
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Union, cast
import asyncio
import json

def install_package(package_name):
    """Instala un paquete específico."""
    print(f"\nInstalando {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"✓ {package_name} instalado correctamente")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error al instalar {package_name}: {e}")
        return False

def check_and_install_dependencies():
    """Verifica e instala las dependencias necesarias."""
    required_packages = [
        'pandas',
        'telethon',
        'openpyxl',
        'python-dotenv',
        'asyncio',
        'boto3'
    ]
    
    # Primero actualizar pip
    print("\nActualizando pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    except subprocess.CalledProcessError:
        print("Advertencia: No se pudo actualizar pip, continuando...")

    # Verificar e instalar cada paquete individualmente
    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            if not install_package(package):
                print(f"\nError: No se pudo instalar {package}")
                print(f"Por favor, instala manualmente ejecutando:")
                print(f"pip install {package}")
                sys.exit(1)

# Verificar e instalar dependencias
check_and_install_dependencies()

# Importar las dependencias después de la instalación
import pandas as pd
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChatAdminRequiredError
from telethon.tl.types import Message, Channel, User
from telethon.tl.custom import Message as CustomMessage
from telethon.tl.types.messages import Messages
from telethon.tl.types.messages import ChannelMessages
from dotenv import load_dotenv

# Set the working directory to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno (.env en raíz del repo y en backend)
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_repo_root, ".env"))
load_dotenv()

DEFAULT_DAYS = 7
DEFAULT_MAX_MESSAGES = 500
DEFAULT_CHANNELS_S3_KEY = os.environ.get('TELEGRAM_CHANNELS_S3_KEY', 's3://monitoria-data/telegram_channels.csv')
DEFAULT_SESSION_PATH = os.environ.get('TELEGRAM_SESSION_PATH', '~/.telethon/monitorIA.session')

def _read_credentials_file(filename):
    try:
        credentials = {}
        with open(filename, 'r') as file:
            for line in file:
                key, value = line.strip().split('=')
                if key == 'API_ID':
                    try:
                        credentials[key] = int(value)
                    except ValueError:
                        print(f"Error: API_ID debe ser un número entero válido en {filename}")
                        return None
                else:
                    credentials[key] = value
        return credentials
    except Exception as e:
        print(f"Error al leer {filename}: {str(e)}")
        return None

def get_credentials_from_user():
    """Solicita las credenciales al usuario y las guarda en un archivo"""
    print("\nPrimera vez usando la aplicación. Necesitamos tus credenciales de Telegram.")
    print("Para obtenerlas:")
    print("1. Visita https://my.telegram.org/auth")
    print("2. Inicia sesión con tu número de teléfono")
    print("3. Ve a 'API development tools'")
    print("4. Crea una nueva aplicación")
    print("5. Copia tu api_id (número) y api_hash (cadena de texto)\n")
    
    while True:
        try:
            api_id = input("Ingresa tu API ID (número): ").strip()
            if not api_id:
                raise ValueError("El API ID no puede estar vacío")
            api_id = int(api_id)
            break
        except ValueError:
            print("Error: El API ID debe ser un número entero válido")
    
    while True:
        api_hash = input("Ingresa tu API Hash: ").strip()
        if not api_hash:
            print("Error: El API Hash no puede estar vacío")
            continue
        break
    
    # Guardar las credenciales en el archivo
    with open('credentials.txt', 'w') as f:
        f.write(f"API_ID={api_id}\n")
        f.write(f"API_HASH={api_hash}\n")
    
    print("\n✓ Credenciales guardadas correctamente en credentials.txt")
    return {'API_ID': api_id, 'API_HASH': api_hash}

def ask_use_existing_file(filename, file_description):
    """Pregunta al usuario si quiere usar un archivo existente"""
    if os.path.exists(filename):
        while True:
            respuesta = input(f"\n¿Quieres usar el archivo {filename} existente para {file_description}? (s/n): ").strip().lower()
            if respuesta in ['s', 'n']:
                return respuesta == 's'
            print("Por favor, responde 's' para sí o 'n' para no")

def load_credentials(filename='credentials.txt', non_interactive=False, api_id=None, api_hash=None):
    """
    Carga las credenciales desde un archivo o variables de entorno.
    Si no existen o el usuario no quiere usarlas, solicita las credenciales al usuario.
    """
    if api_id and api_hash:
        return {'API_ID': int(api_id), 'API_HASH': api_hash}

    env_api_id = os.environ.get('TELEGRAM_API_ID') or os.environ.get('API_ID')
    env_api_hash = os.environ.get('TELEGRAM_API_HASH') or os.environ.get('API_HASH')
    if env_api_id and env_api_hash:
        try:
            return {'API_ID': int(env_api_id), 'API_HASH': env_api_hash}
        except ValueError:
            print("Error: TELEGRAM_API_ID debe ser un número entero válido")

    if non_interactive:
        if os.path.exists(filename):
            return _read_credentials_file(filename)
        print("Error: Credenciales no disponibles para ejecución no interactiva.")
        return None

    # Preguntar si quiere usar el archivo existente
    if ask_use_existing_file(filename, "las credenciales de Telegram"):
        credentials = _read_credentials_file(filename)
        if credentials:
            return credentials
        return get_credentials_from_user()
    return get_credentials_from_user()

def get_user_input(days_arg=None, messages_arg=None, non_interactive=False):
    """Obtiene la configuración del usuario"""
    try:
        if days_arg is not None or messages_arg is not None:
            days = days_arg if days_arg is not None else DEFAULT_DAYS
            messages = messages_arg if messages_arg is not None else DEFAULT_MAX_MESSAGES
            return days, messages

        if non_interactive:
            return DEFAULT_DAYS, DEFAULT_MAX_MESSAGES

        days = input(f"Ingresa el número de días a scrapear (deja en blanco para usar {DEFAULT_DAYS} días): ")
        days = int(days) if days.strip() else DEFAULT_DAYS

        messages = input(f"Ingresa el número máximo de mensajes por canal (deja en blanco para usar {DEFAULT_MAX_MESSAGES}): ")
        messages = int(messages) if messages.strip() else DEFAULT_MAX_MESSAGES

        return days, messages
    except ValueError:
        print(f"Valor inválido. Usando valores por defecto ({DEFAULT_DAYS} días, {DEFAULT_MAX_MESSAGES} mensajes)")
        return DEFAULT_DAYS, DEFAULT_MAX_MESSAGES

def _parse_s3_uri(value):
    if not value or not isinstance(value, str):
        return None, None
    if not value.startswith("s3://"):
        return None, None
    without_scheme = value.replace("s3://", "", 1)
    if "/" not in without_scheme:
        return without_scheme, ""
    bucket, key = without_scheme.split("/", 1)
    return bucket, key

def _ensure_s3_bucket(bucket):
    if not bucket:
        return
    current = os.environ.get("S3_BUCKET")
    if current and current != bucket:
        print(f"Advertencia: S3_BUCKET='{current}' no coincide con '{bucket}', se usará '{bucket}'.")
    os.environ["S3_BUCKET"] = bucket

def load_channels_from_s3(s3_key):
    try:
        bucket, key = _parse_s3_uri(s3_key)
        if bucket:
            _ensure_s3_bucket(bucket)
            s3_key = key
        if not s3_key:
            print("Error: Key S3 de canales vacía.")
            return []

        from s3_client import get_s3_client
        s3_client = get_s3_client()
        content = s3_client.get_file_content(s3_key)
        reader = csv.reader(io.StringIO(content))
        channels = []
        for row in reader:
            if row and row[0].strip():
                channel = row[0].strip()
                if not channel.startswith('#'):
                    channels.append(channel)
        if channels:
            print(f"✓ Canales cargados desde S3: {s3_key} ({len(channels)})")
        return channels
    except Exception as e:
        print(f"No se pudo cargar {s3_key} desde S3: {e}")
        return []

def get_channels_from_user(channels_file=None, channels_s3_key=None, non_interactive=False):
    """Solicita los canales al usuario y los guarda en un archivo CSV"""
    if channels_file:
        bucket, key = _parse_s3_uri(channels_file)
        if key:
            channels_s3_key = channels_file
            channels_file = None

    s3_key = channels_s3_key or DEFAULT_CHANNELS_S3_KEY
    target_file = channels_file or 'telegram_channels.csv'

    if s3_key:
        channels = load_channels_from_s3(s3_key)
        if channels:
            return channels

    if channels_file:
        if not os.path.exists(channels_file):
            print(f"Error: No se encontró el archivo {channels_file}")
            return []
        channels = load_channels_from_csv(channels_file)
        if not channels:
            print(f"Error: El archivo {channels_file} no contiene canales válidos")
        return channels

    if non_interactive:
        if os.path.exists(target_file):
            return load_channels_from_csv(target_file)
        print("Error: No hay archivo telegram_channels.csv y no se pudo leer desde S3.")
        return []

    # Preguntar si quiere usar el archivo existente solo si existe
    if os.path.exists(target_file):
        if ask_use_existing_file(target_file, "la lista de canales"):
            channels = load_channels_from_csv(target_file)
            if channels:
                return channels
    
    # Si llegamos aquí, es porque el archivo no existe o el usuario no quiere usarlo
    print("\n¿Cómo quieres proporcionar los canales?")
    print("1. Ingresar un solo canal")
    print("2. Proporcionar un archivo CSV con la lista de canales")
    
    while True:
        try:
            opcion = input("\nElige una opción (1-2): ").strip()
            if opcion not in ['1', '2']:
                raise ValueError("Opción no válida")
            break
        except ValueError:
            print("Error: Debes elegir una opción entre 1 y 2")
    
    channels = []
    
    if opcion == '1':
        while True:
            channel = input("\nIngresa el nombre del canal (sin @): ").strip()
            if not channel:
                print("Error: El nombre del canal no puede estar vacío")
                continue
            channels.append(channel)
            break
    
    elif opcion == '2':
        while True:
            csv_path = input("\nIngresa la ruta al archivo CSV: ").strip()
            if not csv_path:
                print("Error: La ruta no puede estar vacía")
                continue
            if not os.path.exists(csv_path):
                print(f"Error: No se encontró el archivo {csv_path}")
                continue
            try:
                channels = load_channels_from_csv(csv_path)
                break
            except Exception as e:
                print(f"Error al leer el archivo CSV: {str(e)}")
                continue
    
    # Guardar los canales en el archivo
    with open('telegram_channels.csv', 'w', encoding='utf-8') as f:
        for channel in channels:
            f.write(f"{channel}\n")
    
    print(f"\n✓ Se han guardado {len(channels)} canales en telegram_channels.csv")
    return channels

def load_channels_from_csv(filename):
    """Carga los canales desde un archivo CSV"""
    channels = []
    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row and row[0].strip():  # Check if row is not empty and first element is not empty
                    channel = row[0].strip()
                    if not channel.startswith('#'):  # Ignorar líneas de comentario
                        channels.append(channel)
    except Exception as e:
        print(f"Error al leer {filename}: {str(e)}")
        return []
    return channels

def extract_channel_details(channel):
    return {
        'Channel ID': channel.id,
        'Username': channel.username,
        'Title': channel.title,
        'Description': getattr(channel, 'description', 'N/A'),
        'Photo': channel.photo,
        'Creation Date': getattr(channel, 'date', 'N/A'),
        'Verified': getattr(channel, 'verified', False),
        'Restricted': getattr(channel, 'restricted', False),
        'Members Count': getattr(channel, 'participants_count', 0)
    }

def extract_message_details(message):
    # Construct the URL
    url = f"https://t.me/s/{message.sender_id}/{message.id}"
    
    # Construct the Embed
    embed = f'<script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-post="{message.sender_id}/{message.id}" data-width="100%"></script>'
    
    return {
        'Message ID': message.id,
        'Message Text': message.text or '',
        'Date Sent': message.date,
        'Views': message.views or 0,
        'Forwarded From': getattr(message.forward, 'sender_id', None) if message.forward else None,
        'Reply To': message.reply_to_msg_id,
        'Mentions': message.mentioned,
        'Media': message.media,
        'Entities': message.entities,
        'Edit Date': message.edit_date,
        'Sender ID': message.sender_id,
        'URL': url,
        'Embed': embed
    }

def extract_media_details(media):
    media_type = type(media).__name__
    
    # Simplificar los tipos de medios
    if media_type == 'MessageMediaPhoto':
        simplified_type = 'Photo'
    elif media_type == 'MessageMediaDocument':
        # Verificar atributos específicos del documento
        if hasattr(media.document, 'attributes'):
            for attr in media.document.attributes:
                if hasattr(attr, 'video'):
                    simplified_type = 'Video'
                    break
                elif hasattr(attr, 'audio'):
                    if hasattr(attr, 'voice'):
                        simplified_type = 'Voice'
                    else:
                        simplified_type = 'Audio'
                    break
                elif hasattr(attr, 'sticker'):
                    simplified_type = 'Sticker'
                    break
                elif hasattr(attr, 'gif'):
                    simplified_type = 'GIF'
                    break
            else:
                simplified_type = 'Document'
    elif media_type == 'MessageMediaWebPage':
        simplified_type = 'Webpage'
    elif media_type == 'MessageMediaPoll':
        simplified_type = 'Poll'
    elif media_type == 'MessageMediaContact':
        simplified_type = 'Contact'
    elif media_type == 'MessageMediaGeo':
        simplified_type = 'Geo'
    elif media_type == 'MessageMediaGame':
        simplified_type = 'Game'
    else:
        simplified_type = media_type
    
    return {
        'Media Type': simplified_type,
        'Media Size': getattr(media, 'size', None),
        'Media Caption': getattr(media, 'caption', None)
    }

def load_existing_data(filename):
    try:
        return pd.read_csv(filename)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()

def load_existing_message_ids(filename):
    try:
        existing_data = pd.read_csv(filename)
        # Create a set of tuples (Username, Message ID) for fast lookup
        existing_ids = set(zip(existing_data['Username'], existing_data['Message ID']))
        return existing_ids
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return set()

def upload_dataset_to_s3(json_path, s3_key, csv_path=None, upload_csv=False, s3_csv_key=None):
    if not os.path.exists(json_path):
        print(f"Error: No se encontró el archivo {json_path} para subir a S3")
        return False
    try:
        from s3_client import get_s3_client
    except Exception as e:
        print(f"Error al importar cliente S3: {e}")
        return False

    try:
        s3_client = get_s3_client()
        s3_client.upload_file(json_path, s3_key)
        print(f"✓ Dataset subido a S3: {s3_key}")

        if upload_csv and csv_path:
            if not os.path.exists(csv_path):
                print(f"Advertencia: No se encontró {csv_path} para subir a S3")
            else:
                key = s3_csv_key or os.path.basename(csv_path)
                s3_client.upload_file(csv_path, key)
                print(f"✓ CSV subido a S3: {key}")
        return True
    except Exception as e:
        print(f"Error al subir a S3: {e}")
        return False

def parse_args():
    parser = argparse.ArgumentParser(description="Scraper de Telegram con subida opcional a S3")
    parser.add_argument("--channels-file", help="Ruta a CSV con la lista de canales")
    parser.add_argument("--channels-s3-key", help="Key S3 para el CSV de canales (default: telegram_channels.csv)")
    parser.add_argument("--days", type=int, help="Días a scrapear")
    parser.add_argument("--max-messages", type=int, help="Máximo de mensajes por canal")
    parser.add_argument("--upload-s3", action="store_true", help="Subir telegram_messages.json a S3")
    parser.add_argument("--upload-csv", action="store_true", help="Subir telegram_messages.csv a S3")
    parser.add_argument("--s3-key", default="telegram_messages.json", help="Key S3 para el JSON")
    parser.add_argument("--s3-csv-key", default="telegram_messages.csv", help="Key S3 para el CSV")
    parser.add_argument("--non-interactive", action="store_true", help="Modo no interactivo (SSH)")
    parser.add_argument("--api-id", type=int, help="API_ID de Telegram (opcional)")
    parser.add_argument("--api-hash", help="API_HASH de Telegram (opcional)")
    return parser.parse_args()

async def main(args):
    print("1. Iniciando script...")
    
    # Cargar credenciales
    print("2. Cargando credenciales...")
    creds = load_credentials(
        non_interactive=args.non_interactive,
        api_id=args.api_id,
        api_hash=args.api_hash
    )
    if not creds:
        print("Error: No se pudieron cargar las credenciales")
        return
    
    # Cargar canales
    print("3. Cargando lista de canales...")
    channels = get_channels_from_user(
        channels_file=args.channels_file,
        channels_s3_key=args.channels_s3_key,
        non_interactive=args.non_interactive
    )
    if not channels:
        print("Error: No se pudieron cargar los canales")
        return
    print(f"4. Se encontraron {len(channels)} canales para procesar")
    
    # Obtener configuración del usuario
    print("5. Configuración...")
    days_to_scrape, max_messages = get_user_input(
        days_arg=args.days,
        messages_arg=args.max_messages,
        non_interactive=args.non_interactive
    )
    time_days_ago = datetime.now(timezone.utc) - timedelta(days=days_to_scrape)
    print(f"6. Configuración: {days_to_scrape} días, {max_messages} mensajes por canal")
    
    # Cargar datos existentes
    print("7. Cargando datos existentes...")
    existing_messages = load_existing_data('telegram_messages.csv')
    existing_ids = load_existing_message_ids('telegram_messages.csv')
    
    # Crear cliente
    print("8. Creando cliente...")
    session_path = os.path.expanduser(DEFAULT_SESSION_PATH)
    session_dir = os.path.dirname(session_path)
    if session_dir and not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)
    client = TelegramClient(session_path, creds['API_ID'], creds['API_HASH'])
    
    try:
        # Conectar
        print("9. Conectando...")
        await client.connect()
        
        # Verificar autorización
        print("10. Verificando autorización...")
        if not await client.is_user_authorized():
            print("11. Necesitas autorizar el acceso:")
            print("   - Abre Telegram en tu dispositivo")
            print("   - Busca un mensaje con un código de verificación")
            print("   - Ingresa el código cuando se te solicite")
            if args.non_interactive:
                print("Error: No hay sesión autorizada y el modo es no interactivo.")
                return
            await client.start()
        
        print("12. Conexión exitosa!")
        
        all_data = []
        for channel in channels:
            try:
                print(f"Procesando canal: {channel}")
                channel_details = await client.get_entity(channel)
                messages = await client.get_messages(
                    channel,
                    limit=max_messages,
                    offset_date=time_days_ago
                )
                
                if not messages:
                    print(f"No se encontraron mensajes para el canal '{channel}'. Continuando con el siguiente.")
                    continue
                # Convert messages to list for easier handling
                messages_list = []
                if isinstance(messages, Message):
                    messages_list = [messages]
                else:
                    messages_list = list(messages)

                # Group messages by their date
                grouped_messages: Dict[str, List[Message]] = {}
                for message in messages_list:
                    if message and message.date:
                        date_str = message.date.strftime('%Y-%m-%d')
                        if date_str not in grouped_messages:
                            grouped_messages[date_str] = []
                        grouped_messages[date_str].append(message)

                # Calculate daily average views
                daily_average_views: Dict[str, float] = {}
                for date_str, daily_messages in grouped_messages.items():
                    views_list = [message.views for message in daily_messages if message.views is not None]
                    daily_average_views[date_str] = sum(views_list) / len(views_list) if views_list else 0

                # Contadores para mensajes
                mensajes_existentes = 0
                mensajes_nuevos = 0

                for message in messages_list:
                    if not message or not message.date:
                        continue
                        
                    data: Dict[str, Any] = {}
                    data.update(extract_channel_details(channel_details))
                    data.update(extract_message_details(message))
                    
                    # Verificar si el mensaje ya existe en el dataset
                    message_key = (data['Username'], message.id)
                    if message_key in existing_ids:
                        mensajes_existentes += 1
                        continue
        
                    # Update the URL and Embed columns using the channel's username
                    channel_username = data['Username']
                    if not channel_username:  # Si no hay username, usar el ID
                        channel_username = str(data['Channel ID'])
                    data['URL'] = f"https://t.me/s/{channel_username}/{message.id}"
                    data['Embed'] = f'<script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-post="{channel_username}/{message.id}" data-width="100%"></script>'
                    
                    date_str = message.date.strftime('%Y-%m-%d')
                    data['Average Views'] = daily_average_views.get(date_str, 0)
                    
                    # Calcular la diferencia con el promedio
                    if data['Average Views'] > 0:
                        data['Average Difference'] = (message.views or 0) - data['Average Views']
                        # Calcular el score como la proporción de views respecto a la media
                        data['Score'] = (message.views or 0) / data['Average Views']
                    else:
                        data['Average Difference'] = 0
                        data['Score'] = 0

                    # Añadir información de medios si existe
                    if message.media:
                        media_details = extract_media_details(message.media)
                        data.update(media_details)
                    else:
                        # Si no hay medios, establecer valores por defecto
                        data['Media Type'] = ''
                        data['Media Size'] = None
                        data['Media Caption'] = None
                    
                    # Inicializar Label como vacío
                    data['Label'] = ''

                    all_data.append(data)
                    mensajes_nuevos += 1

                print(f"✓ Canal '{channel}': {mensajes_existentes} mensajes existentes, {mensajes_nuevos} nuevos mensajes añadidos")

            except ChannelInvalidError:
                print(f"✗ Canal '{channel}' inválido o no accesible. Continuando con el siguiente.")
            except Exception as e:
                print(f"Error al procesar {channel}: {str(e)}")
                continue

        if all_data:
            print("13. Guardando datos...")
            # Convert the new data to a DataFrame
            new_data_df = pd.DataFrame(all_data)

            # Asegurarse de que las columnas coincidan entre los DataFrames
            if not existing_messages.empty:
                # Añadir columnas faltantes a existing_messages
                for col in new_data_df.columns:
                    if col not in existing_messages.columns:
                        existing_messages[col] = pd.NA
                
                # Añadir columnas faltantes a new_data_df
                for col in existing_messages.columns:
                    if col not in new_data_df.columns:
                        new_data_df[col] = pd.NA

            # Set the 'Message ID' and 'Username' columns as the index for both DataFrames
            if 'Message ID' in existing_messages.columns and 'Username' in existing_messages.columns:
                existing_messages.set_index(['Message ID', 'Username'], inplace=True)

            if 'Message ID' in new_data_df.columns and 'Username' in new_data_df.columns:
                new_data_df.set_index(['Message ID', 'Username'], inplace=True)

            # Actualizar todos los campos, incluyendo el score
            existing_messages.update(new_data_df)

            # Reset the index of the existing data
            existing_messages.reset_index(inplace=True)
            new_data_df.reset_index(inplace=True)

            # Concatenar los DataFrames asegurando que las columnas coincidan
            if existing_messages.empty:
                df = new_data_df
            else:
                # Asegurarse de que las columnas coincidan entre los DataFrames
                for col in new_data_df.columns:
                    if col not in existing_messages.columns:
                        existing_messages[col] = pd.NA
                
                for col in existing_messages.columns:
                    if col not in new_data_df.columns:
                        new_data_df[col] = pd.NA
                
                # Convertir columnas vacías a NA antes de la concatenación
                existing_messages = existing_messages.replace('', pd.NA)
                new_data_df = new_data_df.replace('', pd.NA)
                
                # Preservar las etiquetas existentes
                if 'Label' in existing_messages.columns:
                    # Crear un diccionario de etiquetas existentes
                    existing_labels = existing_messages.set_index(['Message ID', 'Username'])['Label'].to_dict()
                    
                    # Aplicar las etiquetas existentes a los nuevos mensajes
                    new_data_df['Label'] = new_data_df.apply(
                        lambda row: existing_labels.get((row['Message ID'], row['Username']), ''),
                        axis=1
                    )
                
                # Concatenar los DataFrames
                df = pd.concat([existing_messages, new_data_df], ignore_index=True, sort=False)
            
            # Eliminar duplicados
            df.drop_duplicates(subset=['Message ID', 'Username'], inplace=True, keep='first')

            # Recalcular el score para todos los mensajes
            df['Score'] = df.apply(
                lambda row: (row['Views'] or 0) / row['Average Views'] if row['Average Views'] > 0 else 0,
                axis=1
            )
                
            # Convertir columnas específicas a entero de manera segura
            columnas_a_convertir = ['Message ID', 'Views', 'Members Count', 'Forwards', 'Replies']
            for columna in columnas_a_convertir:
                if columna in df.columns and df[columna].dtype not in ['datetime64[ns]', 'timedelta64[ns]']:
                    df[columna] = pd.to_numeric(df[columna], errors='coerce').fillna(0).astype(int)

            # Asegurar que las columnas de texto no sean nulas
            columnas_texto = ['Message Text', 'URL', 'Embed', 'Label', 'Media Type', 'Media Caption']
            for columna in columnas_texto:
                if columna in df.columns:
                    df[columna] = df[columna].fillna('')

            # Eliminar columnas vacías o no deseadas
            columnas_a_eliminar = []  # Ya no eliminamos ninguna columna
            for columna in columnas_a_eliminar:
                if columna in df.columns:
                    df = df.drop(columns=[columna])

            df.to_csv('telegram_messages.csv', index=False, encoding='utf-8')
            print("14. Datos guardados en telegram_messages.csv")

            # Guardar también en JSON
            print("15. Guardando datos en JSON...")
            
            # Crear una copia del DataFrame para JSON
            df_json = df.copy()
            
            # Eliminar columnas que no son serializables
            columns_to_drop = ['Photo', 'Media', 'Entities']
            for col in columns_to_drop:
                if col in df_json.columns:
                    df_json = df_json.drop(columns=[col])
            
            # Convertir las fechas a string ISO
            for col in ['Date Sent', 'Creation Date', 'Edit Date']:
                if col in df_json.columns:
                    df_json[col] = df_json[col].astype(str)
            
            # Convertir el DataFrame a un formato JSON amigable
            json_data = {
                'messages': df_json.to_dict(orient='records')
            }
            
            # Guardar en JSON con formato legible
            with open('telegram_messages.json', 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
            print("16. Datos guardados en telegram_messages.json")

            # Convertir todas las columnas de fecha a datetime sin zona horaria
            for col in ['Date Sent', 'Creation Date', 'Edit Date']:
                if col in df.columns:
                    try:
                        # Primero convertir a datetime si no lo es
                        df[col] = pd.to_datetime(df[col])
                        # Luego eliminar la zona horaria
                        df[col] = df[col].dt.tz_localize(None)
                    except (AttributeError, TypeError):
                        # Si la columna no tiene zona horaria o ya está en el formato correcto
                        df[col] = pd.to_datetime(df[col])
            
            # Guardar en Excel
            with pd.ExcelWriter('telegram_data.xlsx', engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Messages', index=False)
            print("17. Datos guardados en telegram_data.xlsx")
            
            if args.upload_s3:
                print("18. Subiendo dataset a S3...")
                upload_dataset_to_s3(
                    json_path='telegram_messages.json',
                    s3_key=args.s3_key,
                    csv_path='telegram_messages.csv',
                    upload_csv=args.upload_csv,
                    s3_csv_key=args.s3_csv_key
                )
        else:
            print("13. No hay datos para guardar")
        print("18. Cerrando conexión...")
        try:
            if client:
                await client.disconnect()
        except:
            pass
        print("19. Script completado!")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == '__main__':
    print("Iniciando ejecución...")
    args = parse_args()
    asyncio.run(main(args))