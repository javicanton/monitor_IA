# Acceso a datos (mensajes)

## Modos soportados

| Modo | Cuándo | Fuente |
|------|--------|--------|
| **PostgreSQL** | `DATABASE_URL` en `.env` | RDS / Postgres — **recomendado para escalar** |
| **Parquet + DuckDB** | Sin `DATABASE_URL` (legacy) | `telegram_messages.parquet` en S3 |
| **Fallback JSON/CSV** | Si no hay parquet en S3 | `telegram_messages.json` en S3 |

Guía completa de migración a SQL: **`docs/SQL_MIGRATION.md`**

## Staging / desarrollo en EC2 (puerto **8080**)

**No uses** `deploy-local-test.sh` para staging: ese script actualiza solo producción (puerto 80 / `app.monitoria.org`).

```bash
cd ~/monitor_IA
git checkout desarrollo
git pull origin desarrollo
./scripts/deploy-staging.sh --host-frontend   # recomendado en EC2
curl -s http://localhost:8080/api/health
```

La UI debe mostrar **v 1.0** (variable `REACT_APP_APP_VERSION` en el build).

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

Guía completa (cron, catch-up, venv, códigos de salida): **`docs/SCRAPER.md`**.

```bash
# Diario (cron 03:00 UTC, últimos 3 días)
./scripts/run_scraper_daily.sh

# Manual: recuperar hueco con ventana mayor (p. ej. tras días sin ingesta)
tmux new -s scraper-catchup
./scripts/run_scraper_catchup.sh
# SCRAPER_DAYS=14 SCRAPER_MAX_MESSAGES=800 ./scripts/run_scraper_catchup.sh
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
