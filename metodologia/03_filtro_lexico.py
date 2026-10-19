#!/usr/bin/env python3
"""Filtro léxico de dos capas con reglas R1-R4.
Uso: python 03_filtro_lexico.py --in mensajes.csv --out filtrado.csv [--text-col message] [--test]
Entrada: CSV o JSON/JSONL con una columna de texto. Ajustar --text-col al esquema real del crawler.
Salida: todas las filas con columnas nuevas: regla (R1/R2/R3/R4/NONE), incluido (1/0), hits_A, hits_B, hits_veto.
R3 (solo B) sale con incluido=1 y regla=R3: la condición 'ventana de acontecimiento o canal denso' se aplica después, en el análisis.
"""
import argparse, re, sys, unicodedata, yaml
from pathlib import Path
import pandas as pd

def normalizar(t):
    t = str(t).lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("@", "a").replace("2o3o", "2030").replace("20 30", "2030")
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)          # caracteres repetidos
    t = re.sub(r"#(\w+)", r" \1 ", t)              # hashtags -> palabra
    t = re.sub(r"[_\-]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def compilar(cfg):
    comp = lambda lst: [re.compile(p) for p in lst]
    A = {k: comp(v) for k, v in cfg["capa_A"].items()}
    B = {k: comp(v) for k, v in cfg["capa_B"].items()}
    return A, B, comp(cfg["veto"])

def hits(grupos, t):
    out = []
    for fam, pats in grupos.items():
        if any(p.search(t) for p in pats):
            out.append(fam)
    return out

def clasificar(texto, A, B, V):
    t = normalizar(texto)
    a, b = hits(A, t), hits(B, t)
    v = [p.pattern for p in V if p.search(t)]
    # 2030 suelto cuenta como ancla de capa A solo si no hay veto
    if not a and re.search(r"\b2030\b", t) and not v:
        a = ["2030_suelto"]
    if v and not b: regla = "R4"
    elif a and b:  regla = "R1"
    elif a:        regla = "R2"
    elif b:        regla = "R3"
    else:          regla = "NONE"
    return regla, int(regla in ("R1", "R2", "R3")), a, b, v

def self_test(A, B, V):
    casos = [
        ("El Gran Reseteo y la Agenda 2030 quieren que no tengas nada", "R1"),
        ("La #Agend@2030 avanza en el pleno", "R2"),
        ("Es una estafa climática, el CO2 es vida", "R3"),
        ("España presenta su candidatura al Mundial 2030", "R4"),
        ("Hoy hace sol en Granada", "NONE"),
        ("Visión 2030 de Arabia Saudí", "R4"),
        ("Mundial 2030 pagado por el Nuevo Orden Mundial", "R3"),
    ]
    ok = True
    for txt, esperado in casos:
        r = clasificar(txt, A, B, V)[0]
        print(("OK  " if r == esperado else "FALLA"), esperado, r, "|", txt)
        ok &= (r == esperado)
    return ok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp"); ap.add_argument("--out")
    ap.add_argument("--text-col", default="message")
    ap.add_argument("--lexico", default=str(Path(__file__).with_name("02_lexico.yaml")))
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.lexico, encoding="utf-8"))
    A, B, V = compilar(cfg)
    if a.test:
        sys.exit(0 if self_test(A, B, V) else 1)
    p = Path(a.inp)
    df = pd.read_csv(p) if p.suffix == ".csv" else pd.read_json(p, lines=p.suffix == ".jsonl")
    res = df[a.text_col].fillna("").map(lambda x: clasificar(x, A, B, V))
    df["regla"] = res.map(lambda r: r[0]); df["incluido"] = res.map(lambda r: r[1])
    df["hits_A"] = res.map(lambda r: "|".join(r[2])); df["hits_B"] = res.map(lambda r: "|".join(r[3]))
    df["hits_veto"] = res.map(lambda r: "|".join(r[4]))
    df.to_csv(a.out, index=False)
    print(df["regla"].value_counts().to_string())

if __name__ == "__main__":
    main()
