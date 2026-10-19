"""Aislamiento: URL, esquema parametrizado y guardias. Sin RDS no se toca public."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bash(script: str, env: dict) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=merged,
        capture_output=True,
        text=True,
    )


def test_los_lanzadores_tienen_sintaxis_bash():
    for nombre in ("run_reco_backfill.sh", "run_reco_unattended.sh", "reco_guard.sh"):
        r = subprocess.run(["bash", "-n", str(ROOT / "aws" / nombre)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_env_de_ejemplo_no_parte_la_url_en_el_ampersand():
    r = _bash(
        'set -a; source aws/env.reco.example; set +a; printf %s "$DATABASE_URL"',
        {},
    )
    assert r.returncode == 0, r.stderr
    assert "options=-csearch_path%3Dreco" in r.stdout
    assert "&options=" in r.stdout


def test_sql_parametriza_el_esquema_y_aborta_si_falla():
    for nombre in ("00_schema_reco.sql", "10_snowball_candidatos.sql", "20_comprobaciones.sql"):
        texto = (ROOT / "aws" / "sql" / nombre).read_text(encoding="utf-8")
        assert "ON_ERROR_STOP" in texto
        assert ':"schema"' in texto
        assert "CREATE TABLE IF NOT EXISTS reco." not in texto
    nieve = (ROOT / "aws" / "sql" / "10_snowball_candidatos.sql").read_text(encoding="utf-8")
    assert "origen = 'semilla'" in nieve
    assert ">= 20" in nieve
    backfill = (ROOT / "aws" / "run_reco_backfill.sh").read_text(encoding="utf-8")
    assert "--channels-file" in backfill
    assert "exit 8" in backfill
    desacoplado = (ROOT / "aws" / "run_reco_unattended.sh").read_text(encoding="utf-8")
    assert "nohup setsid" in desacoplado
    assert "flock -n" in desacoplado
    assert "reco_status.json" in desacoplado


def _psql_falso(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    psql = bindir / "psql"
    psql.write_text(
        "#!/bin/sh\n"
        "for a in \"$@\"; do\n"
        "  case \"$a\" in\n"
        "    *public.messages*) printf '%s\\n' \"$FAKE_PUBLIC_COUNT\"; exit 0 ;;\n"
        "    *search_path*) printf '%s\\n' \"$FAKE_SEARCH_PATH\"; exit 0 ;;\n"
        "  esac\n"
        "done\n"
        "echo psql-inesperado >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    psql.chmod(0o755)
    return bindir


def test_guardia_acepta_el_esquema_esperado(tmp_path):
    bindir = _psql_falso(tmp_path)
    r = _bash(
        "source aws/reco_guard.sh; reco_exigir_search_path",
        {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "DATABASE_URL": "postgresql://ejemplo",
            "RECO_SCHEMA": "reco_test",
            "FAKE_SEARCH_PATH": "reco_test",
        },
    )
    assert r.returncode == 0, r.stderr
    assert "search_path=reco_test" in r.stdout


def test_guardia_aborta_si_el_search_path_es_public(tmp_path):
    bindir = _psql_falso(tmp_path)
    r = _bash(
        "source aws/reco_guard.sh; reco_exigir_search_path",
        {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "DATABASE_URL": "postgresql://ejemplo",
            "RECO_SCHEMA": "reco_test",
            "FAKE_SEARCH_PATH": "public",
        },
    )
    assert r.returncode == 9
    assert "ABORTO" in r.stdout
    assert "public" in r.stdout


def test_public_messages_distinto_aborta_y_el_igual_no(tmp_path):
    bindir = _psql_falso(tmp_path)
    base = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "DATABASE_URL": "postgresql://ejemplo",
        "FAKE_PUBLIC_COUNT": "12345",
        "FAKE_SEARCH_PATH": "reco",
    }
    ok = _bash(
        "source aws/reco_guard.sh; antes=$(reco_contar_public); reco_exigir_public_igual \"$antes\" \"$antes\"",
        base,
    )
    assert ok.returncode == 0, ok.stderr
    assert "sin cambios (12345)" in ok.stdout
    mal = _bash(
        "source aws/reco_guard.sh; reco_exigir_public_igual 10 11",
        base,
    )
    assert mal.returncode == 10
    assert "public.messages cambió (10 -> 11)" in mal.stdout


def test_config_conserva_search_path_en_la_url():
    codigo = r"""
import os, sys
sys.path.insert(0, "backend")
os.environ["DATABASE_URL"] = (
    "postgresql://u:p@h:5432/monitor_ia?sslmode=require&options=-csearch_path%3Dreco_test"
)
import config
uri = config.Config.SQLALCHEMY_DATABASE_URI
assert uri.startswith("postgresql+psycopg2://"), uri
assert "options=-csearch_path%3Dreco_test" in uri, uri
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
opciones = make_url(uri).query["options"]
assert opciones == "-csearch_path=reco_test", opciones
motor = create_engine(uri)
_args, kwargs = motor.dialect.create_connect_args(motor.url)
assert kwargs.get("options") == "-csearch_path=reco_test", kwargs
print("ok")
"""
    r = subprocess.run([sys.executable, "-c", codigo], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout


def test_guardia_python_no_escribe_si_el_esquema_no_coincide():
    sys.path.insert(0, str(ROOT / "aws"))
    import reco_filtro_db as filtro

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *_a, **_k):
            return None

        def fetchone(self):
            return ("public",)

    class Conexion:
        def cursor(self):
            return Cursor()

    with pytest.raises(SystemExit) as exc:
        filtro.exigir_search_path(Conexion(), "reco_test")
    assert "public" in str(exc.value)


def test_rds_reco_test_no_esta_en_este_entorno():
    if not os.environ.get("RECO_TEST_DATABASE_URL"):
        pytest.skip("Sin RECO_TEST_DATABASE_URL: este entorno no tiene la RDS y no se crea reco_test")
