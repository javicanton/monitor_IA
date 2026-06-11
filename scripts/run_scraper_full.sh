#!/usr/bin/env bash
# Backfill histórico: todos los canales activos en monitored_channels.
# Puede tardar horas. Usar tmux: tmux new -s scraper-full
#
# Uso:
#   ./scripts/run_scraper_full.sh
#   SCRAPER_MAX_MESSAGES=15000 ./scripts/run_scraper_full.sh
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

# Por canal: hasta N mensajes hacia atrás en el tiempo (sin límite de días)
export SCRAPER_FULL_HISTORY=1
export SCRAPER_MAX_MESSAGES="${SCRAPER_MAX_MESSAGES:-10000}"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi

LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/scraper_full_${STAMP}.log"

echo "==> Escrapeo COMPLETO → PostgreSQL"
echo "    Canales: monitored_channels (activos, no descontinuados)"
echo "    Máx. mensajes/canal: ${SCRAPER_MAX_MESSAGES}"
echo "    Log: ${LOG_FILE}"
echo ""

cd backend
exec "$PYTHON" scraper.py \
  --postgres \
  --non-interactive \
  --full-history \
  --max-messages "$SCRAPER_MAX_MESSAGES" \
  "$@" 2>&1 | tee -a "$LOG_FILE"
