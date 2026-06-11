#!/usr/bin/env bash
# Despliegue de la rama desarrollo (puerto 8080). No toca funcional en :80.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.deploy-test.yml -f docker-compose.staging.yml)
PROJECT_NAME="${STAGING_PROJECT_NAME:-monitoria-staging}"
STAGING_PORT="${STAGING_FRONTEND_PORT:-8080}"

down=false
backend_only=false
host_frontend=false
for arg in "$@"; do
  case "$arg" in
    --down) down=true ;;
    --backend-only) backend_only=true ;;
    --host-frontend) host_frontend=true ;;
    -h|--help)
      echo "Uso: $0 [--down] [--backend-only] [--host-frontend]"
      echo "  Despliega staging en puerto ${STAGING_PORT} (proyecto Docker: ${PROJECT_NAME})"
      echo ""
      echo "  --backend-only    Solo reconstruye backend (frontend con imagen previa)"
      echo "  --host-frontend   Compila React en el host y usa Dockerfile.runtime (recomendado en EC2 pequeña)"
      exit 0
      ;;
  esac
done

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

export STAGING_FRONTEND_PORT="$STAGING_PORT"
export FRONTEND_PORT="$STAGING_PORT"
export REACT_APP_APP_VERSION="${REACT_APP_APP_VERSION:-0.4 (en desarrollo)}"

if $down; then
  docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" down
  echo "Staging detenido."
  exit 0
fi

if [[ -f .env ]]; then
  # Exportar .env al shell para que compose sustituya variables (sin xargs: rompe contraseñas).
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  if [[ -n "${DATABASE_URL:-}" ]]; then
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

if $host_frontend; then
  echo "==> Build frontend en el host (evita OOM dentro de Docker)..."
  echo "    Puede tardar 5–15 min en instancias pequeñas; es normal."
  (
    cd "$ROOT/frontend"
    export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1024}"
    export GENERATE_SOURCEMAP=false
    export DISABLE_ESLINT_PLUGIN=true
    export BROWSERSLIST_IGNORE_OLD_DATA=true
    export CI=false
    export REACT_APP_API_URL=/api
    export REACT_APP_APP_VERSION="${REACT_APP_APP_VERSION:-0.4 (en desarrollo)}"
    npm install --omit=dev
    npm run build
  )
  export FRONTEND_DOCKERFILE=Dockerfile.runtime
fi

echo "==> Build staging (${PROJECT_NAME})..."
if $backend_only; then
  echo "    (solo backend)"
  docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" build backend
else
  echo "    El paso 'npm run build' del frontend puede tardar 10–20 min en EC2; no es un bloqueo si sigue en 'Creating an optimized production build...'"
  docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" build --progress=plain
fi

echo "==> Arrancando staging en puerto ${STAGING_PORT}..."
docker compose -p "$PROJECT_NAME" "${COMPOSE_FILES[@]}" up -d

echo ""
echo "Staging listo (producción en :80 no se toca si usa otro proyecto compose)."
echo "  http://localhost:${STAGING_PORT}/"
echo "  curl -s http://localhost:${STAGING_PORT}/api/health"

if docker ps --format '{{.Names}}' | grep -q '^monitoria-staging-backend$'; then
  db_mode="$(docker exec monitoria-staging-backend printenv DATABASE_URL 2>/dev/null | wc -c)"
  if [[ "${db_mode}" -gt 1 ]]; then
    echo "  PostgreSQL en contenedor: OK (DATABASE_URL presente)"
  else
    echo "  AVISO: DATABASE_URL vacío en el contenedor — revisa .env y vuelve a desplegar"
  fi
fi

echo "Parar: $0 --down"
