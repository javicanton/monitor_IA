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

En staging (`:8080`):

```bash
curl -s http://localhost:8080/topics | python3 -m json.tool | head -80
```

Revisa el filtro **Temas**. Nombra con admin `POST /admin/topic_titles` o editando `topics/staging/topic_titles.json`.

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
