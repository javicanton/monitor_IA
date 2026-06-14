#!/usr/bin/env bash
# Marca canales inválidos en monitored_channels (no los borra del CSV).
# Uso: ./scripts/mark_channel_discontinued.sh saludprohibida "Username inválido"
set -euo pipefail

USERNAME="${1:?Indica username sin @}"
REASON="${2:-Canal inválido o descontinuado}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/_scraper_env.sh"
scraper_load_env

cd "${ROOT}/backend"
"$PYTHON" - <<PY
from channel_graph import mark_monitored_channel_error
from pg_upsert import create_app

app = create_app()
with app.app_context():
    mark_monitored_channel_error("${USERNAME}", """${REASON}""")
print("OK: ${USERNAME} → discontinued=true, status=error")
PY
