# Gestión de canales monitorizados (roadmap)

Documento de diseño para cuando el sistema de login esté operativo.  
**Implementación temporal (sin login):** botón «Incluir canales» → correo a `monitoria@unir.net`.

## Estado actual (sin login)

- `POST /api/channels/suggest` — formulario público; envía email al equipo.
- Tabla `monitored_channels` en PostgreSQL — lista oficial del scraper.
- CSV en S3 (`telegram_channels.csv`) — copia manual revisada; importable con `scripts/import_monitored_channels.py`.
- Tabla `channel_edges` — grafo de reenvíos entre canales (scraper).

## Modelo de datos (implementado)

### `monitored_channels`

| Campo | Descripción |
|-------|-------------|
| `username` | Usuario Telegram (único, sin @) |
| `title` | Título visible (opcional) |
| `status` | `active` \| `error` \| `disabled` |
| `discontinued` | `true` si el canal falló o está dado de baja |
| `source` | `csv_import` \| `manual` \| `proposal` \| `forward_discovery` |
| `last_error` | Último error del scraper |
| `last_scraped_at` | Última ejecución exitosa |

### `channel_edges`

| Campo | Descripción |
|-------|-------------|
| `source_channel_id` | Canal origen del reenvío |
| `target_channel_id` | Canal que publicó el reenvío |
| `forward_count` | Número acumulado de reenvíos detectados |
| `last_seen_at` | Última vez visto |

### Futuro: `channel_proposals` (con login)

| Campo | Descripción |
|-------|-------------|
| `username` | Canal propuesto |
| `note` | Comentario del usuario |
| `user_id` | FK `users` |
| `status` | `pending` \| `approved` \| `rejected` |
| `reviewed_by` | Admin |
| `reviewed_at`, `admin_note` | Auditoría |

## API futura (con login)

| Endpoint | Rol | Acción |
|----------|-----|--------|
| `POST /api/channels/propose` | Usuario | Crear propuesta |
| `GET /api/channels/proposals/mine` | Usuario | Ver sus propuestas |
| `GET /api/admin/channel-proposals` | Admin | Cola pendiente |
| `POST /api/admin/channel-proposals/:id/approve` | Admin | → `monitored_channels` |
| `POST /api/admin/channel-proposals/:id/reject` | Admin | Rechazar |

## Flujo objetivo

1. Usuario propone canal (autenticado).
2. Admin aprueba → fila en `monitored_channels` con `status=active`.
3. Scraper lee solo `active` y `discontinued=false`.
4. Errores de Telegram → `status=error`, `discontinued=true`.
5. Reenvíos frecuentes → candidatos en `channel_discoveries` (futuro) o propuesta automática.

## Descarga de datos

- `GET /download_channel_graph` — ZIP con `monitored_channels.csv` y `channel_edges.csv`.
- Botón «Descargar canales» en la UI (junto a «Descargar mensajes»).

### `monitored_channels.csv` (nodos)

Incluye **todos** los canales de la tabla: activos y descontinuados (`discontinued=true`, `status=error`).
El scraper solo monitoriza filas con `status=active` y `discontinued=false`.

Los canales pasan a descontinuados cuando:

1. El scraper falla al acceder (username inválido, canal borrado, etc.).
2. Se importan con `discontinued=true` o `status=error` en un CSV extendido (`username,title,discontinued,status`).
3. Tras un error, una reimportación del CSV simple **no los reactiva** (salvo `--reactivate-errors`).

### `channel_edges.csv` (aristas)

Solo se rellena cuando el scraper corre con `--postgres` y detecta **reenvíos** entre canales.
Si está vacío, ejecuta al menos una pasada del scraper tras desplegar esta funcionalidad:

```bash
cd backend && python3 scraper.py --postgres --non-interactive --days 30 --max-messages 500
```
