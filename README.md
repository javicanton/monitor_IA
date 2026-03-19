# Monitor IA — Telegram Analytics App

Aplicación web para analizar y etiquetar mensajes de alto rendimiento en canales de Telegram, con integración con AWS S3, modelado de temas (topics) y búsqueda full-text.

**Más información del proyecto:** [monitoria.org](https://monitoria.org/)

## Estado del proyecto

- **Frontend**: React 18 + Material-UI (v0.33), con filtros, gráficos (Recharts) y exportación.
- **Backend**: Flask en `backend/`, puerto 5001, con API REST, JWT, S3 y endpoints de administración.
- **Topics**: Worker asíncrono (pytopicgram) que genera temas sobre los mensajes y los guarda en S3; opcionalmente arranca en el mismo proceso con `TOPIC_WORKER_AUTOSTART`.
- **Búsqueda**: Índice FTS5 (SQLite) sobre mensajes para búsqueda full-text; se mantiene sincronizado con los datos cargados.
- **Despliegue**: Docker Compose (backend + frontend + topic_worker), y documentación para GitHub Actions + ECS en `docs/GITHUB_ACTIONS_SETUP.md`.

**En desarrollo**

- **Sistema de login**: Autenticación (email/contraseña, recuperación), roles admin/user y preparación para OAuth (Google, GitHub, Apple). Flujo de registro y verificación de email en curso.
- **Base de datos**: Migración a **PostgreSQL** (compatible con AWS RDS) para la API web: consultas paginadas, sin cargar el dataset en memoria. Script de ingesta desde CSV/Parquet (`scripts/import_dataset.py`). SQLite sigue disponible como fallback en desarrollo.

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
| Base de datos   | PostgreSQL (RDS) con `DATABASE_URL`; SQLite por defecto si no está definido |
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
└── docs/                    # Documentación (guías, OAuth, despliegue)
```

## Solución de problemas

- **S3**: Comprobar credenciales, región y nombre del bucket; opcionalmente URL pública del JSON.
- **Datos no cargan**: Revisar logs del backend y formato/nombres de archivos en S3.
- **Frontend no conecta**: Comprobar que el backend esté en el puerto correcto y CORS (`CORS_ORIGINS`).
- **Topics**: Revisar variables `TOPICS_*` y que el worker tenga acceso a S3 y al archivo de mensajes.

## Documentación adicional

En la carpeta **`docs/`** hay guías de despliegue, OAuth (Google/GitHub/Apple), referencia de variables de entorno y CI/CD. Esa carpeta no se sube al repo (está en `.gitignore`).

## Contribución

1. Fork del proyecto.
2. Rama para la feature (`git checkout -b feature/nueva-funcionalidad`).
3. Commit (`git commit -m 'Añadir nueva funcionalidad'`).
4. Push (`git push origin feature/nueva-funcionalidad`).
5. Abrir un Pull Request.

## Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](LICENSE) para más detalles.