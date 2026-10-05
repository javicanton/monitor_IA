# Autenticación (magic link)

Acceso restringido por **lista de correos autorizados**. El usuario recibe un enlace de un solo uso (TTL 15 min) por email.

OAuth (Google / GitHub) está preparado en stubs (`backend/auth/providers/`) para una fase posterior.

## Flujo

1. El usuario introduce su email en `/login`.
2. `POST /auth/login-request` comprueba la allowlist (sin revelar si el correo está o no).
3. Si está autorizado, se crea un **código corto** en BD y se envía
   `{AUTH_FRONTEND_URL}/auth/verify?code=...` (sin `<a href>` trackeable).
4. El frontend llama a `POST /auth/verify-magic-link` con `{code}` y guarda el JWT.
5. Las rutas de datos del API exigen `Authorization: Bearer <token>`.

## Allowlist

**Fuentes (se fusionan):**

1. Variable de entorno `ALLOWED_EMAILS` (coma-separada; opcional `email:role`)
2. Archivo **`backend/allowed_emails.txt` en el servidor** (uno por línea: `email [role]`)

Si un email está en ambas, **gana el archivo**. Así las invitaciones admin (que escriben en el archivo) funcionan aunque exista `ALLOWED_EMAILS` en el `.env`.

La allowlist se recarga al cambiar el mtime del archivo (no hace falta reiniciar el backend tras editarlo o invitar).

Roles: `user` (por defecto) o `admin`.

> Repo **público**: no subir la allowlist real. Plantilla versionada: `backend/allowed_emails.example.txt`. En el EC2: `cp backend/allowed_emails.example.txt backend/allowed_emails.txt` y editar.

Ejemplos:

```env
ALLOWED_EMAILS=admin@example.com:admin,usuario@example.com
```

```text
# backend/allowed_emails.txt  (solo en el servidor)
admin@example.com admin
usuario@example.com
```

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `ALLOWED_EMAILS` | Lista de correos (opcional si usas el archivo) |
| `ALLOWED_EMAILS_FILE` | Ruta alternativa al archivo de allowlist |
| `AUTH_FRONTEND_URL` | Base del frontend para el enlace (`https://app.monitoria.org`) |
| `AUTH_DEV_RETURN_LINK` | `1` en desarrollo: incluye el magic link en la respuesta JSON |
| `MAIL_*` / SES | Envío real del correo (si no hay mail, el enlace se registra en logs) |
| `JWT_SECRET_KEY` | Firma de tokens |
| `SECRET_KEY` | Firma de magic links |
| `JWT_ACCESS_TOKEN_HOURS` | Caducidad del JWT (por defecto 12) |

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/auth/login-request` | Solicitar magic link |
| `GET` | `/auth/verify-magic-link/<token>` | Canjear enlace por JWT |
| `GET` | `/auth/me` | Usuario actual |
| `POST` | `/auth/logout` | Cierre de sesión (el cliente borra el token) |
| `POST` | `/auth/admin/invite` | **Admin:** añadir a allowlist + generar magic link (opcional enviar email) |
| `GET` | `/auth/admin/activity` | **Admin:** listar actividad |
| `GET` | `/auth/admin/activity/export` | **Admin:** CSV de actividad |

### Invitar / generar enlace (admin)

Desde el menú de perfil → **Invitar / generar enlace**, o por API:

```bash
curl -sS -X POST "https://app.monitoria.org/api/auth/admin/invite" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"usuario@ejemplo.com","role":"user","send_email":true}'
```

Respuesta: `magic_link` (siempre), `email_sent`, `allowlist_created`. Si el correo no llega (spam, SES, dominio institucional), copia el enlace y envíaselo por otro canal. Caduca en 15 minutos.

Con nginx (`/api/` → backend), el frontend llama a `/api/auth/...`, que llega como `/auth/...`.

También se registra el prefijo `/api/auth` en el backend por compatibilidad.

## Desarrollo local sin correo

```env
AUTH_DEV_RETURN_LINK=1
AUTH_FRONTEND_URL=http://localhost:3000
ALLOWED_EMAILS=tu@email.com:admin
```

La respuesta de `login-request` incluirá `dev_magic_link` para abrir el enlace en el navegador.

## Frontend

- `AuthProvider` + `ProtectedRoute` en `App.js`
- Login: `frontend/src/auth/components/LoginForm.js`
- Verificación: `/auth/verify?token=...`
- Botones Google/GitHub: visibles como “próximamente” hasta `REACT_APP_OAUTH_ENABLED=true`
- Menú de usuario: nombre + avatar (iniciales) + plan (`Free` / `Member` derivado del rol por ahora)
- Pedir acceso: enlace «Regístrate y pide acceso» → `REACT_APP_ACCESS_REQUEST_URL` (Tally / Google Form). Si no se define, fallback a `mailto:monitoria@unir.net`.

En el build del frontend (staging/producción):

```bash
export REACT_APP_ACCESS_REQUEST_URL='https://tally.so/r/xxxx'
# o pasar como build-arg en docker compose
```

## Actividad de usuarios (login + API)

Tabla PostgreSQL `user_activities` (se crea con `db.create_all`).

| Acción | Cuándo |
|--------|--------|
| `login` | Magic link canjeado |
| `logout` | `POST /auth/logout` |
| `filter_messages` | Listado/filtros/búsqueda |
| `load_more` | Paginación |
| `messages_over_time` | Gráfico |
| `label_message` | Etiquetado |
| `download_filtered_messages` / `download_channel_graph` / `export_relevants` | Descargas |
| `admin_*` | Acciones admin de topics |

Consulta (solo admin):

```bash
curl -sS "https://app.monitoria.org/api/auth/admin/activity?limit=50" \
  -H "Authorization: Bearer $TOKEN"
# filtros opcionales: &email=user@example.com&action=login&days=7
```

Descarga CSV (últimos N días, default 7) — también desde el menú de perfil (usuarios admin):

```bash
curl -sS "https://app.monitoria.org/api/auth/admin/activity/export?days=7" \
  -H "Authorization: Bearer $TOKEN" -o activity.csv
```

En SQL:

```sql
SELECT created_at, email, action, meta, ip
FROM user_activities
ORDER BY created_at DESC
LIMIT 50;
```

## Fase 2 (OAuth)

Implementar `GoogleOAuthProvider` / `GitHubOAuthProvider` y rutas `/auth/oauth/...`. La allowlist por email sigue siendo la puerta de entrada.
