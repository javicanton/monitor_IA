# Ramas del proyecto

## Modelo actual

| Rama / tag | Para qué sirve |
|------------|----------------|
| **`main`** | **Producción** en https://app.monitoria.org (con login magic link). Rama principal protegida. |
| **`desarrollo`** | Staging / pruebas en puerto 8080 (`./scripts/deploy-staging.sh`). |
| **`backup/production-pre-login`** | Copia congelada de producción **antes** del login. |
| Tag **`production-stable-pre-login-2026-09-30`** | Mismo punto de rollback (recomendado). |
| Tag **`production-baseline-2026-02-17`** | Baseline antiguo (feb 2026). |

## Uso diario

```bash
git fetch origin

# Producción
git checkout main
git pull origin main

# Nuevas funcionalidades
git checkout desarrollo
git pull origin desarrollo
```

## Si algo sale mal en producción (rollback sin login)

```bash
git fetch origin --tags
git checkout production-stable-pre-login-2026-09-30
# o: git checkout backup/production-pre-login
./scripts/deploy-local-test.sh --production
```

## Pasar cambios a producción

1. Probar en `desarrollo` (staging :8080).
2. Abrir PR: `desarrollo` → **`main`**.
3. Merge y desplegar desde `main`:

```bash
git checkout main
git pull origin main
./scripts/deploy-local-test.sh --production
```

## Proteger `main` en GitHub

**Settings → Rules → Rulesets** (o Branch protection rules) para `main`:

- Require a pull request before merging
- Block force pushes
- Block branch deletion
- (Opcional) Require approvals

## Datos sensibles (repo público)

No versionar:

- `backend/allowed_emails.txt` → usar `allowed_emails.example.txt` como plantilla; el real solo en el servidor
- Listas de canales CSV locales
- Credenciales AWS / `.env`

La allowlist y secretos viven en el EC2 (`.env` + `allowed_emails.txt`), no en Git.

## Ramas obsoletas

Tras la limpieza: no usar `funcional`, `production`, `develop`, `scraper`, `database`, `login` ni `cursor/*` antiguas como líneas de trabajo. Staging = `desarrollo`; producción = `main`.
