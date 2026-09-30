#!/usr/bin/env bash
# Entorno virtual para scripts en la EC2 (init_postgres, import_dataset, scraper).
# Ubuntu 24+ no permite pip install global (PEP 668).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "==> Creando .venv..."
  python3 -m venv "$VENV"
fi

echo "==> Instalando dependencias del backend..."
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r backend/requirements.txt

echo ""
echo "Listo. Usa:"
echo "  source .venv/bin/activate"
echo "  export \$(grep -v '^#' .env | xargs)"
echo "  python scripts/init_postgres.py"
