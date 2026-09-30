#!/usr/bin/env bash
# Estado del scraper: proceso en curso, último log y conteos en PostgreSQL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env

echo "==> Proceso scraper"
if pgrep -af "scraper\.py" 2>/dev/null; then
  echo "    (en ejecución)"
else
  echo "    (no hay scraper.py corriendo)"
fi

echo ""
echo "==> Último log de backfill"
LATEST_FULL="$(ls -t "${LOG_DIR}"/scraper_full_*.log 2>/dev/null | head -1 || true)"
if [[ -n "$LATEST_FULL" ]]; then
  echo "    Archivo: $LATEST_FULL"
  if grep -q "19. Script completado" "$LATEST_FULL" 2>/dev/null; then
    echo "    Estado: TERMINADO"
  else
    echo "    Estado: EN CURSO o interrumpido"
  fi
  echo "    Últimas líneas:"
  tail -5 "$LATEST_FULL" | sed 's/^/      /'
  echo ""
  echo "    Ver en vivo: tail -f $LATEST_FULL"
else
  echo "    (sin logs scraper_full_*)"
fi

echo ""
echo "==> Último log diario (cron)"
LATEST_DAILY="${LOG_DIR}/scraper_daily_$(date -u +%Y%m%d).log"
if [[ -f "$LATEST_DAILY" ]]; then
  tail -3 "$LATEST_DAILY" | sed 's/^/    /'
else
  echo "    (sin log de hoy)"
fi

echo ""
scraper_print_status
