# Línea base de despliegue (app.monitoria.org)

Este documento fija el **punto exacto** donde la web funciona igual que en producción (v0.33, gráfico temporal, búsqueda FTS, sin login obligatorio).

## Referencia Git

| Referencia | Commit | Notas |
|------------|--------|--------|
| Tag `production-baseline-2026-02-17` | `06967fd` | Coincide con `build-id.txt` en producción (`2026-02-17T12:55:59Z`) |
| Rama de trabajo | `cursor/deploy-baseline-a92b` | Parte de ese commit; aquí se prueba el despliegue antes de publicar |

La rama remota `scraper` **contiene** este commit y tiene 5 commits posteriores (mejoras del scraper). Para la UI idéntica a producción, usa **`06967fd`**, no necesariamente la punta de `scraper`.

## Volver a este punto en tu máquina

Si al hacer `git checkout` ves `M .venv/pyvenv.cfg`, es porque `.venv` estaba versionado por error. Solución:

```bash
git fetch origin
git checkout cursor/deploy-baseline-a92b
# Si sigue apareciendo .venv modificado:
git restore .venv/pyvenv.cfg 2>/dev/null || rm -rf .venv
```

Alternativa por tag (solo lectura):

```bash
git fetch origin --tags
git checkout production-baseline-2026-02-17
```

Desde `origin/scraper` sin perder la referencia:

```bash
git fetch origin
git checkout -b mi-baseline origin/scraper
git reset --hard 06967fd   # solo si quieres quedarte exactamente en producción
```

## Comprobar que es el mismo build que producción

```bash
curl -s https://app.monitoria.org/build-id.txt
# Debe coincidir con frontend/public/build-id.txt tras npm run build en este commit
```

Versión en UI: **v 0.33 (en desarrollo)** (`frontend/src/config.js`).

## Prueba de despliegue local (Docker)

Requisitos: Docker, Docker Compose, credenciales AWS en `.env` (S3) para que el backend cargue mensajes.

```bash
cp credentials.example.txt .env   # editar AWS_* y JWT_SECRET_KEY
./scripts/deploy-local-test.sh
```

Abre http://localhost (o el puerto indicado). Comprueba:

- [ ] La página carga el dashboard y el logo
- [ ] Aparece el gráfico «Evolución de mensajes»
- [ ] «Buscar en mensajes» devuelve resultados
- [ ] `curl -s http://localhost/api/health` → `{"status":"healthy"}`
- [ ] `curl -s -X POST http://localhost/api/filter_messages -H "Content-Type: application/json" -d '{"page":1}'` → JSON con mensajes

Parar:

```bash
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml down
```

## Despliegue en EC2 (Monitor IA)

Instancia objetivo: **Monitor IA** (`eu-north-1`), la que sirve https://app.monitoria.org/

### 1. En el servidor

```bash
cd /ruta/al/repo
git fetch origin
git checkout cursor/deploy-baseline-a92b
git pull origin cursor/deploy-baseline-a92b
```

### 2. Variables de entorno

Archivo `.env` en la raíz (no subir a Git):

```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-north-1
S3_BUCKET=monitoria-data
JWT_SECRET_KEY=...
FRONTEND_PORT=80
```

### 3. Build y arranque

```bash
./scripts/deploy-local-test.sh --production
# o manualmente:
cd frontend && npm ci && npm run build && cd ..
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml build
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml up -d
```

### 4. Comprobación post-despliegue

Igual que la lista local, contra `https://app.monitoria.org/`.

### 5. Rollback

```bash
git checkout production-baseline-2026-02-17
./scripts/deploy-local-test.sh --production
```

## Flujo recomendado hasta producción

1. Trabajar solo en `cursor/deploy-baseline-a92b` (o ramas `cursor/*-a92b` creadas desde aquí).
2. Cada cambio: prueba local con `deploy-local-test.sh`.
3. Push y despliegue en EC2 de **staging** (mismo compose, otro puerto o subdominio) si lo tienes.
4. Cuando todo pase checklist → merge a rama de despliegue y `up -d` en producción.
5. **No** mezclar aún login/OAuth ni rama `database` hasta cerrar este baseline.

## Qué viene después (fuera de este baseline)

- Login sencillo (rama aparte desde este punto).
- PostgreSQL para escalar datos (rama `database`).
- Worker pytopicgram en la instancia detenida.
