#!/usr/bin/env bash
# Crea/repara el venv del scraper en el EC2 (una vez, o tras rotura del venv).
# Uso: ./scripts/ensure_scraper_venv.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_SYS="${ENSURE_PYTHON:-python3}"
VENV_PY="${ROOT}/.venv/bin/python"
VENV_PIP="${ROOT}/.venv/bin/pip"

if [[ ! -x "$VENV_PY" ]]; then
  echo "==> Creando venv en ${ROOT}/.venv"
  "$PYTHON_SYS" -m venv "${ROOT}/.venv"
fi

echo "==> Python: $VENV_PY"
"$VENV_PIP" install -U pip wheel

# Deps mínimas del scraper (evita pytopicgram/git del requirements raíz, no hace falta para el cron)
echo "==> Instalando deps del scraper..."
"$VENV_PIP" install \
  "pandas>=2.0.0" \
  "telethon>=1.34.0" \
  "openpyxl>=3.1.2" \
  "python-dotenv>=1.0.0" \
  "boto3>=1.28.0" \
  "psycopg2-binary>=2.9.0" \
  "flask>=2.3.0" \
  "flask-sqlalchemy>=3.0.0" \
  "SQLAlchemy>=2.0.0"

echo "==> Comprobando imports..."
"$VENV_PY" -c "import pandas, telethon, openpyxl, dotenv, boto3; print('OK pandas', pandas.__version__, '| telethon', telethon.__version__)"

echo ""
echo "Listo. Prueba: ./scripts/run_scraper_daily.sh"
