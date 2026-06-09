# Telegram Analytics App

Aplicación web para analizar y etiquetar mensajes de alto rendimiento en canales de Telegram, con integración completa con AWS S3.

## Ramas

| Rama | Uso |
|------|-----|
| **`funcional`** | Versión estable y mostrable (app.monitoria.org) |
| **`desarrollo`** | Nuevas funcionalidades en curso |

Detalle: [docs/RAMAS.md](docs/RAMAS.md)

## 🚀 Características

- **Conexión automática con AWS S3**: Los datos se cargan automáticamente desde el bucket configurado
- **Sincronización en tiempo real**: Los cambios se guardan tanto localmente como en la nube
- **Sistema de filtros avanzado**: Filtra por fecha, canal, puntuación y tipo de contenido
- **Etiquetado de mensajes**: Marca mensajes como relevantes o no relevantes
- **Exportación de datos**: Exporta mensajes etiquetados como relevantes
- **Interfaz moderna**: Diseño responsive con Material-UI
- **Autenticación de usuarios**: Sistema de login y registro completo

## 🏗️ Arquitectura

- **Backend**: Flask (Python) con cliente S3 integrado y autenticación JWT
- **Frontend**: React con Material-UI y contexto de autenticación
- **Almacenamiento**: AWS S3 + archivos locales como fallback
- **Base de datos**: PostgreSQL para autenticación de usuarios
- **Autenticación**: JWT tokens con verificación de email

## 📋 Requisitos Previos

- Python 3.8+
- Node.js 16+
- PostgreSQL (para autenticación)
- Cuenta de AWS con acceso a S3
- Bucket S3 configurado con los datos de Telegram

## 🔧 Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd Telegram-app
```

### 2. Configurar el backend

```bash
# Instalar dependencias de Python
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```bash
# Configuración de Flask
SECRET_KEY=tu_secret_key_aqui_cambiar_en_produccion
JWT_SECRET_KEY=tu_jwt_secret_key_aqui_cambiar_en_produccion

# Configuración de AWS S3
AWS_ACCESS_KEY_ID=tu_access_key_id
AWS_SECRET_ACCESS_KEY=tu_secret_access_key
AWS_REGION=eu-north-1
S3_BUCKET=monitoria-data

# Configuración de base de datos PostgreSQL
DB_USER=admin
DB_PASSWORD=tu_password_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=telegram_app

# Configuración de correo electrónico (AWS SES)
MAIL_DEFAULT_SENDER=tu_email@ejemplo.com
AWS_SES_ACCESS_KEY=tu_ses_access_key
AWS_SES_SECRET_KEY=tu_ses_secret_key

# Configuración de CORS
CORS_ORIGINS=http://localhost:3000,http://app.monitoria.org

# Usuario administrador por defecto (opcional)
ADMIN_EMAIL=admin@monitoria.org
ADMIN_PASSWORD=admin123
ADMIN_NAME=Administrador
```

### 4. Inicializar la base de datos

```bash
# Crear tablas y usuario administrador
python init_db.py
```

### 5. Configurar el frontend

```bash
cd frontend
npm install
```

Crear un archivo `.env` en el directorio `frontend`:

```bash
REACT_APP_API_URL=http://localhost:5001
REACT_APP_S3_BUCKET=monitoria-data
REACT_APP_AWS_REGION=eu-north-1
```

## 🚀 Ejecución

### 1. Iniciar el backend

```bash
# Desde la raíz del proyecto
python app.py
```

El servidor se ejecutará en `http://localhost:5001`

### 2. Iniciar el frontend

```bash
cd frontend
npm start
```

La aplicación se abrirá en `http://localhost:3000`

## 🔐 Autenticación

### Usuario por defecto
- **Email**: admin@monitoria.org
- **Contraseña**: admin123
- **Rol**: Administrador

⚠️ **IMPORTANTE**: Cambia la contraseña del administrador después del primer login.

### Endpoints de autenticación
- `POST /api/auth/register` - Registro de usuarios
- `POST /api/auth/login` - Login de usuarios
- `GET /api/auth/me` - Obtener usuario actual (requiere token)
- `POST /api/auth/forgot-password` - Recuperar contraseña
- `POST /api/auth/reset-password/<token>` - Restablecer contraseña

## 🧪 Pruebas

### Probar conexión con S3
```bash
python test_s3_connection.py
```

### Probar autenticación
```bash
# Usar el usuario administrador por defecto
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@monitoria.org","password":"admin123"}'
```

## 📊 Estructura de Datos en S3

La aplicación espera los siguientes archivos en tu bucket S3:

- `telegram_messages.json` - Archivo principal con los mensajes
- `telegram_channels.csv` - Información de canales (opcional)
- `telegram_messages_relevant.csv` - Mensajes etiquetados como relevantes (se crea automáticamente)

### Formato del archivo JSON de mensajes:

```json
{
  "messages": [
    {
      "Message ID": 12345,
      "Title": "Nombre del Canal",
      "Date": "2024-01-01T10:00:00",
      "Date Sent": "2024-01-01T10:00:00",
      "Score": 8.5,
      "URL": "https://t.me/channel/123",
      "Embed": "Contenido del mensaje...",
      "Media Type": "text",
      "Views": 1000,
      "Label": null
    }
  ]
}
```

## 🔧 Solución de Problemas

### Error de conexión S3

- Verifica que las credenciales de AWS estén configuradas correctamente
- Asegúrate de que el bucket exista y sea accesible
- Verifica que la región sea correcta

### Datos no se cargan

- Revisa los logs del backend para errores específicos
- Verifica que los archivos en S3 tengan el formato correcto
- Comprueba que los nombres de archivo coincidan con lo esperado

### Frontend no se conecta

- Verifica que el backend esté ejecutándose en el puerto correcto
- Comprueba la configuración de CORS
- Revisa la consola del navegador para errores de red

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## 📞 Soporte

Si tienes problemas o preguntas:

1. Revisa la documentación
2. Busca en los issues existentes
3. Crea un nuevo issue con detalles del problema

## 🔄 Actualizaciones

La aplicación se actualiza automáticamente desde S3. Para forzar una actualización:

1. Usa el botón "Actualizar" en la interfaz
2. Reinicia el backend
3. Refresca la página del frontend
