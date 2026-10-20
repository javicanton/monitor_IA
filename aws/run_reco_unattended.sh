#!/usr/bin/env bash
# Fases del corpus RECO desacopladas de la sesión SSH.
#   ./aws/run_reco_unattended.sh A|B|status
# A y B vuelven al momento. El trabajo sigue con nohup setsid.
# status se puede consultar al día siguiente, sin la sesión de hoy.
set -euo pipefail
ROOT="${ROOT:-$HOME/monitor_IA}"
cd "$ROOT"
mkdir -p logs out
FASE="${1:-}"

estado() {
  printf '{"fase":"%s","paso":"%s","hora_utc":"%s"}\n' \
    "$FASE" "$1" "$(date -u +%FT%TZ)" > logs/reco_status.json
}

if [ "$FASE" = "status" ]; then
  if [ -f logs/reco_status.json ]; then
    cat logs/reco_status.json
  else
    echo "sin estado"
  fi
  log=""
  if [ -d logs ]; then
    log="$(find logs -maxdepth 1 -type f \( -name 'reco_fase_*.log' -o -name 'reco_backfill_*.log' \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 { print $2 }')"
  fi
  if [ -n "${log:-}" ]; then
    echo "-- ${log}"
    tail -n 5 "$log" || true
  fi
  exit 0
fi

[ "$FASE" = "A" ] || [ "$FASE" = "B" ] || { echo "Uso: $0 A|B|status"; exit 2; }

if [ -z "${RECO_DETACHED:-}" ]; then
  command -v setsid >/dev/null || { echo "Falta setsid"; exit 1; }
  export RECO_DETACHED=1
  log="logs/reco_fase_${FASE}_$(date -u +%Y%m%d_%H%M%S).log"
  nohup setsid "$0" "$FASE" >>"$log" 2>&1 &
  echo "Fase $FASE lanzada en segundo plano (PID $!). Log: $log"
  echo "Puedes cerrar la sesión. Mañana: cd ~/monitor_IA && ./aws/run_reco_unattended.sh status"
  exit 0
fi

on_err() {
  local rc=$?
  trap - ERR
  if [ "$rc" -eq 10 ]; then
    estado "ALERTA_public_cambio"
  else
    estado "error"
  fi
  exit "$rc"
}
trap on_err ERR

[ -f .env.reco ] || { echo "Falta .env.reco"; estado "abortado_sin_env"; exit 1; }
set -a
# shellcheck disable=SC1091
source .env.reco
set +a
# shellcheck disable=SC1091
source "$ROOT/aws/reco_guard.sh"

exec 8>"logs/reco_fase.lock"
flock -n 8 || { echo "Ya hay una fase RECO en curso"; estado "abortado_lock"; exit 8; }

reco_exigir_search_path || { estado "abortado_search_path"; exit 9; }
pub_antes="$(reco_contar_public)" || { estado "abortado_conteo"; exit 9; }

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Falta .venv (ver docs/SCRAPER.md)"; estado "abortado_venv"; exit 7; }
"$PY" -c "import yaml" || {
  echo "Falta PyYAML en .venv. Instala con: $PY -m pip install 'PyYAML>=6.0'"
  estado "abortado_yaml"
  exit 7
}

estado "backfill"
if [ "$FASE" = "B" ]; then
  # La semilla ya está en reco.messages. La ronda 1 solo baja los canales nuevos.
  ./aws/run_reco_backfill.sh "$ROOT/aws/reco_monitored_ronda1.csv"
else
  ./aws/run_reco_backfill.sh
fi
estado "filtro"
"$PY" aws/reco_filtro_db.py --lexico metodologia/02_lexico.yaml --version "${LEXICO_VERSION:-v0.1}"
estado "exportar"
"$PY" aws/reco_filtro_db.py --export "out/corpus_bruto_${FASE}.csv"
"$PY" aws/reco_filtro_db.py --export "out/corpus_reco_${FASE}.csv" --solo-incluidos
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "\copy (SELECT s.username AS origen, t.username AS destino, e.forward_count AS peso FROM channel_edges e JOIN channels s ON s.id = e.source_channel_id JOIN channels t ON t.id = e.target_channel_id) TO 'out/aristas_${FASE}.csv' CSV HEADER"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v schema="${RECO_SCHEMA:-reco}" -f aws/sql/10_snowball_candidatos.sql > "out/candidatos_snowball_${FASE}.txt"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v schema="${RECO_SCHEMA:-reco}" -f aws/sql/20_comprobaciones.sql > "out/comprobaciones_${FASE}.txt"

pub_despues="$(reco_contar_public)" || { estado "abortado_conteo"; exit 9; }
reco_exigir_public_igual "$pub_antes" "$pub_despues" || { estado "ALERTA_public_cambio"; exit 10; }

if command -v aws >/dev/null && [ -n "${RECO_S3_PREFIX:-}" ]; then
  aws s3 sync out/ "${RECO_S3_PREFIX%/}/fase_${FASE}/" --only-show-errors
fi
estado "terminado"
echo "FASE $FASE TERMINADA. Salidas en $ROOT/out/"
echo "Candidatos para curar a mano: out/candidatos_snowball_${FASE}.txt"
