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
STATUS_FILE="${LOG_DIR}/scraper_last_status.json"
STARTED_AT="$(date -u -Iseconds)"

echo "==> Escrapeo DIARIO → PostgreSQL (${STARTED_AT})" | tee -a "$LOG_FILE"
echo "    Últimos ${SCRAPER_DAYS} días, máx ${SCRAPER_MAX_MESSAGES} msg/canal, pausa ${SCRAPER_CHANNEL_DELAY}s" | tee -a "$LOG_FILE"

set +e
cd backend
"$PYTHON" scraper.py \
  --postgres \
  --non-interactive \
  --days "$SCRAPER_DAYS" \
  --max-messages "$SCRAPER_MAX_MESSAGES" \
  "$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

FINISHED_AT="$(date -u -Iseconds)"
if [[ "$EXIT_CODE" -eq 0 ]]; then
  STATUS="ok"
  echo "==> Fin escrapeo diario ${FINISHED_AT} (OK)" | tee -a "$LOG_FILE"
else
  STATUS="error"
  echo "==> Fin escrapeo diario ${FINISHED_AT} (FALLÓ, código ${EXIT_CODE})" | tee -a "$LOG_FILE"
fi

# Estado legible para scraper_status.sh / operadores (sin secretos)
cat > "$STATUS_FILE" <<EOF
{
  "status": "${STATUS}",
  "exit_code": ${EXIT_CODE},
  "mode": "daily",
  "started_at": "${STARTED_AT}",
  "finished_at": "${FINISHED_AT}",
  "days": ${SCRAPER_DAYS},
  "max_messages": ${SCRAPER_MAX_MESSAGES},
  "log_file": "${LOG_FILE}"
}
EOF

exit "$EXIT_CODE"
