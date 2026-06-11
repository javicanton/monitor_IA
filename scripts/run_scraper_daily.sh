#!/usr/bin/env bash
# Actualización diaria: mensajes recientes de todos los canales monitorizados.
# Pensado para cron (3:00 UTC). No solapar con backfill en curso.
#
# Uso:
#   ./scripts/run_scraper_daily.sh
#   SCRAPER_DAYS=2 SCRAPER_MAX_MESSAGES=400 ./scripts/run_scraper_daily.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env
scraper_acquire_lock daily

# Ventana móvil: últimos N días (suficiente margen si el cron falla un día)
export SCRAPER_DAYS="${SCRAPER_DAYS:-3}"
export SCRAPER_MAX_MESSAGES="${SCRAPER_MAX_MESSAGES:-500}"
export SCRAPER_CHANNEL_DELAY="${SCRAPER_CHANNEL_DELAY:-5}"

LOG_FILE="${LOG_DIR}/scraper_daily_$(date -u +%Y%m%d).log"

echo "==> Escrapeo DIARIO → PostgreSQL ($(date -u -Iseconds))" | tee -a "$LOG_FILE"
echo "    Últimos ${SCRAPER_DAYS} días, máx ${SCRAPER_MAX_MESSAGES} msg/canal, pausa ${SCRAPER_CHANNEL_DELAY}s" | tee -a "$LOG_FILE"

cd backend
"$PYTHON" scraper.py \
  --postgres \
  --non-interactive \
  --days "$SCRAPER_DAYS" \
  --max-messages "$SCRAPER_MAX_MESSAGES" \
  "$@" >> "$LOG_FILE" 2>&1

echo "==> Fin escrapeo diario $(date -u -Iseconds)" >> "$LOG_FILE"
