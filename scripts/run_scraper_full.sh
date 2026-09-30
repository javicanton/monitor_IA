#!/usr/bin/env bash
# Backfill histórico: todos los canales activos en monitored_channels.
# Puede tardar horas. Usar tmux: tmux new -s scraper-full
#
# Uso:
#   ./scripts/run_scraper_full.sh
#   ./scripts/run_scraper_resume.sh   # tras FloodWait (más conservador)
#   SCRAPER_MAX_MESSAGES=15000 ./scripts/run_scraper_full.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env

# Por canal: hasta N mensajes hacia atrás en el tiempo (sin límite de días)
export SCRAPER_FULL_HISTORY=1
export SCRAPER_MAX_MESSAGES="${SCRAPER_MAX_MESSAGES:-10000}"
export SCRAPER_CHANNEL_DELAY="${SCRAPER_CHANNEL_DELAY:-5}"

STAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/scraper_full_${STAMP}.log"

echo "==> Escrapeo COMPLETO → PostgreSQL"
echo "    Canales: monitored_channels (activos, no descontinuados)"
echo "    Máx. mensajes/canal: ${SCRAPER_MAX_MESSAGES}"
echo "    Pausa entre canales: ${SCRAPER_CHANNEL_DELAY}s"
echo "    Log: ${LOG_FILE}"
echo "    Seguir en vivo: tail -f ${LOG_FILE}"
scraper_print_status
echo ""

cd backend
exec "$PYTHON" scraper.py \
  --postgres \
  --non-interactive \
  --full-history \
  --max-messages "$SCRAPER_MAX_MESSAGES" \
  "$@" 2>&1 | tee -a "$LOG_FILE"
