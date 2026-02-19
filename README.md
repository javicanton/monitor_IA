# Monitor IA — Telegram Analytics App

Aplicación web para analizar y etiquetar mensajes de alto rendimiento en canales de Telegram, con integración con AWS S3, modelado de temas (topics) y búsqueda full-text.

**Más información del proyecto:** [monitoria.org](https://monitoria.org/)

## Estado del proyecto

- **Frontend**: React 18 + Material-UI (v0.33), con autenticación, filtros, gráficos (Recharts) y exportación.
- **Backend**: Flask en `backend/`, puerto 5001, con API REST, JWT, S3, SQLite por defecto y endpoints de administración.
- **Topics**: Worker asíncrono (pytopicgram) que genera temas sobre los mensajes y los guarda en S3; opcionalmente arranca en el mismo proceso con `TOPIC_WORKER_AUTOSTART`.
- **Búsqueda**: Índice FTS5 (SQLite) sobre mensajes para búsqueda full-text; se mantiene sincronizado con los datos cargados.
- **Despliegue**: Docker Compose (backend + frontend + topic_worker), y documentación para GitHub Actions + ECS en [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md).

## Características

- **Conexión con AWS S3**: Carga de datos desde el bucket configurado (o URL pública de S3 como fallback).
- **Sincronización**: Cambios en etiquetas se persisten en S3 y en caché local.
- **Filtros**: Por fecha, canal, puntuación, tipo de contenido y ordenación.
- **Etiquetado**: Marcar mensajes como relevantes o no relevantes.
- **Exportación**: Exportar mensajes etiquetados como relevantes.
- **Temas (topics)**: Modelado automático de temas sobre el corpus; títulos editables por admin; worker configurable por intervalo y parámetros.
- **Búsqueda full-text**: Índice FTS5 para buscar en texto y título de mensajes.
- **Autenticación**: Login, registro, recuperación de contraseña y JWT; roles admin/user.
- **Interfaz**: Material-UI, responsive, con gráficos de mensajes en el tiempo.

## Arquitectura

| Capa            | Tecnología                                      |
|-----------------|-------------------------------------------------|
| Backend         | Flask (Python), Gunicorn en producción         |
| Frontend        | React 18, Material-UI, Recharts, Axios         |
| Datos           | AWS S3 (mensajes JSON/CSV) + caché en memoria  |
| Base de datos   | SQLite por defecto (`backend/instance/`)       |
| Autenticación   | JWT (Flask-JWT-Extended), bcrypt               |
| Topics          | Worker Python (pytopicgram), estado en S3     |
| Búsqueda        | SQLite FTS5 (`backend/instance/telegram_search.db`) |

## Requisitos previos

- Python 3.9+
- Node.js 16+
- Cuenta AWS con acceso a S3 (y opcionalmente SES para correo)
- Opcional: Docker y Docker Compose para ejecutar todo en contenedores

## Estructura del proyecto

```
monitor_IA/
├── backend/                 # API Flask
│   ├── app.py               # Aplicación principal y rutas
│   ├── auth.py              # Blueprint de autenticación
│   ├── config.py            # Configuración (env)
│   ├── models.py            # Modelos SQLAlchemy (User)
│   ├── s3_client.py         # Cliente S3
│   ├── search_index.py      # Índice FTS5 para búsqueda
│   ├── topic_processor.py  # Lógica de modelado de temas
│   ├── topic_worker.py     # Worker de topics (loop o --once)
│   ├── requirements.txt
│   ├── Dockerfile           # Imagen del backend
│   └── Dockerfile.worker   # Imagen del topic worker
├── frontend/                # React
│   ├── src/
│   │   ├── components/      # Dashboard, filtros, auth, gráficos
│   │   ├── contexts/        # AuthContext
│   │   ├── utils/           # api, axios, config
│   │   └── config.js
│   ├── package.json
│   ├── Dockerfile / Dockerfile.runtime / Dockerfile.build
│   └── ...
├── docker-compose.yml       # backend + topic_worker + frontend
├── docker-compose.worker.yml # solo topic_worker
├── init_db.py               # Inicializar DB y usuario admin (desde raíz)
├── test_s3_connection.py    # Probar conexión S3
├── requirements.txt         # Dependencias Python (raíz; scraper/topics)
└── GITHUB_ACTIONS_SETUP.md  # CI/CD con GitHub Actions y ECS
```

## Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd monitor_IA
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

Para el worker de topics (pytopicgram y dependencias extra):

```bash
pip install -r requirements-topics.txt   # desde backend/
# o desde raíz: requirements.txt incluye pytopicgram
```

### 3. Variables de entorno

Crear `.env` en la raíz o en `backend/` (el backend carga desde su directorio):

```bash
# Flask
SECRET_KEY=tu_secret_key_cambiar_en_produccion
JWT_SECRET_KEY=tu_jwt_secret_key_cambiar_en_produccion

# AWS S3
AWS_ACCESS_KEY_ID=tu_access_key_id
AWS_SECRET_ACCESS_KEY=tu_secret_access_key
AWS_REGION=eu-north-1
S3_BUCKET=monitoria-data

# Base de datos (por defecto SQLite en backend/instance/)
# SQLALCHEMY_DATABASE_URI=sqlite:///telegram_app.db

# Correo (AWS SES, opcional)
MAIL_DEFAULT_SENDER=tu_email@ejemplo.com
AWS_SES_ACCESS_KEY=...
AWS_SES_SECRET_KEY=...

# CORS
CORS_ORIGINS=http://localhost:3000,https://app.monitoria.org

# Admin por defecto
ADMIN_EMAIL=admin@monitoria.org
ADMIN_PASSWORD=admin123
ADMIN_NAME=Administrador

# Topics (worker)
TOPIC_POLL_INTERVAL_MIN=1440
TOPICS_NUM_TOPICS=50
TOPICS_SAMPLE_RATIO=0.3
# TOPIC_WORKER_AUTOSTART=true   # opcional: arrancar worker en el mismo proceso que app.py
```

### 4. Inicializar la base de datos

Desde la raíz del proyecto (con dependencias instaladas y `backend` en `PYTHONPATH` si hace falta):

```bash
# Opción: desde raíz, asegurando que Python encuentre el backend
export PYTHONPATH=backend
python init_db.py
```

O ejecutar la creación de tablas desde el propio backend la primera vez que arranque (`db.create_all()` en `app.py`). El script `init_db.py` además crea el usuario administrador por defecto.

### 5. Frontend

```bash
cd frontend
npm install
```

Crear `frontend/.env`:

```bash
REACT_APP_API_URL=http://localhost:5001
REACT_APP_S3_BUCKET=monitoria-data
REACT_APP_AWS_REGION=eu-north-1
```

## Ejecución

### Desarrollo

**Backend** (desde `backend/`):

```bash
cd backend
python app.py
```

Servidor en `http://localhost:5001`.

**Frontend**:

```bash
cd frontend
npm start
```

App en `http://localhost:3000`.

### Docker Compose

En la raíz:

```bash
docker-compose up --build
```

- Backend: puerto 5001 (interno).
- Frontend: puerto 80 (o `FRONTEND_PORT`).
- Topic worker: ejecuta `topic_worker.py` en intervalo configurado.

Solo el worker de topics:

```bash
docker-compose -f docker-compose.worker.yml up --build
```

## Autenticación

### Usuario por defecto

- **Email**: admin@monitoria.org  
- **Contraseña**: admin123  
- **Rol**: Administrador  

Cambia la contraseña después del primer acceso.

### Endpoints de autenticación (prefijo `/api/auth`)

- `POST /api/auth/register` — Registro
- `POST /api/auth/login` — Login
- `GET /api/auth/me` — Usuario actual (requiere token)
- `POST /api/auth/forgot-password` — Recuperar contraseña
- `POST /api/auth/reset-password/<token>` — Restablecer contraseña

### Endpoints de topics (admin)

- `GET /admin/topic_titles` — Listar títulos de temas (JWT)
- `POST /admin/topic_titles` — Actualizar títulos (JWT)
- `POST /admin/run_topics` — Disparar ejecución de topics (JWT)

## API principal (resumen)

- `GET /health` — Health check
- `GET /api/messages` — Mensajes para el frontend
- `POST /filter_messages` — Filtrar mensajes
- `POST /label` — Etiquetar mensaje (relevante / no relevante)
- `GET /export_relevants` — Exportar relevantes
- `GET /channels` — Listar canales
- `GET /topics` — Listar temas
- `GET /messages_over_time` — Datos para gráfico en el tiempo
- `POST /download_filtered_messages` — Descargar mensajes filtrados

## Datos en S3

La aplicación espera en el bucket:

- `telegram_messages.json` — Mensajes (formato con clave `messages`: array de objetos).
- Opcional: `telegram_channels.csv`, `telegram_messages_relevant.csv` (relevantes; se puede generar/actualizar desde la app).

El worker de topics usa por defecto `telegram_messages.json` y escribe en el prefijo `topics/` (estado, modelo, asignaciones, títulos, etc.).

## Pruebas rápidas

**Conexión S3** (desde raíz, con env cargado):

```bash
python test_s3_connection.py
```

**Login**:

```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@monitoria.org","password":"admin123"}'
```

## Despliegue y CI/CD

- **Docker**: Usar `docker-compose.yml` para backend, frontend y topic_worker.
- **GitHub Actions + ECS**: Ver [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) para secrets, ECR, ECS y rama `deploy-beta`.

## Solución de problemas

- **S3**: Comprobar credenciales, región y nombre del bucket; opcionalmente URL pública del JSON.
- **Datos no cargan**: Revisar logs del backend y formato/nombres de archivos en S3.
- **Frontend no conecta**: Comprobar que el backend esté en el puerto correcto y CORS (`CORS_ORIGINS`).
- **Topics**: Revisar variables `TOPICS_*` y que el worker tenga acceso a S3 y al archivo de mensajes.

## Contribución

1. Fork del proyecto.
2. Rama para la feature (`git checkout -b feature/nueva-funcionalidad`).
3. Commit (`git commit -m 'Añadir nueva funcionalidad'`).
4. Push (`git push origin feature/nueva-funcionalidad`).
5. Abrir un Pull Request.

## Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](LICENSE) para más detalles.

## Soporte

1. Revisar este README y [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md).
2. Buscar en los issues del repositorio.
3. Abrir un nuevo issue con detalles del problema.
