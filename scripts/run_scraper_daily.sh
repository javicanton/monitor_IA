#!/usr/bin/env bash
# Actualización diaria: mensajes recientes de todos los canales monitorizados.
# Pensado para cron (p. ej. 3:00 UTC).
#
# Uso:
#   ./scripts/run_scraper_daily.sh
#   SCRAPER_DAYS=2 SCRAPER_MAX_MESSAGES=400 ./scripts/run_scraper_daily.sh
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

# Ventana móvil: últimos N días (suficiente margen si el cron falla un día)
export SCRAPER_DAYS="${SCRAPER_DAYS:-3}"
export SCRAPER_MAX_MESSAGES="${SCRAPER_MAX_MESSAGES:-500}"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi

LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/scraper_daily_$(date -u +%Y%m%d).log"

echo "==> Escrapeo DIARIO → PostgreSQL ($(date -u -Iseconds))" | tee -a "$LOG_FILE"
echo "    Últimos ${SCRAPER_DAYS} días, máx ${SCRAPER_MAX_MESSAGES} msg/canal" | tee -a "$LOG_FILE"

cd backend
"$PYTHON" scraper.py \
  --postgres \
  --non-interactive \
  --days "$SCRAPER_DAYS" \
  --max-messages "$SCRAPER_MAX_MESSAGES" \
  "$@" >> "$LOG_FILE" 2>&1

echo "==> Fin escrapeo diario $(date -u -Iseconds)" >> "$LOG_FILE"
