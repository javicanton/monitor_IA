# Funciones comunes para scripts de scraper (source, no ejecutar).
_scraper_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[1]}")/.." && pwd)"
  echo "$script_dir"
}

scraper_load_env() {
  ROOT="$(_scraper_root)"
  cd "$ROOT"

  if [[ ! -f .env ]]; then
    echo "ERROR: falta .env con DATABASE_URL en ${ROOT}"
    exit 1
  fi
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a

  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL no está definido en .env"
    exit 1
  fi

    PYTHON="${ROOT}/.venv/bin/python"
    if [[ ! -x "$PYTHON" ]]; then
        echo "ERROR: no existe ${ROOT}/.venv/bin/python"
        echo "Crea el venv e instala deps del scraper (una vez):"
        echo "  cd ${ROOT}"
        echo "  python3 -m venv .venv"
        echo "  .venv/bin/pip install -U pip"
        echo "  .venv/bin/pip install -r requirements.txt -r backend/requirements.txt"
        echo "Luego: ./scripts/run_scraper_daily.sh"
        exit 7
    fi

    export PYTHONUNBUFFERED=1
    echo "==> Python scraper: ${PYTHON}" >&2

    # Comprobación rápida antes de lanzar scraper.py (mensaje más claro que el pip auto-install)
    if ! "$PYTHON" -c "import pandas, telethon, openpyxl, dotenv, boto3" 2>/dev/null; then
        echo "ERROR: el venv existe pero faltan paquetes del scraper (p.ej. pandas/telethon)."
        echo "Repara con:"
        echo "  ${PYTHON} -m pip install -r ${ROOT}/requirements.txt -r ${ROOT}/backend/requirements.txt"
        exit 7
    fi

    LOG_DIR="${ROOT}/logs"
  mkdir -p "$LOG_DIR"
}

scraper_acquire_lock() {
  local lock_name="${1:-scraper}"
  LOCK_FILE="${LOG_DIR}/${lock_name}.lock"
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "AVISO: otro proceso de scraper (${lock_name}) ya está en curso. Salida."
    exit 0
  fi
}

scraper_print_status() {
  if command -v psql >/dev/null 2>&1; then
    echo "==> Estado actual en PostgreSQL:"
    psql "$DATABASE_URL" -t -A -c "
      SELECT 'mensajes=' || count(*) FROM messages;
      SELECT 'canales_con_msgs=' || count(DISTINCT channel_id) FROM messages;
      SELECT 'monitorizados_activos=' || count(*) FROM monitored_channels WHERE status='active' AND discontinued=false;
      SELECT 'descontinuados=' || count(*) FROM monitored_channels WHERE discontinued=true;
    " 2>/dev/null | sed 's/^/    /' || echo "    (no se pudo consultar psql)"
  fi
}
