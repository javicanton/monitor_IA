# Scraper de Telegram → PostgreSQL

## Fuentes de canales

1. **`monitored_channels`** en PostgreSQL (`status=active`, `discontinued=false`) — lista oficial.
2. Fallback: CSV local o S3 (`telegram_channels.csv`) si la tabla está vacía.

Importar lista inicial:

```bash
python3 scripts/import_monitored_channels.py
```

## Modos

| Script | Cuándo | Qué hace |
|--------|--------|----------|
| `run_scraper_full.sh` | Backfill | Hasta 10 000 msg/canal, sin límite de días |
| `run_scraper_unlimited.sh` | Backfill total | **Sin límite** de mensajes/canal (todo el historial) |
| `run_scraper_resume.sh` | Tras FloodWait / parada | Hasta 5 000 msg/canal, 10 s entre canales |
| `run_scraper_daily.sh` | Cada día (cron 03:00 UTC) | Últimos **3** días, hasta 500 msg/canal |
| `run_scraper_catchup.sh` | **Manual** tras hueco de ingesta | Últimos **14** días (configurable), hasta 800 msg/canal |
| `setup_scraper_schedule.sh` | Una vez en EC2 | Instala cron + muestra comandos de retoma |
| `run_scraper_postgres.sh` | Manual / legacy | Parámetros por `.env` |
| `ensure_scraper_venv.sh` | Una vez / si falla pandas | Crea/repara `.venv` con deps del scraper |

Todos usan **upsert**: mensajes nuevos + actualización de views/score; las **etiquetas** se conservan.

## Escrapeo completo (ahora)

```bash
cd ~/monitor_IA
source .venv/bin/activate

# Recomendado: tmux para no perder la sesión SSH
tmux new -s scraper-full

chmod +x scripts/run_scraper_full.sh scripts/run_scraper_daily.sh
./scripts/run_scraper_full.sh

# Más agresivo (canales muy activos):
SCRAPER_MAX_MESSAGES=15000 ./scripts/run_scraper_full.sh
```

Log en `logs/scraper_full_YYYYMMDD_HHMMSS.log`.

## Actualización diaria automática

```bash
chmod +x scripts/install_scraper_cron.sh
./scripts/install_scraper_cron.sh
```

Por defecto: **03:00 UTC** todos los días. Cambiar hora:

```bash
SCRAPER_CRON_TIME='0 5 * * *' ./scripts/install_scraper_cron.sh
```

Probar manualmente antes del cron:

```bash
./scripts/run_scraper_daily.sh
tail -f logs/scraper_daily_$(date -u +%Y%m%d).log
```

Variables opcionales en `.env`:

```bash
SCRAPER_DAYS=3
SCRAPER_MAX_MESSAGES=500
```

## Manual: recuperar hueco con ventana mayor (catch-up)

Cuando el cron diario ha estado parado varios días (p. ej. UI dice
«Último mensaje en base de datos: 2026-09-30»), el diario solo cubre
**3 días** y puede dejar huecos en el medio. Usa el catch-up.

### Cuándo usarlo

- Tras arreglar el venv / sesión Telethon / RDS y ver que faltan días.
- Si un día concreto (p. ej. 30-sep) tiene muy pocos mensajes frente a lo habitual.
- Siempre que quieras re-escrapear una ventana reciente sin hacer un full histórico.

### Comando (EC2, en tmux)

```bash
cd ~/monitor_IA

# Estado rápido
./scripts/scraper_status.sh
# (opcional) ver huecos por día en RDS:
# source .env
# psql "$DATABASE_URL" -c "
#   SELECT date(date_sent) AS dia, count(*)
#   FROM messages
#   WHERE date_sent > now() - interval '21 days'
#   GROUP BY 1 ORDER BY 1;
# "

tmux new -s scraper-catchup
./scripts/run_scraper_catchup.sh

# Seguir el log (otro panel tmux o SSH):
# tail -f logs/scraper_catchup_*.log
```

### Ventana a medida

Por defecto: **14 días**, 800 msg/canal. Ajusta según el hueco:

```bash
# Hueco ~1 semana (p. ej. desde 30-sep hasta hoy ~6–7 días) → margen 10–14
SCRAPER_DAYS=14 ./scripts/run_scraper_catchup.sh

# Hueco corto pero canales muy activos
SCRAPER_DAYS=10 SCRAPER_MAX_MESSAGES=1500 ./scripts/run_scraper_catchup.sh

# Equivalente sin el script (mismo efecto que el diario con ventana mayor)
SCRAPER_DAYS=14 SCRAPER_MAX_MESSAGES=800 ./scripts/run_scraper_daily.sh
```

### Notas

- Comparte el **lock** con el cron diario: no corre a la vez que `run_scraper_daily.sh`.
- Es **seguro relanzar** (upsert; no duplica; no pisa etiquetas).
- Tras terminar, recarga la UI: «Último mensaje en base de datos» y el gráfico por día
  deberían rellenar el hueco.
- Si Telegram impone FloodWait, el scraper espera solo; déjalo en tmux.

## Requisitos

- `DATABASE_URL` en `.env`
- Sesión Telethon autorizada (`~/.telethon/monitorIA.session`)
- `credentials.txt` o `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`
- **Venv del repo** con deps instaladas (el cron **no** hace `pip install` solo):

```bash
cd ~/monitor_IA
python3 -m venv .venv          # solo si no existe
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt -r backend/requirements.txt
```

Si ves `Error: No se pudo instalar pandas` o código **7**, el cron está usando un Python
sin deps (o no hay `.venv`). Repara con los comandos de arriba y relanza
`./scripts/run_scraper_daily.sh`.

## Límites de Telegram (FloodWait)

Si ves `A wait of N seconds is required (caused by ResolveUsernameRequest)`:

- **No es culpa del canal** (p. ej. `irinamar_z`): Telegram limita cuántos usuarios/canales puedes resolver por hora.
- Suele pasar tras un **escrapeo masivo** de muchos canales seguidos.
- El scraper **espera y reintenta** automáticamente (`FloodWaitError`).
- Pausa entre canales: `SCRAPER_CHANNEL_DELAY=8` (segundos, default 5).

Recomendaciones:

- No relances un full scrape justo después de otro.
- Usa `tmux` y deja que el script espere (18 h ≈ 65467 s es normal en casos graves).
- Para muchos canales nuevos: `SCRAPER_CHANNEL_DELAY=10 SCRAPER_MAX_MESSAGES=3000 ./scripts/run_scraper_full.sh`
- Canales inválidos (no FloodWait) → `discontinued=true` y se omiten en siguientes pasadas.

## Códigos de salida (cron)

`scraper.py` / `run_scraper_daily.sh` ahora fallan con código ≠ 0 cuando algo va mal
(antes muchos errores salían con exit 0 y el cron parecía “OK”):

| Código | Significado |
|--------|-------------|
| 0 | OK |
| 1 | Error inesperado |
| 2 | Credenciales Telegram no cargadas |
| 3 | Sin canales |
| 4 | Falta `DATABASE_URL` con `--postgres` |
| 5 | Sesión Telethon no autorizada (modo no interactivo) |
| 6 | Sesión Telethon rota a mitad de ejecución |
| 7 | Falta `.venv` o dependencias (pandas/telethon/…) |

Tras cada corrida diaria se escribe `logs/scraper_last_status.json`
(visible con `./scripts/scraper_status.sh`).

## Comprobar resultado

```bash
./scripts/scraper_status.sh

psql "$DATABASE_URL" -c "
  SELECT count(*) AS mensajes FROM messages;
  SELECT max(date_sent) AS ultimo_mensaje FROM messages;
  SELECT count(*) AS aristas FROM channel_edges;
  SELECT status, discontinued, count(*) FROM monitored_channels GROUP BY 1,2;
"
```
