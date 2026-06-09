#!/usr/bin/env bash
# Ejecuta el scraper guardando en PostgreSQL (cron / SSH en EC2).
# Requiere: DATABASE_URL, sesión Telethon autorizada, credentials.txt o TELEGRAM_API_*.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: falta .env con DATABASE_URL"
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL no está definido en .env"
  exit 1
fi

DAYS="${SCRAPER_DAYS:-7}"
MAX_MSG="${SCRAPER_MAX_MESSAGES:-500}"

echo "==> Scraper → PostgreSQL (últimos ${DAYS} días, máx ${MAX_MSG} msg/canal)"
cd backend
python3 scraper.py \
  --postgres \
  --non-interactive \
  --days "$DAYS" \
  --max-messages "$MAX_MSG" \
  "$@"
