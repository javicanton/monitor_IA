# Autenticación (magic link)

Acceso restringido por **lista de correos autorizados**. El usuario recibe un enlace de un solo uso (TTL 15 min) por email.

OAuth (Google / GitHub) está preparado en stubs (`backend/auth/providers/`) para una fase posterior.

## Flujo

1. El usuario introduce su email en `/login`.
2. `POST /auth/login-request` comprueba la allowlist (sin revelar si el correo está o no).
3. Si está autorizado, se envía un enlace a `{AUTH_FRONTEND_URL}/auth/verify?token=...`.
4. El frontend llama a `GET /auth/verify-magic-link/<token>` y guarda el JWT.
5. Las rutas de datos del API exigen `Authorization: Bearer <token>`.

## Allowlist

**Prioridad:**

1. Variable de entorno `ALLOWED_EMAILS` (coma-separada; opcional `email:role`)
2. Archivo `backend/allowed_emails.txt` (uno por línea: `email [role]`)

Roles: `user` (por defecto) o `admin`.

Ejemplos:

```env
ALLOWED_EMAILS=admin@monitoria.org:admin,usuario@unir.net
```

```text
# backend/allowed_emails.txt
admin@monitoria.org admin
usuario@unir.net
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

## Fase 2 (OAuth)

Implementar `GoogleOAuthProvider` / `GitHubOAuthProvider` y rutas `/auth/oauth/...`. La allowlist por email sigue siendo la puerta de entrada.
