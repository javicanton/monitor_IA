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
| `run_scraper_daily.sh` | Cada día (cron 03:00 UTC) | Últimos 3 días, hasta 500 msg/canal |
| `setup_scraper_schedule.sh` | Una vez en EC2 | Instala cron + muestra comandos de retoma |
| `run_scraper_postgres.sh` | Manual / legacy | Parámetros por `.env` |

Los tres usan **upsert**: mensajes nuevos + actualización de views/score; las **etiquetas** se conservan.

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

## Requisitos

- `DATABASE_URL` en `.env`
- Sesión Telethon autorizada (`~/.telethon/monitorIA.session`)
- `credentials.txt` o `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`

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

## Comprobar resultado

```bash
psql "$DATABASE_URL" -c "
  SELECT count(*) AS mensajes FROM messages;
  SELECT count(*) AS aristas FROM channel_edges;
  SELECT status, discontinued, count(*) FROM monitored_channels GROUP BY 1,2;
"
```
