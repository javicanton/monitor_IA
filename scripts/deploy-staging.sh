#!/usr/bin/env bash
# Despliegue de la rama desarrollo (puerto 8080). No toca funcional en :80.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.deploy-test.yml -f docker-compose.staging.yml)
PROJECT_NAME="${STAGING_PROJECT_NAME:-monitoria-staging}"
STAGING_PORT="${STAGING_FRONTEND_PORT:-8080}"

down=false
for arg in "$@"; do
  case "$arg" in
    --down) down=true ;;
    -h|--help)
      echo "Uso: $0 [--down]"
      echo "  Despliega staging en puerto ${STAGING_PORT} (proyecto Docker: ${PROJECT_NAME})"
      exit 0
      ;;
  esac
done

export STAGING_FRONTEND_PORT="$STAGING_PORT"
export FRONTEND_PORT="$STAGING_PORT"

if $down; then
  docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" down
  echo "Staging detenido."
  exit 0
fi

if [[ -f .env ]]; then
  if grep -q '^DATABASE_URL=' .env 2>/dev/null; then
    echo "==> Modo datos: PostgreSQL (DATABASE_URL definido)"
  else
    echo "==> Modo datos: Parquet/S3 (sin DATABASE_URL). Ver docs/SQL_MIGRATION.md para escalar."
  fi
fi

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "AVISO: creado .env desde .env.example (edítalo si hace falta)."
  else
    touch .env
    echo "AVISO: creado .env vacío; en EC2 suele bastar el rol IAM o la URL pública de S3."
  fi
fi

echo "==> Build staging (${PROJECT_NAME})..."
docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" build

echo "==> Arrancando staging en puerto ${STAGING_PORT}..."
docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" up -d

echo ""
echo "Staging listo (producción en :80 no se toca si usa otro proyecto compose)."
echo "  http://localhost:${STAGING_PORT}/"
echo "  curl -s http://localhost:${STAGING_PORT}/api/health"
echo "Parar: $0 --down"
