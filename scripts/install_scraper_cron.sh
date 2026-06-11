#!/usr/bin/env bash
# Instala cron para escrapeo diario automático en la EC2.
# Uso: ./scripts/install_scraper_cron.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRON_TIME="${SCRAPER_CRON_TIME:-0 3 * * *}"
MARKER="# monitor_ia_scraper_daily"
LINE="${CRON_TIME} cd ${ROOT} && ${ROOT}/scripts/run_scraper_daily.sh"

if crontab -l 2>/dev/null | grep -qF "$MARKER"; then
  echo "Cron ya instalado. Entrada actual:"
  crontab -l | grep -F "$MARKER" || true
  echo ""
  echo "Para cambiar la hora: SCRAPER_CRON_TIME='0 4 * * *' $0"
  exit 0
fi

(
  crontab -l 2>/dev/null || true
  echo "${LINE} ${MARKER}"
) | crontab -

echo "Cron instalado:"
crontab -l | grep -F "$MARKER"
echo ""
echo "Hora por defecto: 03:00 UTC (todos los días)."
echo "Logs: ${ROOT}/logs/scraper_daily_YYYYMMDD.log"
echo "Quitar: crontab -e  (borra la línea con ${MARKER})"
