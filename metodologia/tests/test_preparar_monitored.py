"""La semilla solo entra si hay handle, y el SQL no queda fijo en el esquema reco."""
import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PREP = _cargar("preparar_reco", ROOT / "aws" / "preparar_monitored.py")


def _semilla(path: Path, filas):
    campos = [
        "handle_telegram",
        "nombre_documentado",
        "tipo_provisional",
        "pais_provisional",
        "fuente_documental",
        "incluir",
        "origen",
        "ronda_snowball",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for fila in filas:
            w.writerow(fila)


def test_filtra_handles_y_parametriza_el_esquema(tmp_path):
    src = tmp_path / "semilla.csv"
    _semilla(
        src,
        [
            {
                "handle_telegram": "https://t.me/CanalUno",
                "nombre_documentado": "Canal Uno",
                "tipo_provisional": "T1",
                "pais_provisional": "ES",
                "fuente_documental": "anexo",
                "incluir": "",
                "origen": "",
                "ronda_snowball": "",
            },
            {
                "handle_telegram": "@Caido",
                "nombre_documentado": "Caído",
                "tipo_provisional": "T2",
                "pais_provisional": "ES",
                "fuente_documental": "anexo",
                "incluir": "0",
                "origen": "semilla",
                "ronda_snowball": "0",
            },
            {
                "handle_telegram": "",
                "nombre_documentado": "Sin handle",
                "tipo_provisional": "T3",
                "pais_provisional": "MX",
                "fuente_documental": "anexo",
                "incluir": "1",
                "origen": "semilla",
                "ronda_snowball": "0",
            },
            {
                "handle_telegram": "BolaNieve",
                "nombre_documentado": "O'Higgins",
                "tipo_provisional": "T4",
                "pais_provisional": "CL",
                "fuente_documental": "snowball",
                "incluir": "1",
                "origen": "snowball",
                "ronda_snowball": "1",
            },
        ],
    )
    out = tmp_path / "aws"
    n = PREP.escribir(src, out, "reco_test")
    assert n == 2
    lista = (out / "reco_monitored.csv").read_text(encoding="utf-8").strip().splitlines()
    assert lista[0].startswith("canaluno,")
    assert "caido" not in (out / "reco_monitored.csv").read_text(encoding="utf-8")
    sql = (out / "reco_canales_insert.sql").read_text(encoding="utf-8")
    assert 'SET search_path TO "reco_test"' in sql
    assert "O''Higgins" in sql
    assert "snowball" in sql
    assert "INSERT INTO reco.reco_canales" not in sql


def test_sin_handles_no_escribe_un_insert_roto(tmp_path):
    src = tmp_path / "vacia.csv"
    _semilla(src, [])
    n = PREP.escribir(src, tmp_path / "out", "reco")
    assert n == 0
    sql = (tmp_path / "out" / "reco_canales_insert.sql").read_text(encoding="utf-8")
    assert "INSERT INTO" not in sql


def test_esquema_raro_se_rechaza(tmp_path):
    src = tmp_path / "semilla.csv"
    _semilla(src, [])
    with pytest.raises(SystemExit):
        PREP.escribir(src, tmp_path / "out", "reco;drop")
