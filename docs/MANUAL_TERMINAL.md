# Manual básico de terminal — monitorIA

Para entrar al servidor y operar la app sin conocer el proyecto de memoria. Los comandos de abajo son los que ya usa el repo. Los datos de acceso (SSH, claves, base de datos) **no están en git**: rellénalos en la ficha y no los subas al repositorio.

Documentos relacionados: [RAMAS.md](RAMAS.md), [DEPLOY_BASELINE.md](DEPLOY_BASELINE.md), [DATOS.md](DATOS.md), [SCRAPER.md](SCRAPER.md).

---

## 1. Ficha de acceso (rellenar a mano)

Copia este bloque a un sitio privado (notas, gestor de contraseñas). No lo commits con datos reales.

```
SSH
  Host / IP:          ________________________________
  Usuario:            ________________________________
  Puerto:             ________   (suele ser 22)
  Clave privada:      ________________________________
  Comando que uso:    ssh -i ________________________________ ________@________________

Servidor
  Carpeta del repo:   ________________________________   (en la EC2 suele ser ~/monitor_IA)
  Región AWS:         eu-north-1
  Web pública:        https://app.monitoria.org
  Staging (pruebas):  http://HOST:8080

Datos (están en el .env del servidor, no en git)
  DATABASE_URL:       ________________________________
  S3 bucket:          monitoria-data
  Sesión Telegram:    ~/.telethon/monitorIA.session
  API Telegram:       (credentials.txt o TELEGRAM_API_ID / TELEGRAM_API_HASH en .env)
```

Ejemplo de forma del SSH, con huecos:

```bash
ssh -i RUTA_DE_LA_CLAVE -p PUERTO USUARIO@HOST
```

Si la clave pide passphrase, escríbela en el terminal cuando lo pida. No la pegues en este archivo.

---

## 2. Al entrar

```bash
cd ~/monitor_IA          # o la carpeta que anotaste arriba
pwd
git status
git branch
docker ps
```

Qué deberías ver:

| Qué | Significa |
|-----|-----------|
| Rama `funcional` | Estás en la versión de https://app.monitoria.org (puerto 80) |
| Rama `desarrollo` | Estás en pruebas (puerto 8080). No despliegues esto en el puerto 80 |
| Contenedores `Up` | La app está arrancada |

---

## 3. Comprobar que la web responde

En el servidor:

```bash
curl -s http://localhost/api/health
curl -s http://localhost:8080/api/health
curl -s https://app.monitoria.org/api/health
curl -s https://app.monitoria.org/build-id.txt
```

Una respuesta sana del API es `{"status":"healthy"}`.

Desde tu máquina, sin entrar por SSH, basta el `curl` a `https://app.monitoria.org/api/health`.

---

## 4. Ramas

Solo se usan dos:

| Rama | Para qué | Puerto |
|------|----------|--------|
| `funcional` | Producción (app.monitoria.org) | 80 |
| `desarrollo` | Probar antes de publicar | 8080 |

```bash
git fetch origin
git checkout funcional
git pull origin funcional

git checkout desarrollo
git pull origin desarrollo
```

Los cambios nuevos se prueban en `desarrollo`. Cuando estén bien, se abre un Pull Request `desarrollo` → `funcional`, se hace merge y se despliega desde `funcional`.

---

## 5. Desplegar producción

Hazlo solo desde la rama `funcional`, en el servidor.

```bash
cd ~/monitor_IA
git checkout funcional
git pull origin funcional
./scripts/deploy-local-test.sh --production
```

El script construye backend y frontend con Docker y los levanta en el **puerto 80**.

Comprobar:

```bash
curl -s http://localhost/api/health
docker ps
```

Parar producción (la web pública se cae):

```bash
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml down
```

Volver a la versión que ya funcionaba:

```bash
git checkout funcional
git pull origin funcional
./scripts/deploy-local-test.sh --production
```

Punto fijo antiguo (17-feb-2026), si hace falta ir más atrás:

```bash
git fetch origin --tags
git checkout production-baseline-2026-02-17
./scripts/deploy-local-test.sh --production
```

---

## 6. Desplegar pruebas (staging)

No toca la web del puerto 80. Hay que estar en `desarrollo`.

```bash
cd ~/monitor_IA
git checkout desarrollo
git pull origin desarrollo
./scripts/deploy-staging.sh --host-frontend
```

`--host-frontend` compila React en la máquina (recomendado en la EC2 pequeña; si no, el build dentro de Docker se queda sin memoria).

Comprobar y parar:

```bash
curl -s http://localhost:8080/api/health
docker ps | grep staging
docker logs monitoria-staging-backend --tail 50

./scripts/deploy-staging.sh --down
```

Solo reconstruir el backend de staging:

```bash
./scripts/deploy-staging.sh --backend-only
```

---

## 7. Logs y contenedores

```bash
docker ps
docker logs --tail 80 NOMBRE_DEL_CONTENEDOR
docker logs -f NOMBRE_DEL_CONTENEDOR
```

Nombres fijos de staging: `monitoria-staging-backend` y `monitoria-staging-frontend`. En producción el nombre sale en `docker ps` (el frontend del compose base se llama `monitoria-frontend`).

Reiniciar sin reconstruir:

```bash
docker restart NOMBRE_DEL_CONTENEDOR
```

El archivo de secretos del servidor es `~/monitor_IA/.env`. Para ver si el contenedor de staging tiene base de datos (no imprime la contraseña entera a propósito en el manual; si lo consultas, no lo copies a un chat):

```bash
docker exec monitoria-staging-backend printenv DATABASE_URL
```

Plantilla de variables (sin secretos): `.env.example` en la raíz del repo.

---

## 8. Scraper de Telegram

Los mensajes entran a PostgreSQL. Hace falta `DATABASE_URL` en `.env` y la sesión de Telethon ya autorizada.

Entorno Python (una vez, o si faltan librerías):

```bash
cd ~/monitor_IA
./scripts/setup-venv.sh
source .venv/bin/activate
```

Ver si está corriendo y el último log:

```bash
./scripts/scraper_status.sh
```

Actualización diaria (últimos 3 días, hasta 500 mensajes por canal). El cron del servidor la lanza a las **03:00 UTC**:

```bash
./scripts/run_scraper_daily.sh
tail -f logs/scraper_daily_$(date -u +%Y%m%d).log
```

Instalar o reinstalar ese cron:

```bash
chmod +x scripts/install_scraper_cron.sh
./scripts/install_scraper_cron.sh
crontab -l
```

Backfill largo (déjalo en `tmux` para que no se corte al cerrar SSH):

```bash
tmux new -s scraper
./scripts/run_scraper_full.sh
```

Salir de tmux sin matar el scraper: `Ctrl+b` y luego `d`. Volver: `tmux attach -t scraper`.

Si Telegram pide esperar (FloodWait), no relances otro full justo después. Para retomar tras una parada:

```bash
./scripts/run_scraper_resume.sh
```

Detalle de límites y canales: [SCRAPER.md](SCRAPER.md).

---

## 9. Desarrollo en tu portátil (sin servidor)

```bash
git clone URL_DEL_REPO
cd Telegram-app          # o el nombre de la carpeta que te quede

cp .env.example .env     # rellena DATABASE_URL, JWT_SECRET_KEY, AWS si hace falta
./scripts/setup-venv.sh
source .venv/bin/activate

cd frontend && npm install && cd ..
```

Arranque con Docker en el puerto 8080 (no publica la web):

```bash
./scripts/deploy-local-test.sh
curl -s http://localhost:8080/api/health
```

Parar:

```bash
docker compose -f docker-compose.yml -f docker-compose.deploy-test.yml down
```

Backend y frontend sueltos, sin Docker:

```bash
source .venv/bin/activate
python backend/app.py          # http://localhost:5001  (revisa cómo arranca app.py si el cwd importa)

cd frontend
npm start                      # http://localhost:3000
```

---

## 10. Cosas que no hay que hacer

- No hagas `git push --force` sobre `funcional`.
- No ejecutes `./scripts/deploy-local-test.sh --production` estando en `desarrollo`.
- No pegues el `.env`, la clave SSH ni `DATABASE_URL` en un commit, un issue o un chat.
- No borres `~/.telethon/monitorIA.session`: sin esa sesión el scraper pide login de Telegram otra vez.
- No lances dos scrapers a la vez (`flock` en el cron diario está para evitarlo).
