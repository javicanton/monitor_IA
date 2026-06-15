#!/usr/bin/env bash
# Despliega el worker pytopicgram en la instancia EC2 dedicada (sin tocar app :80 ni staging :8080).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ONCE=false
DAYS="${TOPICS_DAYS_WINDOW:-7}"
DOWN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --once) ONCE=true; shift ;;
    --down) DOWN=true; shift ;;
    --days=*) DAYS="${1#*=}"; shift ;;
    --days) DAYS="${2:-7}"; shift 2 ;;
    -h|--help)
      cat <<EOF
Uso: $0 [--once] [--days N] [--down]

  Despliega topic_worker con docker-compose.worker.yml en esta instancia.
  Por defecto procesa solo los últimos 7 días (TOPICS_DAYS_WINDOW).

  --once     Ejecuta una pasada y sale (no deja el bucle activo)
  --days N   Ventana temporal en días (pruebas: 7)
  --down     Detiene el contenedor del worker

Variables útiles en .env:
  DATABASE_URL          PostgreSQL (mensajes + message_topics)
  TOPICS_RESET_STATE=1  Reprocesar toda la ventana (recomendado en pruebas)
  TOPICS_S3_PREFIX      Prefijo S3 para modelo/asignaciones (p. ej. topics/staging/)
EOF
      exit 0
      ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
export TOPICS_DAYS_WINDOW="$DAYS"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

_validate_database_url() {
  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL no está definido en .env"
    echo ""
    echo "En la instancia Monitor IA (staging), obtén la URL real:"
    echo "  grep DATABASE_URL ~/monitor_IA/.env"
    echo "  # o: docker exec monitoria-staging-backend printenv DATABASE_URL"
    echo ""
    echo "Pégala en este servidor (worker), descomentada, con host RDS (no localhost)."
    exit 1
  fi
  if [[ "$DATABASE_URL" == *"@localhost"* ]] || [[ "$DATABASE_URL" == *"@127.0.0.1"* ]]; then
    echo "ERROR: DATABASE_URL apunta a localhost; en el worker debe ser el host RDS."
    echo "  Actual: ${DATABASE_URL/@*/@***}"
    echo ""
    echo "Copia la URL de Monitor IA (termina en .rds.amazonaws.com)."
    exit 1
  fi
  if [[ "$DATABASE_URL" != *"sslmode="* ]]; then
    echo "AVISO: RDS suele requerir ?sslmode=require al final de DATABASE_URL"
  fi
  echo "==> DATABASE_URL: ${DATABASE_URL/@*/@***} (${#DATABASE_URL} chars)"
}

_validate_database_url

_detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN=(docker compose)
    COMPOSE_PROGRESS=(--progress=plain)
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(docker-compose)
    COMPOSE_PROGRESS=()
    echo "==> Usando docker-compose (v1); si falla, instala el plugin: docker compose"
    return 0
  fi
  echo "ERROR: no se encontró 'docker compose' ni 'docker-compose'."
  echo "  Ubuntu: sudo apt install docker-compose-plugin   # o: docker-compose"
  exit 1
}

_detect_compose
COMPOSE=("${COMPOSE_BIN[@]}" -f docker-compose.worker.yml)

if $DOWN; then
  "${COMPOSE[@]}" down
  echo "Worker de topics detenido."
  exit 0
fi

echo "==> Build topic_worker (pytopicgram + PyTorch CPU; puede tardar varios minutos)..."
"${COMPOSE[@]}" build "${COMPOSE_PROGRESS[@]}" topic_worker

if $ONCE; then
  echo "==> Ejecución única (--once), ventana ${DAYS} días..."
  "${COMPOSE[@]}" run --rm \
    -e TOPICS_DAYS_WINDOW="$DAYS" \
    topic_worker python topic_worker.py --once --days "$DAYS"
  echo "Listo. Revisa logs y S3 (${TOPICS_S3_PREFIX:-topics/staging/})."
  exit 0
fi

echo "==> Arrancando worker en bucle (intervalo ${TOPIC_POLL_INTERVAL_MIN:-1440} min)..."
"${COMPOSE[@]}" up -d topic_worker
echo ""
echo "Worker activo. Logs:"
echo "  docker logs -f monitoria-topic-worker"
echo "Ejecución manual:"
echo "  $0 --once --days ${DAYS}"
