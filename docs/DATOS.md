# Acceso a datos (mensajes)

## Modos soportados

| Modo | Cuándo | Fuente |
|------|--------|--------|
| **PostgreSQL** | `DATABASE_URL` en `.env` | RDS / Postgres — **recomendado para escalar** |
| **Parquet + DuckDB** | Sin `DATABASE_URL` (legacy) | `telegram_messages.parquet` en S3 |
| **Fallback JSON/CSV** | Si no hay parquet en S3 | `telegram_messages.json` en S3 |

Guía completa de migración a SQL: **`docs/SQL_MIGRATION.md`**

## Staging / desarrollo en EC2

```bash
cd ~/monitor_IA
git checkout desarrollo
git pull
cp .env.example .env   # editar DATABASE_URL si usas RDS
./scripts/deploy-staging.sh
curl -s http://localhost:8080/api/health
```

### Con PostgreSQL (recomendado)

```bash
export DATABASE_URL=postgresql://...
python3 scripts/init_postgres.py
python3 scripts/import_dataset.py --path /ruta/al/dataset.json
./scripts/deploy-staging.sh
```

### Sin PostgreSQL (legacy)

La primera petición puede tardar (descarga JSON + parquet en caché).

## Scraper → PostgreSQL

```bash
chmod +x scripts/run_scraper_postgres.sh
# Cron: 0 3 * * * /home/ubuntu/monitor_IA/scripts/run_scraper_postgres.sh
```

O manualmente:

```bash
cd backend
export DATABASE_URL=...
python3 scraper.py --postgres --non-interactive --days 7 --max-messages 500
```

## Credenciales AWS en Docker

- **Lectura legacy (sin SQL)**: URL pública de `telegram_messages.json`.
- **Con SQL**: mensajes desde RDS; S3 solo para topics/canales.
- **No** dejes `AWS_ACCESS_KEY_ID=` vacío en `.env` (rompe boto3).

## Comprobar errores

```bash
docker ps | grep staging
docker logs monitoria-staging-backend --tail 50
docker exec monitoria-staging-backend printenv DATABASE_URL
curl -s http://localhost:8080/api/health
```
