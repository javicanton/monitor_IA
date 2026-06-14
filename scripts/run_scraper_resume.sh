#!/usr/bin/env bash
# Retomar el backfill histórico tras FloodWait o parada manual.
# Usa parámetros conservadores para no volver a saturar Telegram.
#
# Uso (en tmux):
#   tmux new -s scraper-resume
#   ./scripts/run_scraper_resume.sh
#
# El upsert no duplica mensajes ya guardados: es seguro relanzar.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export SCRAPER_FULL_HISTORY=1
export SCRAPER_MAX_MESSAGES="${SCRAPER_MAX_MESSAGES:-5000}"
export SCRAPER_CHANNEL_DELAY="${SCRAPER_CHANNEL_DELAY:-10}"

echo "==> Reanudar escrapeo COMPLETO (modo seguro, máx ${SCRAPER_MAX_MESSAGES} msg/canal)"
echo "    Para TODO el historial sin límite: ./scripts/run_scraper_unlimited.sh"
echo "    Pausa entre canales: ${SCRAPER_CHANNEL_DELAY}s"
echo "    Máx. mensajes/canal: ${SCRAPER_MAX_MESSAGES}"
echo "    Si hay FloodWait, el scraper esperará y continuará solo."
echo ""

# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env
scraper_print_status
echo ""

exec "${ROOT}/scripts/run_scraper_full.sh" "$@"
