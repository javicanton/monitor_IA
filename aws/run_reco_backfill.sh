#!/usr/bin/env bash
# Backfill RECO con el scraper de monitorIA, sin modificar su código.
# La lista sale de aws/reco_monitored.csv (--channels-file tiene prioridad).
# Si monitored_channels del esquema está vacía, aborta: no cae al CSV de S3 de monitorIA.
# Uso, en la EC2: ./aws/run_reco_backfill.sh [lista.csv]
# Si una pasada muere a mitad, la siguiente con el código nuevo puede saltar
# los canales ya cerrados (mensaje y grafo guardados):
#   RECO_RETOMAR_DESDE=2026-10-20T15:00:00Z ./aws/run_reco_backfill.sh lista.csv
# El instante es el arranque de la pasada que ya escribe el grafo por canal.
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

# Salta canales cuyo last_scraped_at es posterior al arranque indicado.
# No usar esto para retomar la pasada que murió antes de escribir el grafo:
# esos canales tienen mensajes, pero sus reenvíos no se guardaron.
if [ -n "${RECO_RETOMAR_DESDE:-}" ]; then
  case "$RECO_RETOMAR_DESDE" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) ;;
    *) echo "ABORTO: RECO_RETOMAR_DESDE debe ser YYYY-MM-DDTHH:MM:SSZ"; exit 3 ;;
  esac
  HECHOS="$(mktemp)"
  PENDIENTES="$(mktemp)"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -t -A \
    -c "SELECT lower(username) FROM monitored_channels WHERE last_scraped_at >= timestamptz '${RECO_RETOMAR_DESDE}'" \
    > "$HECHOS"
  n_pend="$("$PY" - "$HECHOS" "$CANALES" "$PENDIENTES" <<'PY'
import csv, sys
hechos = {ln.strip().lower() for ln in open(sys.argv[1], encoding="utf-8") if ln.strip()}
n = 0
with open(sys.argv[2], encoding="utf-8", newline="") as src, open(sys.argv[3], "w", encoding="utf-8", newline="") as dst:
    writer = csv.writer(dst)
    for row in csv.reader(src):
        if not row or not row[0].strip() or row[0].strip().lower() in hechos:
            continue
        writer.writerow(row)
        n += 1
print(n)
PY
)"
  echo "==> Retomar desde ${RECO_RETOMAR_DESDE}: ${n_pend} canales pendientes"
  if [ "${n_pend}" = "0" ]; then
    echo "Nada pendiente de bajar."
    pub_despues="$(reco_contar_public)" || exit 9
    reco_exigir_public_igual "$pub_antes" "$pub_despues" || exit 10
    exit 0
  fi
  CANALES="$PENDIENTES"
fi

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
