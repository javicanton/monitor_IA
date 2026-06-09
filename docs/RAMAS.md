# Ramas del proyecto

Dos ramas con nombres sencillos:

| Rama | Para qué sirve |
|------|----------------|
| **`funcional`** | La herramienta **como está ahora** y se puede mostrar (app.monitoria.org). No desarrollar aquí. |
| **`desarrollo`** | **Nuevas funcionalidades** (login, SQL, etc.). Se prueba aquí antes de pasar a `funcional`. |

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

## Ramas antiguas (ignorar)

`production`, `cursor/deploy-baseline-a92b`, `cursor/staging-next-a92b` y `main` quedan sustituidas por **`funcional`** y **`desarrollo`**.

La rama remota `develop` (con OAuth) es un experimento anterior; no usarla salvo que quieras recuperar algo concreto de ahí.
