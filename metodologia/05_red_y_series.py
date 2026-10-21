#!/usr/bin/env python3
"""Red de reenvíos entre los canales del corpus y series mensuales.

La red solo une canales de la semilla (incluir distinto de 0). Un reenvío
hacia un canal que no está en el corpus no entra en el grafo.

Uso, en la EC2:
  .venv/bin/python metodologia/05_red_y_series.py \
    --corpus out/corpus_reco_B.csv \
    --aristas out/aristas_B.csv \
    --semilla metodologia/01_canales_semilla.csv \
    --out-dir out/analisis
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

INICIO = "2024-09-01"
FIN = "2026-01-01"


def norm_handle(valor: str) -> str:
    h = (valor or "").strip().lstrip("@").lower()
    h = re.sub(r"^https?://(t\.me|telegram\.me)/(s/)?", "", h, flags=re.I)
    return h.split("/")[0].split("?")[0].strip()


def _esta_excluido(valor) -> bool:
    return str(valor or "").strip().lower() in {"0", "0.0"}


def canales_corpus(semilla: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for _, r in semilla.iterrows():
        if _esta_excluido(r.get("incluir")):
            continue
        handle = norm_handle(str(r.get("handle_telegram") or ""))
        if not handle or handle == "nan":
            continue
        filas.append(
            {
                "username": handle,
                "nombre": str(r.get("nombre_documentado") or handle),
                "tipo": str(r.get("tipo_provisional") or "").replace("nan", ""),
                "pais": str(r.get("pais_provisional") or "").replace("nan", ""),
                "origen": str(r.get("origen") or "semilla").replace("nan", "") or "semilla",
            }
        )
    if not filas:
        return pd.DataFrame(columns=["username", "nombre", "tipo", "pais", "origen"])
    return pd.DataFrame(filas).drop_duplicates("username")


def serie_mensual(corpus: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = corpus.copy()
    df["fecha"] = pd.to_datetime(df["date_sent"], utc=True, errors="coerce")
    df = df[df["fecha"].notna()]
    df = df[(df["fecha"] >= INICIO) & (df["fecha"] < FIN)]
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    por_mes = (
        df.groupby("mes", as_index=False)
        .agg(mensajes=("message_pk", "size"), canales=("channel", "nunique"))
    )
    por_regla = (
        df.groupby(["mes", "regla"], as_index=False)
        .size()
        .rename(columns={"size": "mensajes"})
    )
    return por_mes, por_regla


def aristas_internas(aristas: pd.DataFrame, usernames: set[str]) -> pd.DataFrame:
    df = aristas.copy()
    df["origen"] = df["origen"].map(lambda v: norm_handle(str(v)))
    df["destino"] = df["destino"].map(lambda v: norm_handle(str(v)))
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce").fillna(0).astype(int)
    df = df[(df["peso"] > 0) & (df["origen"] != df["destino"])]
    dentro = df["origen"].isin(usernames) & df["destino"].isin(usernames)
    internas = (
        df.loc[dentro]
        .groupby(["origen", "destino"], as_index=False)["peso"]
        .sum()
    )
    return internas


def metricas_nodos(nodos: pd.DataFrame, aristas: pd.DataFrame) -> pd.DataFrame:
    base = nodos.copy()
    if aristas.empty:
        for col in ("grado_entrada", "grado_salida", "peso_entrada", "peso_salida"):
            base[col] = 0
        return base
    entrada = aristas.groupby("destino").agg(
        grado_entrada=("origen", "nunique"), peso_entrada=("peso", "sum")
    )
    salida = aristas.groupby("origen").agg(
        grado_salida=("destino", "nunique"), peso_salida=("peso", "sum")
    )
    base = base.merge(entrada, left_on="username", right_index=True, how="left")
    base = base.merge(salida, left_on="username", right_index=True, how="left")
    for col in ("grado_entrada", "grado_salida", "peso_entrada", "peso_salida"):
        base[col] = base[col].fillna(0).astype(int)
    return base


def comunidades(aristas: pd.DataFrame) -> dict[str, int]:
    if aristas.empty:
        return {}
    import networkx as nx
    from networkx.algorithms.community import greedy_modularity_communities

    g = nx.Graph()
    for _, r in aristas.iterrows():
        a, b, w = r["origen"], r["destino"], int(r["peso"])
        if g.has_edge(a, b):
            g[a][b]["weight"] += w
        else:
            g.add_edge(a, b, weight=w)
    grupos = greedy_modularity_communities(g, weight="weight")
    mapa = {}
    for i, grupo in enumerate(grupos):
        for nodo in grupo:
            mapa[nodo] = i
    return mapa


def analizar(corpus: pd.DataFrame, aristas: pd.DataFrame, semilla: pd.DataFrame, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    por_mes, por_regla = serie_mensual(corpus)
    nodos = canales_corpus(semilla)
    usernames = set(nodos["username"])
    internas = aristas_internas(aristas, usernames)
    bruto = aristas.copy()
    bruto["origen"] = bruto["origen"].map(lambda v: norm_handle(str(v)))
    bruto["destino"] = bruto["destino"].map(lambda v: norm_handle(str(v)))
    dentro = bruto["origen"].isin(usernames) & bruto["destino"].isin(usernames)
    fuera = int((~dentro).sum())
    metricas = metricas_nodos(nodos, internas)
    mapa = comunidades(internas)
    metricas["comunidad"] = metricas["username"].map(lambda u: mapa.get(u, -1)).astype(int)
    por_mes.to_csv(out_dir / "series_mes.csv", index=False)
    por_regla.to_csv(out_dir / "series_mes_regla.csv", index=False)
    metricas.sort_values(["peso_entrada", "peso_salida"], ascending=False).to_csv(
        out_dir / "red_nodos.csv", index=False
    )
    internas.sort_values("peso", ascending=False).to_csv(out_dir / "red_aristas.csv", index=False)
    n_com = metricas.loc[metricas["comunidad"] >= 0, "comunidad"].nunique()
    aislados = int((metricas["comunidad"] < 0).sum())
    texto = "\n".join(
        [
            f"mensajes_incluidos={len(corpus)}",
            f"meses={len(por_mes)}",
            f"canales_corpus={len(nodos)}",
            f"aristas_internas={len(internas)}",
            f"aristas_fuera_del_corpus={fuera}",
            f"comunidades={n_com}",
            f"canales_sin_arista_interna={aislados}",
            "",
        ]
    )
    (out_dir / "red_resumen.txt").write_text(texto, encoding="utf-8")
    return texto


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--aristas", type=Path, required=True)
    ap.add_argument("--semilla", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    corpus = pd.read_csv(args.corpus, low_memory=False)
    aristas = pd.read_csv(args.aristas)
    semilla = pd.read_csv(args.semilla)
    print(analizar(corpus, aristas, semilla, args.out_dir), end="")
    print(f"Salidas en {args.out_dir}")


if __name__ == "__main__":
    main()
