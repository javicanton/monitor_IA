#!/usr/bin/env python3
"""Validación del filtro: hojas de anotación, kappa, precisión y exhaustividad.

  python3 metodologia/04_validacion.py muestra --in corpus_bruto.csv --n 400 --seed 2026 --out-dir validacion/
  python3 metodologia/04_validacion.py evaluar --dir validacion/

La muestra sale del corpus bruto (incluidos y excluidos), para poder medir exhaustividad.
Cada codificador rellena 'relevante' (1 = trata de Agenda 2030/ODS/clima institucional o de su impugnación, 0 = no).
El gold de las métricas es el acuerdo: si discrepan, la fila queda fuera hasta el consenso.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

COLUMNAS_FILTRO = ["regla", "incluido", "hits_A", "hits_B", "hits_veto"]


def kappa(a, b) -> float:
    if len(a) != len(b):
        raise ValueError("las dos series de anotación tienen distinta longitud")
    n = len(a)
    if n == 0:
        raise ValueError("no hay pares para kappa")
    po = sum(x == y for x, y in zip(a, b)) / n
    categorias = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in categorias)
    if pe >= 1:
        return 1.0
    return (po - pe) / (1 - pe)


def metricas(incluido, gold):
    """Precisión y exhaustividad sobre las filas con gold ya consensuado (sin None)."""
    tp = fp = fn = 0
    for marca, oro in zip(incluido, gold):
        if oro is None or (isinstance(oro, float) and pd.isna(oro)):
            continue
        marca_i = int(marca)
        oro_i = int(oro)
        if marca_i == 1 and oro_i == 1:
            tp += 1
        elif marca_i == 1 and oro_i == 0:
            fp += 1
        elif marca_i == 0 and oro_i == 1:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else None
    exhaustividad = tp / (tp + fn) if (tp + fn) else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "exhaustividad": exhaustividad}


def _fmt(valor):
    return "n/d" if valor is None else round(valor, 3)


def leer_hoja(path: Path) -> pd.DataFrame:
    """Lee una hoja aunque Excel la haya guardado con punto y coma."""
    return pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")


def muestra(args) -> None:
    df = pd.read_csv(args.inp)
    if df.empty:
        raise SystemExit("el corpus de entrada está vacío")
    if args.n > len(df):
        raise SystemExit(f"la muestra pedida ({args.n}) es mayor que el corpus ({len(df)})")
    s = df.sample(n=args.n, random_state=args.seed).reset_index(drop=True)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = s.copy()
    base.insert(0, "id_val", range(1, len(s) + 1))
    base.to_csv(out / "muestra_maestra.csv", index=False)
    ocultas = {c.lower() for c in COLUMNAS_FILTRO}
    ciego = base.drop(columns=[c for c in base.columns if c.lower() in ocultas])
    ciego["relevante"] = ""
    ciego.to_csv(out / "codificador_1.csv", index=False)
    ciego.to_csv(out / "codificador_2.csv", index=False)
    print("Hojas generadas en", out)


def evaluar(args) -> None:
    d = Path(args.dir)
    m = leer_hoja(d / "muestra_maestra.csv")
    c1 = leer_hoja(d / "codificador_1.csv")
    c2 = leer_hoja(d / "codificador_2.csv")
    if not (len(m) == len(c1) == len(c2)):
        raise SystemExit("las tres hojas no tienen el mismo número de filas")
    try:
        x = c1["relevante"].astype(int).tolist()
        y = c2["relevante"].astype(int).tolist()
    except (TypeError, ValueError) as exc:
        raise SystemExit("hay celdas 'relevante' vacías o no numéricas") from exc
    k = kappa(x, y)
    acuerdo = sum(i == j for i, j in zip(x, y)) / len(x)
    print("Cohen kappa:", round(k, 3), "| acuerdo bruto:", round(acuerdo, 3))
    m["gold"] = [1 if (i + j) == 2 else 0 if (i + j) == 0 else None for i, j in zip(x, y)]
    print("Desacuerdos a resolver por consenso:", int(m["gold"].isna().sum()))
    g = m.dropna(subset=["gold"])
    res = metricas(g["incluido"].tolist(), g["gold"].tolist())
    print("Precisión:", _fmt(res["precision"]), "| Exhaustividad:", _fmt(res["exhaustividad"]))
    if "regla" in g.columns and not g.empty:
        tabla = g.groupby("regla")["gold"].agg(["count", "mean"])
        tabla = tabla.rename(columns={"mean": "proporcion_relevante"})
        print(tabla.to_string())


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("muestra")
    m.add_argument("--in", dest="inp", required=True)
    m.add_argument("--n", type=int, default=400)
    m.add_argument("--seed", type=int, default=2026)
    m.add_argument("--out-dir", required=True)
    e = sp.add_parser("evaluar")
    e.add_argument("--dir", required=True)
    args = ap.parse_args(argv)
    (muestra if args.cmd == "muestra" else evaluar)(args)


if __name__ == "__main__":
    main()
