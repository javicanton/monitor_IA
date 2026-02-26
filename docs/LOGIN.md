# Login y OAuth (app.monitoria.org)

El acceso a la app requiere estar logueado. Se soporta:

- **Email y contraseña** (registro en la app)
- **Google** (OAuth 2.0)
- **GitHub** (OAuth 2.0)
- **Apple** (Sign in with Apple)

## Variables de entorno

### Backend

Añade en tu `.env` o entorno de despliegue:

```bash
# URL del frontend (para redirigir tras login OAuth)
FRONTEND_URL=https://app.monitoria.org

# URL pública del backend (para redirect_uri de OAuth). Si el API está en el mismo dominio que el frontend, usa la misma base.
BACKEND_URL=https://api.monitoria.org

# Google (crear credenciales en https://console.cloud.google.com/apis/credentials)
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

# GitHub (crear OAuth App en https://github.com/settings/developers)
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx

# Apple (requiere cuenta Apple Developer; Service ID y Key para client_secret JWT)
APPLE_CLIENT_ID=org.monitoria.service
APPLE_CLIENT_SECRET=xxx   # JWT generado con tu key .p8
```

En **redirect URIs** de cada proveedor debes autorizar:

- Google: `https://api.monitoria.org/api/auth/google/callback` (o tu BACKEND_URL)
- GitHub: `https://api.monitoria.org/api/auth/github/callback`
- Apple: `https://api.monitoria.org/api/auth/apple/callback`

### Frontend

Si el frontend y el API están en dominios distintos, configura la URL del API:

```bash
REACT_APP_API_URL=https://api.monitoria.org
```

## Base de datos

El modelo `User` tiene nuevos campos opcionales: `oauth_provider`, `oauth_id`, y `password` es opcional para usuarios que solo usan OAuth.

Si ya tenías la base creada, puedes necesitar una migración para añadir las columnas. Con SQLAlchemy `create_all()` en una base nueva se crean todas las tablas; en una base existente no se añaden columnas nuevas. Opciones:

1. **Desarrollo**: borrar la base y volver a ejecutar `init_db.py`.
2. **Producción**: usar Flask-Migrate (Alembic) para generar y aplicar migraciones.

## Flujo

1. El usuario entra en `app.monitoria.org` → si no hay token, se redirige a `/login`.
2. En `/login` puede usar email/contraseña o un botón “Continuar con Google/Apple/GitHub”.
3. Al elegir un proveedor, el navegador va al backend `/api/auth/{provider}`, que redirige al proveedor.
4. Tras autorizar, el proveedor redirige a `/api/auth/{provider}/callback`. El backend crea o vincula el usuario, genera un JWT y redirige a `FRONTEND_URL/auth/callback?token=...`.
5. El frontend en `/auth/callback` guarda el token y redirige a la app.
