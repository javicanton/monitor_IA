#!/usr/bin/env bash
# Comprueba que pytopicgram dejó datos visibles en staging (:8080) o producción.
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
echo "==> Verificando topics en ${BASE_URL}"

health="$(curl -sf "${BASE_URL}/api/health" || true)"
if [[ -z "$health" ]]; then
  echo "ERROR: no responde ${BASE_URL}/api/health"
  exit 1
fi
echo "  health: ${health}"

topics_json="$(curl -sf "${BASE_URL}/api/topics" || echo '{}')"
topic_count="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('topics') or []))" <<<"$topics_json" 2>/dev/null || echo 0)"
echo "  topics en API: ${topic_count}"

sample="$(curl -sf -X POST "${BASE_URL}/api/filter_messages" \
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

if [[ "$topic_count" -eq 0 ]]; then
  echo ""
  echo "AVISO: aún no hay topics. En la instancia del worker ejecuta:"
  echo "  ./scripts/deploy-worker.sh --once --days 7"
  exit 1
fi

echo ""
echo "OK: narrativas disponibles."
