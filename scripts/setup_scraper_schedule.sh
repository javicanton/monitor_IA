#!/usr/bin/env bash
# Prepara escrapeo: cron diario 03:00 UTC + instrucciones para retomar backfill.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x scripts/run_scraper_*.sh scripts/install_scraper_cron.sh 2>/dev/null || true

echo "==> 1/2 Instalar cron diario (03:00 UTC)..."
"${ROOT}/scripts/install_scraper_cron.sh" "$@"

echo ""
echo "==> 2/2 Listo. Comandos útiles:"
echo ""
echo "  Retomar backfill (cuando expire el FloodWait):"
echo "    tmux new -s scraper-resume"
echo "    cd ${ROOT} && ./scripts/run_scraper_resume.sh"
echo ""
echo "  Probar escrapeo diario ahora:"
echo "    ./scripts/run_scraper_daily.sh"
echo ""
echo "  Ver log del cron:"
echo "    tail -f logs/scraper_daily_\$(date -u +%Y%m%d).log"
echo ""
echo "  Ver cron instalado:"
echo "    crontab -l | grep monitor_ia"
