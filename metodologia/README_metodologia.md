# Paquete metodológico · Artículo RECO

Punto de entrada: **`GUIA_implementacion.md`** (paso a paso sobre la infraestructura de monitorIA).

| Archivo | Para qué | Estado |
|---|---|---|
| `GUIA_implementacion.md` | Pasos 1 a 12, calendario hasta el 23 de octubre | Léela primero |
| `01_canales_semilla.csv` | 17 canales documentados + 9 huecos | Falta rellenar handles |
| `02_lexico.yaml` | Capas A y B, veto | v0.1 |
| `03_filtro_lexico.py` | Reglas R1 a R4 (`--test` ejecuta 7 casos) | Probado |
| `04_validacion.py` | Muestra en ciego, kappa, precisión y exhaustividad | Probado con datos sintéticos |
| `../aws/sql/*.sql` | Esquema parametrizable, candidatos de snowball, comprobaciones | Revisado, sin ejecutar en RDS |
| `../aws/env.reco.example` | Conexión aislada (URL entre comillas) y sesión Telethon propia | Plantilla |
| `../aws/preparar_monitored.py` | Semilla CSV a formato de importación y metadatos | Con tests |
| `../aws/reco_guard.sh` | Exige `search_path` y vigila `public.messages` | Con tests (psql simulado) |
| `../aws/run_reco_unattended.sh` | Fases A/B con `nohup setsid`, `flock` y estado en `logs/reco_status.json` | Sintaxis revisada, sin lanzar |
| `../aws/run_reco_backfill.sh` | Backfill. No cae al CSV de S3 si la semilla está vacía | Sintaxis revisada, sin lanzar |
| `../aws/reco_filtro_db.py` | Filtro sobre la base (cursor `WITH HOLD`) y exportaciones | Revisado, sin ejecutar en RDS |

## Búsqueda de huecos (términos para la búsqueda de Telegram)

| Tipo | Términos de partida | Dónde más mirar |
|---|---|---|
| T1 negacionismo | estafa climática, timo del clima, el CO2 es vida | Canales de divulgadores negacionistas citados por Maldita o Chequeado |
| T5 rural/agro | guerra al campo, Pacto Verde agricultores, ganadería ONU | Canales de protesta agraria 2024 |
| T6 energía/motor | apagón provocado, coche eléctrico obligatorio, ZBE | Comunidades de motor y de renovables escépticas |
| LatAm | globalismo, Agenda 2030 soberanía, Gran Reseteo | Informes de Chequeado, AFP Factual, Ecuador Chequea |

## Notas para el artículo

- Guardar el commit de monitorIA y la fecha de captura: son columnas de la tabla de canales del anexo.
- Anotar la mortalidad de canales: es un dato en sí.
- Aunque se aloje en la infraestructura de monitorIA, el corpus se construye con criterios propios; decirlo explícitamente.
- Reportar la precisión de R3 por separado.
