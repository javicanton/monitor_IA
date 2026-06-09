# Acceso a datos (mensajes)

## Modos soportados

| Modo | Cuándo | Fuente |
|------|--------|--------|
| **PostgreSQL** | `DATABASE_URL` en `.env` | RDS / Postgres con tablas `channels`, `messages` |
| **Parquet + DuckDB** | Sin `DATABASE_URL` (por defecto) | `telegram_messages.parquet` en S3 |
| **Fallback JSON/CSV** | Si no hay parquet en S3 | `telegram_messages.json` o `.csv` en S3 → se genera parquet en caché |

## Staging / desarrollo en EC2

```bash
cd ~/monitor_IA
git checkout desarrollo
git pull
touch .env   # o cp .env.example .env
./scripts/deploy-staging.sh
curl -s http://localhost:8080/api/health
```

La primera petición de mensajes puede tardar (descarga JSON + generación de parquet).

### Credenciales AWS en Docker

- **Lectura de mensajes**: por defecto usa la **URL pública** de `telegram_messages.json` (igual que producción antigua).
- **Escritura en S3** (etiquetas, topics): añade en `.env`:
  ```bash
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  ```
- **No** dejes `AWS_ACCESS_KEY_ID=` vacío en `.env` (rompe boto3).
- El rol IAM de la instancia **no llega al contenedor** salvo configuración IMDS hop limit 2; para Docker usa claves en `.env` o URL pública.

## PostgreSQL (escalado)

1. Crear RDS PostgreSQL y definir en `.env`:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/monitor_ia
```

2. Importar dataset:

```bash
export DATABASE_URL=...
python scripts/import_dataset.py --path telegram_messages.csv
```

3. Redesplegar staging o funcional.

## Comprobar errores 502

```bash
docker ps | grep staging
docker logs monitoria-staging-backend --tail 50
curl -s http://localhost:8080/api/health
```
