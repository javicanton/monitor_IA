# Estrategia de ramas y despliegues

## Resumen

| Rama | URL / destino | Quién toca | Propósito |
|------|----------------|------------|-----------|
| **`production`** | https://app.monitoria.org | Solo merge vía PR aprobado | Lo que está en vivo |
| **`cursor/staging-next-a92b`** | Puerto **8080** o `staging.app.monitoria.org` | Desarrollo diario | Login, SQL, nuevas features |
| **`cursor/deploy-baseline-a92b`** | (histórica) | Archivada | Punto donde se creó el baseline; usar `production` |

Tag inmutable de referencia: **`production-baseline-2026-02-17`** → commit `06967fd` (UI v0.33 desplegada en febrero).

## Flujo de trabajo

```
cursor/staging-next-a92b  ──PR──►  production  ──deploy──►  app.monitoria.org :80
        │
        └── deploy-staging.sh ──►  :8080  (misma EC2, sin tocar producción)
```

1. **Nunca** commits directos en `production`.
2. Trabajar en `cursor/staging-next-a92b` (o ramas `cursor/<feature>-a92b` creadas desde staging).
3. Probar con `./scripts/deploy-staging.sh` en la instancia EC2 (puerto 8080).
4. Cuando esté listo: PR `cursor/staging-next-a92b` → `production`, revisar, merge.
5. En el servidor de producción: `git checkout production && git pull && ./scripts/deploy-local-test.sh --production`.

## Proteger `production` en GitHub

Si no está aplicado aún, en **Settings → Branches → Add rule**:

- Branch name pattern: `production`
- Require a pull request before merging
- Require approvals: 1 (opcional)
- Do not allow bypassing the above settings
- Restrict who can push: solo maintainers (opcional)
- **No** permitir force push ni borrado

Desde CLI (mantenedor):

```bash
gh api repos/javicanton/monitor_IA/branches/production/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

## Despliegue staging (puerto 8080)

En la instancia **Monitor IA**, con producción ya corriendo en el puerto 80:

```bash
git fetch origin
git checkout cursor/staging-next-a92b
git pull
./scripts/deploy-staging.sh
```

Comprobar: `http://<IP-EC2>:8080/` o configurar DNS `staging.app.monitoria.org` → misma IP.

Parar solo staging (producción sigue en 80):

```bash
./scripts/deploy-staging.sh --down
```

## Despliegue producción

Solo desde la rama `production`:

```bash
git checkout production
git pull origin production
./scripts/deploy-local-test.sh --production
```

## Rollback producción

```bash
git checkout production-baseline-2026-02-17
./scripts/deploy-local-test.sh --production
# Luego fijar production en ese commit con un PR de emergencia
```

## Crear una rama de feature

```bash
git fetch origin
git checkout cursor/staging-next-a92b
git pull
git checkout -b cursor/mi-feature-a92b
# ... commits ...
git push -u origin cursor/mi-feature-a92b
# PR hacia cursor/staging-next-a92b (no hacia production directamente)
```
