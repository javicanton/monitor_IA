#!/usr/bin/env bash
# Prueba de despliegue local o en EC2 (build Docker + compose up).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PRODUCTION=false
FRONTEND_PORT="${FRONTEND_PORT:-8080}"

for arg in "$@"; do
  case "$arg" in
    --production) PRODUCTION=true; FRONTEND_PORT=80 ;;
    -h|--help)
      echo "Uso: $0 [--production]"
      echo "  --production  expone el frontend en el puerto 80"
      echo ""
      echo "  No construye topic_worker (análisis de temas). Para activarlo:"
      echo "  docker compose --profile topics build topic_worker && docker compose --profile topics up -d topic_worker"
      exit 0
      ;;
  esac
done

export FRONTEND_PORT

if $PRODUCTION; then
  export REACT_APP_APP_VERSION="${REACT_APP_APP_VERSION:-1.0}"
  echo "==> Versión UI: ${REACT_APP_APP_VERSION}"
  echo "==> NOTA: Este script despliega en el puerto ${FRONTEND_PORT} (producción)."
  echo "    Staging en :8080 requiere rama desarrollo y ./scripts/deploy-staging.sh"
else
  export REACT_APP_APP_VERSION="${REACT_APP_APP_VERSION:-1.0}"
fi

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "AVISO: creado .env desde .env.example."
  else
    touch .env
    echo "AVISO: creado .env vacío."
  fi
fi

echo "==> Build imágenes (backend + frontend; topic_worker opcional con perfil topics)..."
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml build backend frontend

echo "==> Arrancando servicios en puerto ${FRONTEND_PORT}..."
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml up -d

echo ""
echo "Comprobaciones sugeridas:"
echo "  curl -s http://localhost:${FRONTEND_PORT}/api/health"
echo "  curl -s -X POST http://localhost:${FRONTEND_PORT}/api/filter_messages -H 'Content-Type: application/json' -d '{\"page\":1}' | head -c 200"
echo ""
echo "Abrir: http://localhost:${FRONTEND_PORT}/"
echo "Parar: docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml down"
