#!/usr/bin/env bash
# Recuperar hueco de ingesta: ventana móvil mayor que el diario (cron = 3 días).
# Upsert: no duplica; actualiza views/score; conserva etiquetas.
#
# Uso (en tmux, recomendado):
#   tmux new -s scraper-catchup
#   ./scripts/run_scraper_catchup.sh
#
# Ejemplos:
#   SCRAPER_DAYS=14 ./scripts/run_scraper_catchup.sh
#   SCRAPER_DAYS=10 SCRAPER_MAX_MESSAGES=1000 ./scripts/run_scraper_catchup.sh
#
# Por defecto: últimos 14 días, 800 msg/canal (cubre un hueco de ~1–2 semanas).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env
# Mismo lock que el diario: no solapar con el cron de las 03:00 UTC
scraper_acquire_lock daily

export SCRAPER_DAYS="${SCRAPER_DAYS:-14}"
export SCRAPER_MAX_MESSAGES="${SCRAPER_MAX_MESSAGES:-800}"
export SCRAPER_CHANNEL_DELAY="${SCRAPER_CHANNEL_DELAY:-5}"

LOG_FILE="${LOG_DIR}/scraper_catchup_$(date -u +%Y%m%d_%H%M%S).log"
STATUS_FILE="${LOG_DIR}/scraper_last_status.json"
STARTED_AT="$(date -u -Iseconds)"

echo "==> Escrapeo CATCH-UP → PostgreSQL (${STARTED_AT})" | tee -a "$LOG_FILE"
echo "    Últimos ${SCRAPER_DAYS} días, máx ${SCRAPER_MAX_MESSAGES} msg/canal, pausa ${SCRAPER_CHANNEL_DELAY}s" | tee -a "$LOG_FILE"
echo "    Log: ${LOG_FILE}" | tee -a "$LOG_FILE"
echo "    (upsert: seguro relanzar; no pisa etiquetas)" | tee -a "$LOG_FILE"

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
  echo "==> Fin catch-up ${FINISHED_AT} (OK)" | tee -a "$LOG_FILE"
else
  STATUS="error"
  echo "==> Fin catch-up ${FINISHED_AT} (FALLÓ, código ${EXIT_CODE})" | tee -a "$LOG_FILE"
fi

cat > "$STATUS_FILE" <<EOF
{
  "status": "${STATUS}",
  "exit_code": ${EXIT_CODE},
  "mode": "catchup",
  "started_at": "${STARTED_AT}",
  "finished_at": "${FINISHED_AT}",
  "days": ${SCRAPER_DAYS},
  "max_messages": ${SCRAPER_MAX_MESSAGES},
  "log_file": "${LOG_FILE}"
}
EOF

exit "$EXIT_CODE"
