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
      exit 0
      ;;
  esac
done

export FRONTEND_PORT

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "AVISO: creado .env desde .env.example."
  else
    touch .env
    echo "AVISO: creado .env vacío."
  fi
fi

echo "==> Build imágenes (backend + frontend)..."
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml build

echo "==> Arrancando servicios en puerto ${FRONTEND_PORT}..."
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml up -d

echo ""
echo "Comprobaciones sugeridas:"
echo "  curl -s http://localhost:${FRONTEND_PORT}/api/health"
echo "  curl -s -X POST http://localhost:${FRONTEND_PORT}/api/filter_messages -H 'Content-Type: application/json' -d '{\"page\":1}' | head -c 200"
echo ""
echo "Abrir: http://localhost:${FRONTEND_PORT}/"
echo "Parar: docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml down"
