#!/usr/bin/env bash
# Comprueba que pytopicgram dejó datos visibles en staging (:8080) o producción.
# /topics exige JWT (allowed_email_required). Pasa el token así:
#   TOKEN='eyJ...' ./scripts/verify-topics.sh
#   ./scripts/verify-topics.sh http://localhost:8080 'eyJ...'
# Sin token: usa S3 vía el contenedor backend (si está en marcha) o falla con instrucciones.
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
TOKEN="${2:-${TOKEN:-${TOPICS_VERIFY_TOKEN:-}}}"

echo "==> Verificando topics en ${BASE_URL}"

health="$(curl -sf "${BASE_URL}/api/health" || true)"
if [[ -z "$health" ]]; then
  echo "ERROR: no responde ${BASE_URL}/api/health"
  exit 1
fi
echo "  health: ${health}"

auth_header=()
if [[ -n "$TOKEN" ]]; then
  auth_header=(-H "Authorization: Bearer ${TOKEN}")
  echo "  auth: Bearer token (${#TOKEN} chars)"
else
  echo "  auth: sin TOKEN — /topics devolverá 401; se intentará leer meta vía contenedor/S3"
fi

topics_json="$(curl -s "${auth_header[@]}" "${BASE_URL}/topics" || echo '{}')"
api_msg="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('msg') or d.get('error') or '')" <<<"$topics_json" 2>/dev/null || true)"

if [[ "$api_msg" == "Missing Authorization Header" ]] || [[ "$api_msg" == *"Authorization"* ]]; then
  echo "  /topics API: requiere Authorization: Bearer <jwt>"
  echo "  Obtén el token: inicia sesión en la UI → DevTools → Application → localStorage → token"
  echo "  Luego: TOKEN='...' ./scripts/verify-topics.sh ${BASE_URL}"
  topics_json='{}'
  topic_count=0
else
  topic_count="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('topics') or []))" <<<"$topics_json" 2>/dev/null || echo 0)"
  echo "  topics en API: ${topic_count}"
  if [[ "$topic_count" -gt 0 ]]; then
    python3 -c "
import json, sys
d = json.loads(sys.argv[1])
topics = d.get('topics') or []
for t in topics[:12]:
    print(f\"    id={t.get('id')}\tcount={t.get('count')}\t{t.get('label')}\")
if len(topics) > 12:
    print(f'    ... +{len(topics) - 12} más')
" "$topics_json" 2>/dev/null || true
  fi
fi

# Fallback: leer topics.json desde S3 dentro del backend staging (sin JWT)
if [[ "$topic_count" -eq 0 ]] && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^monitoria-staging-backend$'; then
  echo "  → leyendo meta S3 vía monitoria-staging-backend..."
  s3_count="$(docker exec monitoria-staging-backend python3 - <<'PY' 2>/dev/null || echo 0
from app import load_topics_meta
topics = load_topics_meta()
print(len(topics))
for t in topics[:12]:
    print(f"    id={t.get('id')}\tcount={t.get('count')}\t{t.get('label')}", flush=True)
if len(topics) > 12:
    print(f"    ... +{len(topics) - 12} más", flush=True)
PY
)"
  # primera línea = count
  topic_count="$(printf '%s\n' "$s3_count" | head -1)"
  printf '%s\n' "$s3_count" | tail -n +2 | sed 's/^/  /'
  echo "  topics en S3 (via backend): ${topic_count}"
fi

if [[ -n "$TOKEN" ]]; then
  sample="$(curl -s "${auth_header[@]}" -X POST "${BASE_URL}/api/filter_messages" \
    -H "Content-Type: application/json" \
    -d '{"page":1,"limit":5}' || echo '{}')"
  with_topic="$(python3 -c "
import json,sys
d=json.load(sys.stdin)
msgs=d.get('messages') or []
n=sum(1 for m in msgs if m.get('topic_id') is not None)
print(f'{n}/{len(msgs)}')
" <<<"$sample" 2>/dev/null || echo '?')"
  echo "  mensajes con topic_id (muestra 5): ${with_topic}"
fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^monitoria-staging-backend$'; then
  count="$(docker exec monitoria-staging-backend python3 - <<'PY' 2>/dev/null || echo '?'
import os
if not os.environ.get("DATABASE_URL"):
    print("N/A (sin DATABASE_URL)")
    raise SystemExit(0)
from pg_upsert import create_app
from models import MessageTopic, db
app = create_app()
with app.app_context():
    print(db.session.query(MessageTopic).count())
PY
)"
  echo "  filas en message_topics (PostgreSQL): ${count}"
fi

# S3 ls si aws cli está disponible
if command -v aws >/dev/null 2>&1; then
  bucket="${S3_BUCKET:-monitoria-data}"
  prefix="${TOPICS_S3_PREFIX:-topics/staging/}"
  echo "  objetos S3 s3://${bucket}/${prefix}:"
  aws s3 ls "s3://${bucket}/${prefix}" 2>/dev/null | sed 's/^/    /' || echo "    (no listable)"
fi

if [[ "${topic_count}" == "0" ]] || [[ -z "${topic_count}" ]]; then
  echo ""
  echo "AVISO: aún no hay topics visibles."
  echo "  Worker: ./scripts/deploy-worker.sh --train-sample --days 0 --sample-size 8000"
  echo "  Con JWT: TOKEN='...' ./scripts/verify-topics.sh ${BASE_URL}"
  exit 1
fi

echo ""
echo "OK: narrativas disponibles (${topic_count} topics)."
