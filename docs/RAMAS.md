# Ramas del proyecto (v1.0)

Solo dos ramas activas:

| Rama | Para qué sirve |
|------|----------------|
| **`funcional`** | Producción en https://app.monitoria.org (puerto 80). Versión **1.0**. |
| **`desarrollo`** | Pruebas en puerto 8080 (`./scripts/deploy-staging.sh`). Misma versión **1.0** hasta el próximo release. |

## Uso diario

```bash
git fetch origin

# Ver o desplegar la versión que funciona
git checkout funcional

# Trabajar en cosas nuevas
git checkout desarrollo
```

## Si algo sale mal

Vuelve a la rama que funciona y despliega:

```bash
git checkout funcional
git pull origin funcional
./scripts/deploy-local-test.sh --production
```

También puedes usar el tag fijo del 17-feb-2026:

```bash
git checkout production-baseline-2026-02-17
```

## Pasar cambios de desarrollo a funcional

1. Prueba en `desarrollo` (local o puerto 8080 con `./scripts/deploy-staging.sh`).
2. Abre un **Pull Request** en GitHub: `desarrollo` → `funcional`.
3. Cuando esté bien, merge y despliega desde `funcional`.

## Proteger `funcional` en GitHub

**Settings → Branches → Add rule** para la rama `funcional`:

- Require a pull request before merging
- Block force pushes
- Block branch deletion

Así no se rompe la versión mostrable por accidente.

## Probar `desarrollo` sin tocar la web pública

En el servidor, con `funcional` ya en el puerto 80:

```bash
git checkout desarrollo
git pull
./scripts/deploy-staging.sh    # puerto 8080
```

Parar la prueba:

```bash
./scripts/deploy-staging.sh --down
```

## Ramas antiguas (eliminadas o archivadas)

`main`, `production`, `develop`, `scraper`, `database`, `login` y ramas `cursor/*` ya no se usan. Trabaja solo en **`desarrollo`** y publica en **`funcional`**.
