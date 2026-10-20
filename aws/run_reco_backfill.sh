#!/usr/bin/env bash
# Backfill RECO con el scraper de monitorIA, sin modificar su código.
# La lista sale de aws/reco_monitored.csv (--channels-file tiene prioridad).
# Si monitored_channels del esquema está vacía, aborta: no cae al CSV de S3 de monitorIA.
# Uso, en la EC2: ./aws/run_reco_backfill.sh
set -euo pipefail
ROOT="${ROOT:-$HOME/monitor_IA}"
cd "$ROOT"
[ -f .env.reco ] || { echo "Falta $ROOT/.env.reco (copiar aws/env.reco.example y citar la URL)"; exit 1; }
set -a
# shellcheck disable=SC1091
source .env.reco
set +a
# shellcheck disable=SC1091
source "$ROOT/aws/reco_guard.sh"
reco_exigir_search_path || exit 9
pub_antes="$(reco_contar_public)" || exit 9

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Falta .venv (ver docs/SCRAPER.md)"; exit 7; }
mkdir -p logs
exec 9>"logs/reco_backfill.lock"
flock -n 9 || { echo "Ya hay un backfill RECO en curso"; exit 8; }

CANALES="${1:-$ROOT/aws/reco_monitored.csv}"
[ -s "$CANALES" ] || { echo "ABORTO: falta $CANALES. Genera la lista con preparar_monitored.py"; exit 3; }

n_db="$(psql "$DATABASE_URL" -t -A -c "SELECT count(*) FROM monitored_channels WHERE status='active' AND discontinued=false" | tr -d '[:space:]')"
case "$n_db" in
  ''|*[!0-9]*|0)
    echo "ABORTO: monitored_channels activos=${n_db:-vacio}. Importa la semilla en este esquema. No se usa el CSV de S3."
    exit 3
    ;;
esac

INI="${RECO_VENTANA_INICIO:-2024-09-01}"
DAYS=$(( ( $(date -u +%s) - $(date -u -d "$INI" +%s) ) / 86400 + 2 ))
STAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG="logs/reco_backfill_${STAMP}.log"
echo "==> RECO: ${DAYS} días hacia atrás (desde ${INI}), ${n_db} canales en la base, lista ${CANALES}. Log: $LOG"

cd backend
set +e
"$PY" scraper.py --postgres --non-interactive \
  --channels-file "$CANALES" \
  --days "$DAYS" --max-messages 0 \
  --postgres-batch-size "${SCRAPER_PG_BATCH:-250}" 2>&1 | tee -a "../$LOG"
scraper_rc=${PIPESTATUS[0]}
set -e
cd "$ROOT"
pub_despues="$(reco_contar_public)" || exit 9
reco_exigir_public_igual "$pub_antes" "$pub_despues" || exit 10
exit "$scraper_rc"
