# Topics / narrativas (pytopicgram)

Pipeline pensado para **>1M mensajes** en PostgreSQL (RDS).  
Todo el trabajo de validación usa el prefijo S3 **`topics/staging/`** y la app en **`desarrollo` / puerto 8080**. No toca producción pública.

## Arquitectura

```
EC2 topic-worker  →  RDS (messages, message_topics)
                  →  S3 topics/staging/{model.pkl,topics.json,...}
Monitor IA staging (:8080)  ← lee RDS + S3 meta/títulos
```

## Flujo recomendado

### 1) Entrenar con submuestra

En la instancia **worker**:

```bash
cd ~/monitor_IA
git checkout desarrollo && git pull

# .env: DATABASE_URL (RDS), TOPICS_* staging, rol IAM S3
./scripts/deploy-worker.sh --train-sample --days 0 --sample-size 30000
```

- Muestreo **en SQL** (`ORDER BY random() LIMIT N`), no carga el millón en RAM.
- Sube `model.pkl` + `topics.json` a S3 staging.
- Asigna topics **solo a la submuestra** (para validar en UI).

### 2) Validar y nombrar etiquetas

`/topics` exige JWT (`Authorization: Bearer …`). Sin token verás `{"msg": "Missing Authorization Header"}` — el proxy está bien; falta auth.

**Opción A — UI:** entra en `http://<host>:8080`, inicia sesión, filtro **Temas**.

**Opción B — curl con token** (DevTools → Application → localStorage → `token`):

```bash
TOKEN='eyJ...'   # valor de localStorage.token tras login
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/topics \
  | python3 -m json.tool | head -80
```

**Opción C — sin JWT, en el EC2 de staging** (lee S3 vía el contenedor):

```bash
docker exec -i monitoria-staging-backend python3 - <<'PY'
from app import load_topics_meta
topics = load_topics_meta()
print("total:", len(topics))
for t in topics[:20]:
    print(t["id"], t.get("count"), t["label"])
PY

# o el script (usa TOKEN si existe; si no, cae a S3 vía backend):
./scripts/verify-topics.sh http://localhost:8080
# TOKEN='eyJ...' ./scripts/verify-topics.sh
```

**Opción D — S3 directo:**

```bash
aws s3 cp s3://monitoria-data/topics/staging/topics.json - | python3 -m json.tool | head -80
```

Nombra etiquetas con admin `POST /admin/topic_titles` (rol admin) o editando `topics/staging/topic_titles.json`.  
Con OpenAI en el próximo train: `TOPICS_OPENAI_KEY=sk-...` en el `.env` del worker.

### 3) Aplicar al histórico

```bash
./scripts/deploy-worker.sh --assign-all --days 0
# Si se corta (créditos CPU), relanza el mismo comando: retoma checkpoint
# Para empezar de cero:
./scripts/deploy-worker.sh --assign-all --days 0 --reset-progress
```

Checkpoint: `topics/staging/assign_progress.json`.

### 4) Diario (mensajes nuevos)

```bash
./scripts/deploy-worker.sh
# o una pasada:
./scripts/deploy-worker.sh --once --days 3
```

## Variables clave

| Variable | Default staging | Uso |
|----------|-----------------|-----|
| `TOPICS_TRAIN_SAMPLE_SIZE` | 30000 | Submuestra de entrenamiento |
| `TOPICS_MIN_TEXT_LEN` | 40 | Longitud mínima tras limpiar URLs |
| `TOPICS_MIN_ALPHA_CHARS` | 25 | Mínimo de letras (evita solo-enlace/emoji) |
| `TOPICS_SAMPLE_OVERFETCH` | 2.5 | Sobre-muestreo SQL antes del filtro de calidad |
| `TOPICS_EXCLUDE_MEDIA_ONLY` | 1 | Excluye Photo/Video/… con caption corto |
| `TOPICS_SAMPLE_SEED` | monitoria-topics | Muestreo reproducible |
| `TOPICS_ASSIGN_BATCH_SIZE` | 5000 | Lotes assign-all |
| `TOPICS_NUM_TOPICS` | 40–100 | Objetivo BERTopic |
| `TOPICS_S3_PREFIX` | `topics/staging/` | No mezclar con prod |

## Calidad de texto (exclusiones)

Se excluyen del entrenamiento (y del assign si no pasan el filtro):

- Mensajes que son **solo una URL** (`https://…`)
- Texto que, **tras quitar URLs / t.me**, queda corto o sin letras suficientes
- **Photo / Video / GIF / Sticker / Voice / Audio / Document / Webpage** con caption corto (<60 chars o < `TOPICS_MIN_TEXT_LEN`)

Los mensajes con media **y** caption narrativo largo **sí** se usan.

## CLI del worker

```bash
python topic_worker.py --train-sample --days 0 --sample-size 30000
python topic_worker.py --assign-all --days 0 --batch-size 5000
python topic_worker.py --once --days 3
```
