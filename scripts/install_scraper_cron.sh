#!/usr/bin/env bash
# Instala cron para escrapeo diario automático en la EC2 (03:00 UTC por defecto).
# Uso: ./scripts/install_scraper_cron.sh [--force]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORCE=false
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
  esac
done

# 03:00 UTC — en España (CEST) son las 05:00; en invierno (CET) las 04:00
CRON_TIME="${SCRAPER_CRON_TIME:-0 3 * * *}"
MARKER="# monitor_ia_scraper_daily"
DAILY_SCRIPT="${ROOT}/scripts/run_scraper_daily.sh"
LINE="${CRON_TIME} flock -n ${ROOT}/logs/scraper_daily.lock ${DAILY_SCRIPT} >> ${ROOT}/logs/scraper_cron.log 2>&1 ${MARKER}"

if crontab -l 2>/dev/null | grep -qF "$MARKER"; then
  if ! $FORCE; then
    echo "Cron ya instalado. Entrada actual:"
    crontab -l | grep -F "$MARKER" || true
    echo ""
    echo "Para reinstalar: $0 --force"
    echo "Para cambiar la hora: SCRAPER_CRON_TIME='0 4 * * *' $0 --force"
    exit 0
  fi
  crontab -l 2>/dev/null | grep -vF "$MARKER" | crontab - || true
fi

mkdir -p "${ROOT}/logs"
chmod +x "${DAILY_SCRIPT}" 2>/dev/null || true

(
  crontab -l 2>/dev/null | grep -vF "$MARKER" || true
  echo "${LINE}"
) | crontab -

echo "Cron instalado:"
crontab -l | grep -F "$MARKER"
echo ""
echo "Hora: ${CRON_TIME} (servidor en UTC; 03:00 UTC ≈ 05:00 hora de España en verano)"
echo "Script: ${DAILY_SCRIPT}"
echo "Logs diarios: ${ROOT}/logs/scraper_daily_YYYYMMDD.log"
echo "Log del cron: ${ROOT}/logs/scraper_cron.log"
echo ""
echo "Probar ahora: ${DAILY_SCRIPT}"
echo "Quitar: crontab -e  (borra la línea con ${MARKER})"
