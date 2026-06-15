#!/usr/bin/env bash
# Resuelve el merge conflictivo tras "git pull origin desarrollo" en EC2.
# Uso: desde ~/monitor_IA con merge en curso, o tras --abort para reset limpio.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
  echo "==> Merge en curso: conservando versión remota (origin/desarrollo) en archivos conflictivos..."
  for f in backend/data_store.py backend/search_index.py scripts/deploy-staging.sh; do
    if [[ -f "$f" ]] && grep -q '^<<<<<<<' "$f" 2>/dev/null; then
      git checkout --theirs -- "$f"
      git add "$f"
      echo "    resuelto: $f (theirs)"
    fi
  done
  if git diff --cached --quiet; then
    echo "No quedan conflictos en los archivos esperados. Revisa: git status"
    exit 1
  fi
  git commit -m "Merge origin/desarrollo: resolver conflictos con versión remota"
  echo "==> Merge completado. Ejecuta: ./scripts/deploy-staging.sh --backend-only"
  exit 0
fi

echo "==> Sin merge activo. Sincronizando con origin/desarrollo (descarta commits locales)..."
read -r -p "¿Descartar commits locales y alinear con origin/desarrollo? [y/N] " ans
if [[ "${ans,,}" != "y" ]]; then
  echo "Cancelado."
  exit 1
fi
git fetch origin
git reset --hard origin/desarrollo
echo "==> Rama alineada con origin/desarrollo ($(git rev-parse --short HEAD))"
echo "    ./scripts/deploy-staging.sh --host-frontend"
