#!/usr/bin/env bash
# Despliega el worker pytopicgram en la instancia EC2 dedicada (sin tocar app :80 ni staging :8080).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.worker.yml"
ONCE=false
DAYS="${TOPICS_DAYS_WINDOW:-7}"
DOWN=false
MODE="incremental"
SAMPLE_SIZE="${TOPICS_TRAIN_SAMPLE_SIZE:-30000}"
BATCH_SIZE="${TOPICS_ASSIGN_BATCH_SIZE:-5000}"
RESET_PROGRESS=false
WORKER_EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --once) ONCE=true; shift ;;
    --down) DOWN=true; shift ;;
    --days=*) DAYS="${1#*=}"; shift ;;
    --days) DAYS="${2:-7}"; shift 2 ;;
    --train-sample) MODE="train_sample"; ONCE=true; shift ;;
    --assign-all) MODE="assign_all"; ONCE=true; shift ;;
    --sample-size=*) SAMPLE_SIZE="${1#*=}"; shift ;;
    --sample-size) SAMPLE_SIZE="${2:-30000}"; shift 2 ;;
    --batch-size=*) BATCH_SIZE="${1#*=}"; shift ;;
    --batch-size) BATCH_SIZE="${2:-5000}"; shift 2 ;;
    --reset-progress) RESET_PROGRESS=true; shift ;;
    -h|--help)
      cat <<EOF
Uso: $0 [--once|--train-sample|--assign-all] [--days N] [--down]

  Despliega topic_worker con docker-compose.worker.yml en esta instancia.
  Prefijo S3 por defecto: topics/staging/ (no toca producción).

  --once              Pasada incremental (mensajes nuevos)
  --train-sample      Entrenar con submuestra SQL (~TOPICS_TRAIN_SAMPLE_SIZE)
  --assign-all        Aplicar modelo al histórico por lotes (con checkpoint)
  --days N            Ventana temporal (0 = sin límite)
  --sample-size N     Tamaño submuestra para --train-sample
  --batch-size N      Lote para --assign-all
  --reset-progress    Reinicia checkpoint de --assign-all
  --down              Detiene el contenedor del worker

Flujo recomendado (dataset grande):
  1) $0 --train-sample --days 0 --sample-size 30000
  2) Revisar /topics en staging :8080 y nombrar etiquetas
  3) $0 --assign-all --days 0
  4) $0   # bucle diario
EOF
      exit 0
      ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

_setup_buildkit() {
  if docker buildx version >/dev/null 2>&1; then
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    echo "==> BuildKit: activado (buildx disponible)"
  else
    unset DOCKER_BUILDKIT COMPOSE_DOCKER_CLI_BUILD
    export DOCKER_BUILDKIT=0
    echo "==> BuildKit: desactivado (buildx no instalado; build clásico)"
  fi
}

_setup_buildkit
export TOPICS_DAYS_WINDOW="$DAYS"
export TOPICS_TRAIN_SAMPLE_SIZE="$SAMPLE_SIZE"
export TOPICS_ASSIGN_BATCH_SIZE="$BATCH_SIZE"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Reaplicar overrides de CLI tras source .env
export TOPICS_DAYS_WINDOW="$DAYS"
export TOPICS_TRAIN_SAMPLE_SIZE="$SAMPLE_SIZE"
export TOPICS_ASSIGN_BATCH_SIZE="$BATCH_SIZE"

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

_setup_compose() {
  COMPOSE_MODE=""
  if command -v docker-compose >/dev/null 2>&1; then
    if docker-compose -f "$COMPOSE_FILE" config -q >/dev/null 2>&1; then
      COMPOSE_MODE=v1
      compose() { docker-compose -f "$COMPOSE_FILE" "$@"; }
      echo "==> Docker Compose: docker-compose (v1)"
      return 0
    fi
  fi
  if docker compose -f "$COMPOSE_FILE" config -q >/dev/null 2>&1; then
    COMPOSE_MODE=v2
    compose() { docker compose -f "$COMPOSE_FILE" "$@"; }
    echo "==> Docker Compose: docker compose (v2)"
    return 0
  fi
  echo "ERROR: no funciona ni 'docker-compose' ni 'docker compose' con ${COMPOSE_FILE}."
  echo ""
  echo "Comprueba en esta instancia:"
  echo "  docker-compose --version"
  echo "  docker compose version"
  echo ""
  echo "Instalar (Ubuntu):"
  echo "  sudo apt update && sudo apt install -y docker-compose"
  echo "  # o: sudo apt install -y docker-compose-plugin"
  exit 1
}

_validate_database_url
_setup_compose

if $DOWN; then
  compose down
  echo "Worker de topics detenido."
  exit 0
fi

echo "==> Build topic_worker (pytopicgram + PyTorch CPU; puede tardar varios minutos)..."
if [[ "$COMPOSE_MODE" == v2 ]]; then
  compose build --progress=plain topic_worker
else
  compose build topic_worker
fi

if [[ "$MODE" == "train_sample" ]]; then
  echo "==> Train-sample: ${SAMPLE_SIZE} msgs, ventana ${DAYS} días..."
  compose run --rm \
    -e TOPICS_DAYS_WINDOW="$DAYS" \
    -e TOPICS_TRAIN_SAMPLE_SIZE="$SAMPLE_SIZE" \
    topic_worker python topic_worker.py --train-sample --days "$DAYS" --sample-size "$SAMPLE_SIZE"
  echo "Listo. Revisa S3 (${TOPICS_S3_PREFIX:-topics/staging/}) y /topics en staging :8080"
  exit 0
fi

if [[ "$MODE" == "assign_all" ]]; then
  echo "==> Assign-all: lote ${BATCH_SIZE}, ventana ${DAYS} días..."
  EXTRA=()
  if $RESET_PROGRESS; then
    EXTRA+=(--reset-progress)
  fi
  compose run --rm \
    -e TOPICS_DAYS_WINDOW="$DAYS" \
    -e TOPICS_ASSIGN_BATCH_SIZE="$BATCH_SIZE" \
    topic_worker python topic_worker.py --assign-all --days "$DAYS" --batch-size "$BATCH_SIZE" "${EXTRA[@]}"
  echo "Listo. Checkpoint en ${TOPICS_ASSIGN_PROGRESS_KEY:-topics/staging/assign_progress.json}"
  exit 0
fi

if $ONCE; then
  echo "==> Ejecución incremental (--once), ventana ${DAYS} días..."
  compose run --rm \
    -e TOPICS_DAYS_WINDOW="$DAYS" \
    topic_worker python topic_worker.py --once --days "$DAYS"
  echo "Listo. Revisa logs y S3 (${TOPICS_S3_PREFIX:-topics/staging/})."
  exit 0
fi

echo "==> Arrancando worker en bucle (intervalo ${TOPIC_POLL_INTERVAL_MIN:-1440} min)..."
compose up -d topic_worker
echo ""
echo "Worker activo. Logs:"
echo "  docker logs -f monitoria-topic-worker"
echo "Ejecución manual:"
echo "  $0 --train-sample --days 0 --sample-size ${SAMPLE_SIZE}"
echo "  $0 --assign-all --days 0"
echo "  $0 --once --days ${DAYS}"
