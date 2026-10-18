# Guía de implementación · corpus RECO en la infraestructura de monitorIA

Preparada el 16 de octubre de 2026 tras leer el repositorio [javicanton/monitor_IA](https://github.com/javicanton/monitor_IA) (`docs/SCRAPER.md`, `docs/DATOS.md`, `backend/models.py`, `backend/scraper.py`, `backend/pg_upsert.py`).

**Estado de lo preparado:** el filtro léxico y la validación están probados con datos sintéticos. Los scripts de `aws/` (en la raíz del repo, no dentro de esta carpeta) compilan. La revisión del 18 de octubre corrigió la URL sin comillas, el cursor de servidor, el esquema fijo `reco.` y la caída al CSV de S3. **Siguen sin ejecutarse contra la RDS ni contra Telegram** desde el agente de Cursor: el piloto del paso 5 hay que hacerlo en la EC2, con la sesión Telethon ya autorizada a mano.

## Lo que he visto en el repo (y cambia el plan)

| Hallazgo | Consecuencia |
|---|---|
| Los mensajes ya no se guardan en S3 sino en **PostgreSQL en RDS** (S3 queda como modo antiguo con Parquet/JSON) | La integración se hace en la base de datos, no en S3. S3 se usa para modelos de tópicos y copias |
| El scraper propio (`backend/scraper.py`, Telethon) lee canales de la tabla `monitored_channels`, guarda con upsert en `messages` y registra reenvíos en `channel_edges` | Sirve tal cual: no hace falta escribir otro recolector |
| El panel hace join de **todos** los canales y mensajes de la base | Meter el corpus en las tablas actuales lo mezclaría en el panel, en los contadores y en el grafo |
| `channel_edges` guarda (origen del reenvío, canal que reenvía) | Da el grafo de reenvíos y los candidatos de snowball sin código nuevo |
| `--days N` corta al llegar a mensajes más antiguos; `--max-messages 0` quita el tope | Cubre la ventana sep 2024 a dic 2025 sin bajar todo el historial |

## Decisión de diseño: esquema aislado `reco`

Una base, dos esquemas. `monitorIA` sigue en `public`. RECO vive en `reco` con las mismas tablas. La conexión de RECO añade `search_path=reco` a `DATABASE_URL`, así que **el scraper, `init_postgres.py` e `import_monitored_channels.py` escriben en `reco.*` sin tocar su código**. Ventajas: no hay mezcla posible, el corpus es citable y reproducible (un esquema = un corpus), y se puede promover a `public` después si quieres verlo en la herramienta. La etiqueta de corpus va en `reco.reco_canales` (tipo, país, procedencia) y en la columna `corpus='RECO'` de las exportaciones.

## Paso a paso

### 1. Rellenar la semilla (manual, hoy)
Abre `01_canales_semilla.csv`. Para cada canal documentado busca el handle en Telegram y rellena `handle_telegram`, `vigente_2024_25`, `suscriptores`, `tipo_provisional` real y `incluir` (0 si cae). Busca los 9 huecos con los términos del README. Meta: 25 a 40 canales, mitad ES y mitad LatAm. Luego:
```bash
python3 aws/preparar_monitored.py metodologia/01_canales_semilla.csv
# genera aws/reco_monitored.csv y aws/reco_canales_insert.sql
# Ensayo: --schema reco_test
```

### 2. Preparar la EC2
```bash
ssh <ec2>; cd ~/monitor_IA
git status            # no mezcles esto con la rama de producción
cp -r /ruta/a/metodologia/aws ./aws          # o súbelo con scp; no lo comitees a main
cp aws/env.reco.example .env.reco && chmod 600 .env.reco
nano .env.reco        # rellena USUARIO, PASSWORD y HOST. Deja las comillas de DATABASE_URL.
```

### 3. Crear el esquema y las tablas
```bash
set -a; source .env.reco; set +a
psql "$DATABASE_URL_ADMIN" -v ON_ERROR_STOP=1 -v schema="${RECO_SCHEMA:-reco}" -f aws/sql/00_schema_reco.sql
psql "$DATABASE_URL" -c "SHOW search_path;"       # DEBE decir exactamente: reco
.venv/bin/python scripts/init_postgres.py          # crea channels, messages, ... dentro de reco
psql "$DATABASE_URL" -c "\dt reco.*"
```
Si `SHOW search_path` no dice `reco`, **para**: cualquier paso siguiente escribiría en `public`. Con SQLAlchemy y psycopg2, `options=-csearch_path%3Dreco` en la URL suele funcionar; si tu RDS lo rechaza, alternativa: `ALTER ROLE tu_usuario SET search_path = reco, public;` con un usuario dedicado solo para RECO.

### 4. Sesión de Telegram propia
Usa una sesión distinta de la del cron diario (dos procesos con la misma sesión se pisan):
```bash
export TELEGRAM_SESSION_PATH=~/.telethon/reco.session
# Primera vez, interactivo: pedirá teléfono y código. Ejecuta el piloto del paso 5 sin --non-interactive una vez.
```
Elige una hora distinta de las 03:00 UTC del cron diario.

### 5. Importar semilla y piloto
```bash
set -a; source .env.reco; set +a
.venv/bin/python scripts/import_monitored_channels.py --path aws/reco_monitored.csv
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f aws/reco_canales_insert.sql
psql "$DATABASE_URL" -c "SELECT count(*) FROM monitored_channels;"

# Control: mensajes en monitorIA antes del piloto
psql "$DATABASE_URL" -t -A -c "SELECT count(*) FROM public.messages;"

# Piloto: 2 canales, 30 días, 200 mensajes. Pasa un CSV solo con esos dos handles
# (primera columna). --channels-file evita que, si la tabla viniera vacía, el scraper
# cargue telegram_channels.csv desde S3.
cd backend && ../.venv/bin/python scraper.py --postgres --non-interactive \
  --channels-file /ruta/piloto_2_canales.csv --days 30 --max-messages 200 && cd ..
# Después del piloto:
psql "$DATABASE_URL" -t -A -c "SELECT count(*) FROM public.messages;"   # debe ser IGUAL que antes
psql "$DATABASE_URL" -c "SELECT count(*) FROM messages;"                   # debe ser > 0 (esquema reco)
```
Si `public.messages` cambió, borra lo ocurrido y revisa el `search_path`.

### 6. Backfill de la semilla (desatendido)
```bash
./aws/run_reco_unattended.sh A     # backfill + filtro léxico + exportaciones; vuelve al instante
./aws/run_reco_unattended.sh status   # estado y últimas líneas del log, desde cualquier sitio
```
Corre con `nohup setsid` en la EC2: puedes cerrar el portátil y la sesión SSH. Hace tres comprobaciones solo: aborta si `search_path` no es `reco`, y al terminar alerta si `public.messages` cambió. Si hay FloodWait, el scraper espera solo. La fase B (tras curar el snowball) se lanza igual con `B`.
Es seguro relanzar (upsert). Si hay FloodWait, el scraper espera solo. Con 30 canales de actividad media cuenta con horas, no minutos.

### 7. Snowball (2 rondas)
```bash
psql "$DATABASE_URL" -f aws/sql/10_snowball_candidatos.sql > candidatos_ronda1.txt
```
Revisa los candidatos con los umbrales del diseño (público, ≥1.000 suscriptores, país inferible, activo en ≥2 de las 3 ventanas, ≥200 mensajes). Apunta los admitidos en el CSV de semilla con `origen=snowball`, repite `preparar_monitored.py`, importa y lanza otra vez el backfill. Haz una segunda ronda. **Para cuando una ronda deje de aportar tópicos o temas nuevos**, no por volumen; con el calendario, tope práctico: lunes 19 de octubre.

### 8. Filtro léxico en la base
```bash
.venv/bin/pip install pyyaml psycopg2-binary pandas   # si falta
.venv/bin/python aws/reco_filtro_db.py --lexico metodologia/02_lexico.yaml --version v0.1
psql "$DATABASE_URL" -f aws/sql/20_comprobaciones.sql
```
Guarda el reparto por regla. Si `NONE` es enorme y R3 pequeño, bien; si R4 (veto) pesa mucho, el ruido del Mundial 2030 está siendo importante y conviene decirlo en el anexo.

### 9. Validación (400 mensajes)
```bash
# Exporta el corpus BRUTO de la ventana con las marcas (sin --solo-incluidos)
.venv/bin/python aws/reco_filtro_db.py --export corpus_bruto.csv
python3 metodologia/04_validacion.py muestra --in corpus_bruto.csv --n 400 --out-dir validacion/
# Repartir codificador_1.csv y codificador_2.csv (columna 'relevante' 0/1), después:
python3 metodologia/04_validacion.py evaluar --dir validacion/
```
Si la precisión de R3 sale baja, ajusta `02_lexico.yaml`, sube la versión (`--version v0.2`) y repite el paso 8.

### 10. Tópicos
Dos caminos; elige uno antes del viernes:
- **Worker de tópicos de monitorIA** (`docs/TOPICS.md`): ya está montado para >1M mensajes y escribe en `message_topics`. Apuntarlo al esquema `reco` debería funcionar con `.env.reco`, pero no lo he verificado y toca una instancia aparte.
- **pytopicgram sobre la exportación** (`--export corpus_reco.csv --solo-incluidos`): más simple y reproducible para el artículo, y encaja con que su uso aún está en desarrollo. Cuando me confirmes el formato de entrada que espera, escribo el script de tópicos.

### 11. Red y series (salidas listas para análisis)
```bash
psql "$DATABASE_URL" -c "\copy (SELECT s.username AS origen, t.username AS destino, e.forward_count AS peso FROM channel_edges e JOIN channels s ON s.id=e.source_channel_id JOIN channels t ON t.id=e.target_channel_id) TO 'aristas.csv' CSV HEADER"
.venv/bin/python aws/reco_filtro_db.py --export corpus_reco.csv --solo-incluidos
```
Con `aristas.csv` (red de reenvíos) y `corpus_reco.csv` (mensajes con fecha, tipo y país) se hacen la red, las comunidades y las series temporales por ventana.

### 12. Qué hacer con la herramienta
- **Hasta el 23 de octubre**: dejar RECO aislado en `reco`. Es lo que garantiza que el corpus no cambia debajo del análisis.
- **Después**: si quieres verlo en el panel, la opción más limpia es una instancia de staging (puerto 8080, `docs/DATOS.md`) con `DATABASE_URL` apuntando al esquema `reco`. Promover a `public` es posible, pero exige añadir una columna `corpus` en `messages` y filtrar en el panel; decídelo cuando el artículo esté enviado.

## Calendario (desde hoy, domingo 18 de octubre)

Todo se ejecuta en la EC2, desacoplado de tu portátil (`aws/run_reco_unattended.sh`). Tú solo intervienes en lo humano: handles, login de Telegram, curación de snowball y anotación.

| Día | Qué ocurre | Quién |
|---|---|---|
| **Dom 18 (hoy)** | Handles de la semilla (paso 1), esquema y piloto (pasos 2 a 5, incluido el login de Telegram una vez por SSH) y **lanzar Fase A por la noche** | Javi + Cursor |
| Lun 19 | Fase A termina durante el día. Curar candidatos de snowball ronda 1 (`out/candidatos_snowball_A.txt`) y lanzar Fase B por la noche | Javi |
| Mar 20 | Fase B termina. Revisar saturación; si aporta temas nuevos, una ronda más (Fase B de nuevo). Lanzar anotación de la muestra de validación | Javi + Pablo |
| Mié 21 | Validación cerrada, ajuste de léxico si procede (nueva versión y repetir filtro). Red y series (Cursor) | Javi + Cursor |
| Jue 22 | Tópicos y figuras. Primeras versiones de 4.1 a 4.3 | Javi + Cursor |
| **Vie 23** | **Congelar corpus y resultados** (`pg_dump --schema=reco` a S3 como copia citable) | Javi |

Una ronda de snowball menos que en el plan original: con 5 días, dos rondas completas son el máximo realista.

## Riesgos concretos

| Riesgo | Mitigación |
|---|---|
| FloodWait al resolver muchos canales nuevos | `SCRAPER_CHANNEL_DELAY=10`, tmux, no relanzar justo después |
| Escritura accidental en `public` | `SHOW search_path` y el control de contadores del paso 5 |
| Canales de 2022 caídos | `monitored_channels.last_error` y `discontinued` los marcan solos; es un dato del anexo (mortalidad) |
| `--max-messages 0` en canales enormes | Si un canal domina el volumen, límite por canal con `SCRAPER_MAX_MESSAGES=` y decláralo |
| Cuenta de Telegram usada para scraping | Cuenta del proyecto, solo canales públicos, ritmo conservador |
