"""Kappa, precisión y exhaustividad con cifras hechas a mano."""
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


VAL = _cargar("validacion_reco", ROOT / "metodologia" / "04_validacion.py")


def test_kappa_caso_manual():
    # a: tres 1 y dos 0. b: dos 1 y tres 0. Coinciden 4 de 5.
    # po = 4/5. pe = (3/5)*(2/5) + (2/5)*(3/5) = 12/25.
    # kappa = (4/5 - 12/25) / (1 - 12/25) = (8/25) / (13/25) = 8/13.
    a = [1, 1, 1, 0, 0]
    b = [1, 1, 0, 0, 0]
    assert VAL.kappa(a, b) == pytest.approx(8 / 13)


def test_kappa_acuerdo_perfecto_y_desacuerdo_total():
    assert VAL.kappa([1, 0, 1], [1, 0, 1]) == pytest.approx(1.0)
    assert VAL.kappa([1, 1, 0, 0], [0, 0, 1, 1]) == pytest.approx(-1.0)


def test_kappa_un_anotador_constante_da_cero():
    # po = pe = 0.75, kappa = 0.
    assert VAL.kappa([1, 1, 1, 1], [1, 1, 1, 0]) == pytest.approx(0.0)


def test_kappa_rechaza_listas_vacias_o_desiguales():
    with pytest.raises(ValueError):
        VAL.kappa([], [])
    with pytest.raises(ValueError):
        VAL.kappa([1], [1, 0])


def test_precision_y_exhaustividad_a_mano():
    # incluido: 1,1,1,0,0,0
    # gold:     1,1,0,0,1,0
    # tp=2, fp=1, fn=1 -> precisión 2/3, exhaustividad 2/3
    res = VAL.metricas([1, 1, 1, 0, 0, 0], [1, 1, 0, 0, 1, 0])
    assert res["tp"] == 2 and res["fp"] == 1 and res["fn"] == 1
    assert res["precision"] == pytest.approx(2 / 3)
    assert res["exhaustividad"] == pytest.approx(2 / 3)


def test_el_desacuerdo_no_entra_en_las_metricas():
    res = VAL.metricas([1, 0], [1, None])
    assert res["tp"] == 1 and res["fn"] == 0 and res["fp"] == 0
    assert res["precision"] == pytest.approx(1.0)
    assert res["exhaustividad"] == pytest.approx(1.0)


def test_sin_positivos_la_precision_queda_indefinida():
    res = VAL.metricas([0, 0], [0, 0])
    assert res["precision"] is None
    assert res["exhaustividad"] is None


def test_muestra_ciega_y_reproducible(tmp_path):
    bruto = tmp_path / "bruto.csv"
    with bruto.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["message", "regla", "incluido", "hits_a"])
        w.writeheader()
        for i in range(6):
            w.writerow({"message": f"texto {i}", "regla": "R2" if i < 3 else "NONE", "incluido": int(i < 3), "hits_a": "ods"})
    out = tmp_path / "val"
    args_m = type("A", (), {"inp": str(bruto), "n": 4, "seed": 2026, "out_dir": str(out)})()
    VAL.muestra(args_m)
    maestro = list(csv.DictReader((out / "muestra_maestra.csv").open(encoding="utf-8")))
    c1 = list(csv.DictReader((out / "codificador_1.csv").open(encoding="utf-8")))
    c2 = (out / "codificador_2.csv").read_text(encoding="utf-8")
    assert len(maestro) == 4
    assert "regla" in maestro[0] and "regla" not in c1[0]
    assert "hits_a" in maestro[0] and "hits_a" not in c1[0]
    assert c1[0]["relevante"] == ""
    assert (out / "codificador_1.csv").read_text(encoding="utf-8") == c2
    with pytest.raises(SystemExit):
        VAL.muestra(type("A", (), {"inp": str(bruto), "n": 99, "seed": 1, "out_dir": str(out)})())
