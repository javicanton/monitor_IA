# Migración a PostgreSQL (millones de mensajes)

La app puede leer mensajes desde **PostgreSQL** cuando `DATABASE_URL` está definido. Sin esa variable sigue usando Parquet/JSON en S3 (modo legacy).

## Arquitectura objetivo

```
Telegram  →  scraper.py --postgres  →  RDS PostgreSQL
                                              ↓
EC2 Docker (staging/prod)  →  data_store_pg.py  →  API / filtros / UI (paginado)
```

- La **UI solo muestra una página** de resultados (p. ej. 24–48 mensajes).
- **Filtros, búsqueda y gráficos** se ejecutan en SQL sobre todo el dataset.
- El scraper hace **upsert**: mensajes nuevos + actualización de views/score; las **etiquetas (Label)** existentes se conservan.

---

## Qué tienes que hacer en AWS

### 1. Crear RDS PostgreSQL

| Parámetro | Recomendación |
|-----------|----------------|
| Motor | PostgreSQL 15 o 16 |
| Región | `eu-north-1` (misma que EC2 y S3) |
| Clase | `db.t4g.small` o superior si crece mucho |
| Almacenamiento | gp3, autoscaling activado |
| BD inicial | `monitor_ia` |
| Usuario | `monitoria` (o el que prefieras) |
| Acceso público | **No** |
| VPC | La misma que la instancia EC2 |

### 2. Security group de RDS

- **Inbound**: TCP **5432** solo desde el security group de la instancia EC2 (no desde `0.0.0.0/0`).

### 3. Variable en EC2 (`.env`)

En `~/monitor_IA/.env`:

```bash
DATABASE_URL=postgresql://monitoria:TU_PASSWORD@monitor-ia.xxxxx.eu-north-1.rds.amazonaws.com:5432/monitor_ia?sslmode=require
```

El contenedor backend recibe esta variable vía `docker-compose.deploy-test.yml`.

### 4. Entorno Python en EC2 (una vez)

Ubuntu 24+ no permite `pip install` global. Usa el venv del proyecto:

```bash
cd ~/monitor_IA
./scripts/setup-venv.sh
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
```

### 5. Inicializar tablas e índices (una vez)

```bash
python scripts/init_postgres.py
```

### 6. Importar el dataset actual (una vez)

Opción A — desde JSON en S3 (descargar y importar):

```bash
python3 scripts/download_dataset.py -o /tmp/telegram_messages.json
python3 scripts/import_dataset.py --path /tmp/telegram_messages.json
```

Opción B — desde CSV local si lo tienes:

```bash
python3 scripts/import_dataset.py --path backend/telegram_messages.csv
```

Comprueba filas:

```bash
python3 -c "
import os, sys
sys.path.insert(0,'backend')
from dotenv import load_dotenv; load_dotenv()
from pg_upsert import create_app
from models import Message, Channel
app = create_app()
with app.app_context():
    print('canales:', Channel.query.count(), 'mensajes:', Message.query.count())
"
```

### 7. Redesplegar staging con SQL

```bash
cd ~/monitor_IA
git checkout desarrollo && git pull
./scripts/deploy-staging.sh
curl -s http://localhost:8080/api/health
curl -s -X POST http://localhost:8080/api/filter_messages \
  -H 'Content-Type: application/json' -d '{"page":1}' | head -c 200
```

### 8. Scraper periódico → PostgreSQL

Primera vez: autorizar sesión Telethon en la instancia (modo interactivo).

```bash
cd ~/monitor_IA/backend
python3 scraper.py --days 7 --max-messages 500   # solo para login Telegram
```

Cron (cada noche):

```bash
chmod +x ~/monitor_IA/scripts/run_scraper_postgres.sh
crontab -e
# 3:00 UTC — nuevos mensajes y actualización de views/score
0 3 * * * /home/ubuntu/monitor_IA/scripts/run_scraper_postgres.sh >> /home/ubuntu/scraper.log 2>&1
```

Variables opcionales en `.env`:

```bash
SCRAPER_DAYS=7
SCRAPER_MAX_MESSAGES=500
```

---

## Resumen de modos

| Componente | Sin `DATABASE_URL` | Con `DATABASE_URL` |
|------------|-------------------|-------------------|
| Lectura API | DuckDB + Parquet/S3 | PostgreSQL |
| Scraper | CSV/JSON/S3 | `--postgres` → SQL |
| Búsqueda | FTS5 + LIKE | tsvector + ILIKE |
| Temas | `message_topics.csv` en S3 | Tabla `message_topics` (import manual por ahora) |

---

## Coste orientativo RDS

- `db.t4g.micro`: ~15–20 USD/mes (pruebas)
- `db.t4g.small`: ~25–35 USD/mes (millones de filas con índices)

---

## Troubleshooting

| Síntoma | Acción |
|---------|--------|
| `connection refused` a RDS | SG: puerto 5432 desde EC2 |
| `SSL required` | Añadir `?sslmode=require` a `DATABASE_URL` |
| Staging sigue en Parquet | Comprobar `docker exec monitoria-staging-backend printenv DATABASE_URL` |
| Scraper sin datos | `DATABASE_URL` en `.env` del host; usar `--postgres` |
| Disco lleno en build | `rm -f backend/telegram_messages.csv`; ver PR dockerignore |

---

## Próximos pasos (no incluidos aún)

- Escribir topics en `message_topics` desde `topic_processor` cuando hay SQL.
- RDS Proxy si hay muchas conexiones simultáneas.
- Réplica de lectura para informes pesados.
