#!/usr/bin/env bash
# Backfill SIN límite: todo el historial disponible de cada canal monitorizado.
# Puede tardar días y provocar FloodWait. Usar tmux obligatorio.
#
# Uso:
#   tmux new -s scraper-all
#   ./scripts/run_scraper_unlimited.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export SCRAPER_FULL_HISTORY=1
export SCRAPER_MAX_MESSAGES=0
export SCRAPER_CHANNEL_DELAY="${SCRAPER_CHANNEL_DELAY:-12}"
export SCRAPER_PG_BATCH="${SCRAPER_PG_BATCH:-250}"

echo "==> Escrapeo ILIMITADO (todo el historial por canal)"
echo "    SCRAPER_MAX_MESSAGES=0 → sin tope por canal"
echo "    Pausa entre canales: ${SCRAPER_CHANNEL_DELAY}s"
echo "    Lote PostgreSQL: ${SCRAPER_PG_BATCH} (menor = menos carga en la web)"
echo "    AVISO: la web en :8080 puede ir lenta; usa tmux y tail -f del log"
echo ""

# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env
scraper_print_status
echo ""

exec "${ROOT}/scripts/run_scraper_full.sh" --postgres-batch-size "$SCRAPER_PG_BATCH" "$@"
