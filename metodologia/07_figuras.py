#!/usr/bin/env python3
"""Figuras de la serie mensual, la red interna y los tópicos.

Lee los CSV de out/analisis. No vuelve a entrenar nada.

En la EC2:
  .venv/bin/python -m pip install matplotlib
  .venv/bin/python metodologia/07_figuras.py --analisis out/analisis --out-dir out/analisis/figuras
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codigo_topicos import APARTADOS, BLOQUES, ETIQUETAS

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

MESES = [f"{anio}-{mes:02d}" for anio, mes in (
    [(2024, m) for m in range(9, 13)] + [(2025, m) for m in range(1, 13)]
)]
REGLAS = ("R1", "R2", "R3", "R4")
MAX_ARISTAS = 250
MAX_ETIQUETAS = 12
COLORES = ("#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#882255")
COLOR_REGLA = {"R1": "#4477AA", "R2": "#228833", "R3": "#CCBB44", "R4": "#EE6677"}


def serie_completa(por_mes: pd.DataFrame) -> pd.DataFrame:
    base = pd.DataFrame({"mes": MESES})
    df = por_mes.copy()
    df["mes"] = df["mes"].astype(str).str.slice(0, 7)
    out = base.merge(df, on="mes", how="left")
    for col in ("mensajes", "canales"):
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    return out


def reglas_completas(por_regla: pd.DataFrame) -> pd.DataFrame:
    df = por_regla.copy()
    df["mes"] = df["mes"].astype(str).str.slice(0, 7)
    df["mensajes"] = pd.to_numeric(df["mensajes"], errors="coerce").fillna(0).astype(int)
    ancho = df.pivot_table(index="mes", columns="regla", values="mensajes", aggfunc="sum", fill_value=0)
    columnas = [r for r in REGLAS if r in ancho.columns]
    columnas += [c for c in ancho.columns if c not in columnas]
    ancho = ancho.reindex(MESES, fill_value=0)
    if not columnas:
        ancho["R2"] = 0
        columnas = ["R2"]
    return ancho[columnas].astype(int)


def aristas_visibles(aristas: pd.DataFrame, max_aristas: int = MAX_ARISTAS) -> pd.DataFrame:
    df = aristas.copy()
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce").fillna(0).astype(int)
    df = df[df["peso"] > 0].sort_values("peso", ascending=False)
    return df.head(max_aristas).reset_index(drop=True)


def conteos_topico(asignacion: pd.DataFrame) -> pd.Series:
    temas = pd.to_numeric(asignacion["topico"], errors="coerce").dropna().astype(int)
    return temas.value_counts().reindex(range(20), fill_value=0).astype(int)


def tabla_bloques(conteos: pd.Series) -> pd.DataFrame:
    total = int(conteos.sum())
    filas = []
    for nombre, miembros in BLOQUES:
        textos = int(sum(int(conteos.get(i, 0)) for i in miembros))
        filas.append({"bloque": nombre, "textos": textos, "pct": (100 * textos / total) if total else 0})
    return pd.DataFrame(filas)


def tabla_apartados(conteos: pd.Series) -> pd.DataFrame:
    total = int(conteos.sum())
    filas = []
    for tema, nombre in APARTADOS.items():
        textos = int(conteos.get(tema, 0))
        filas.append({"apartado": nombre, "topico": tema, "textos": textos, "pct": (100 * textos / total) if total else 0})
    return pd.DataFrame(filas)


def _estilo():
    plt.rcParams.update({
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def _guardar(fig, ruta: Path) -> None:
    fig.savefig(ruta, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(ruta.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def figura_serie(por_mes: pd.DataFrame, ruta: Path) -> None:
    df = serie_completa(por_mes)
    _estilo()
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.bar(df["mes"], df["mensajes"], color="#4477AA", width=0.72)
    ax.set_ylabel("Mensajes incluidos")
    ax.set_xlabel("")
    ax2 = ax.twinx()
    ax2.plot(df["mes"], df["canales"], color="#882255", marker="o", linewidth=1.6)
    ax2.set_ylabel("Canales con algún mensaje")
    ax2.spines["top"].set_visible(False)
    ax.tick_params(axis="x", rotation=55)
    fig.tight_layout()
    _guardar(fig, ruta)


def figura_reglas(por_regla: pd.DataFrame, ruta: Path) -> None:
    ancho = reglas_completas(por_regla)
    _estilo()
    fig, ax = plt.subplots(figsize=(11, 4.6))
    fondo = pd.Series(0, index=ancho.index)
    for regla in ancho.columns:
        color = COLOR_REGLA.get(str(regla), "#999999")
        ax.bar(ancho.index, ancho[regla], bottom=fondo, color=color, width=0.72, label=str(regla))
        fondo = fondo + ancho[regla]
    ax.set_ylabel("Mensajes incluidos")
    ax.legend(frameon=False, ncol=len(ancho.columns))
    ax.tick_params(axis="x", rotation=55)
    fig.tight_layout()
    _guardar(fig, ruta)


def _fila_nodo(info: pd.DataFrame, nodo: str):
    if nodo not in info.index:
        return None
    fila = info.loc[nodo]
    if isinstance(fila, pd.DataFrame):
        return fila.iloc[0]
    return fila


def _nombre_nodo(info: pd.DataFrame, nodo: str) -> str:
    fila = _fila_nodo(info, nodo)
    if fila is None:
        return nodo
    nombre = str(fila.get("nombre") or nodo)
    if nombre in {"", "nan"}:
        nombre = nodo
    return nombre[:32]


def figura_red(nodos: pd.DataFrame, aristas: pd.DataFrame, ruta: Path) -> tuple[int, int]:
    visibles = aristas_visibles(aristas)
    g = nx.Graph()
    for _, r in visibles.iterrows():
        a, b, w = str(r["origen"]), str(r["destino"]), int(r["peso"])
        if a == b:
            continue
        if g.has_edge(a, b):
            g[a][b]["weight"] += w
        else:
            g.add_edge(a, b, weight=w)
    _estilo()
    fig, ax = plt.subplots(figsize=(11, 11))
    if g.number_of_edges() == 0:
        ax.set_axis_off()
        _guardar(fig, ruta)
        return 0, 0
    separacion = 2.4 / (g.number_of_nodes() ** 0.5)
    pos = nx.spring_layout(g, seed=2026, k=separacion, iterations=120)
    info = nodos.copy()
    info["username"] = info["username"].astype(str)
    info = info.drop_duplicates("username").set_index("username")
    fuerza = {}
    colores = []
    for nodo in g.nodes:
        fila = _fila_nodo(info, nodo)
        if fila is None:
            fuerza[nodo] = 1
            comunidad = -1
        else:
            fuerza[nodo] = int(fila.get("peso_entrada", 0)) + int(fila.get("peso_salida", 0))
            comunidad = int(fila.get("comunidad", -1))
        colores.append("#BBBBBB" if comunidad < 0 else COLORES[comunidad % len(COLORES)])
    max_f = max(fuerza.values()) or 1
    max_w = max(d["weight"] for _, _, d in g.edges(data=True)) or 1
    tamaños = [60 + 1100 * (fuerza[n] / max_f) ** 0.5 for n in g.nodes]
    anchos = [0.4 + 2.4 * (d["weight"] / max_w) for _, _, d in g.edges(data=True)]
    nx.draw_networkx_edges(g, pos, ax=ax, width=anchos, edge_color="#C8C8C8", alpha=0.95)
    nx.draw_networkx_nodes(g, pos, ax=ax, node_size=tamaños, node_color=colores, linewidths=0)
    orden = sorted(g.nodes, key=lambda n: fuerza[n], reverse=True)
    etiquetas = {nodo: _nombre_nodo(info, nodo) for nodo in orden[:MAX_ETIQUETAS]}
    nx.draw_networkx_labels(
        g, pos, labels=etiquetas, ax=ax, font_size=8,
        bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none", "alpha": 0.85},
    )
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    dx = (max(xs) - min(xs)) * 0.18 or 0.2
    dy = (max(ys) - min(ys)) * 0.18 or 0.2
    ax.set_xlim(min(xs) - dx, max(xs) + dx)
    ax.set_ylim(min(ys) - dy, max(ys) + dy)
    ax.set_axis_off()
    fig.tight_layout()
    _guardar(fig, ruta)
    return g.number_of_nodes(), g.number_of_edges()


def canales_visibles(nodos: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    df = nodos.copy()
    df["peso_entrada"] = pd.to_numeric(df["peso_entrada"], errors="coerce").fillna(0).astype(int)
    df["peso_salida"] = pd.to_numeric(df.get("peso_salida", 0), errors="coerce").fillna(0).astype(int)
    return df.sort_values(["peso_entrada", "peso_salida"], ascending=False).head(n)


def figura_canales(nodos: pd.DataFrame, ruta: Path) -> None:
    tabla = canales_visibles(nodos).sort_values("peso_entrada", ascending=True)
    info_nombre = tabla["nombre"].astype(str) if "nombre" in tabla.columns else tabla["username"].astype(str)
    etiquetas = [
        usuario if nombre in {"", "nan"} else nombre[:32]
        for nombre, usuario in zip(info_nombre, tabla["username"].astype(str))
    ]
    _estilo()
    fig, ax = plt.subplots(figsize=(10, 6.2))
    ax.barh(etiquetas, tabla["peso_entrada"], color="#4477AA")
    ax.set_xlabel("Reenvíos recibidos desde canales del corpus")
    fig.tight_layout()
    _guardar(fig, ruta)


def figura_bloques(conteos: pd.Series, ruta: Path) -> None:
    tabla = tabla_bloques(conteos).sort_values("textos", ascending=True)
    _estilo()
    fig, ax = plt.subplots(figsize=(10, 5.2))
    colores = []
    nombres = [nombre for nombre, _ in BLOQUES]
    for bloque in tabla["bloque"]:
        colores.append(COLORES[nombres.index(bloque) % len(COLORES)])
    ax.barh(tabla["bloque"], tabla["textos"], color=colores)
    ax.set_xlim(0, float(tabla["textos"].max()) * 1.18)
    ax.set_xlabel("Textos")
    for i, (_, fila) in enumerate(tabla.iterrows()):
        ax.text(fila["textos"], i, f"  {fila['pct']:.1f} %".replace(".", ","), va="center", fontsize=10)
    fig.tight_layout()
    _guardar(fig, ruta)


def figura_detalle(conteos: pd.Series, ruta: Path) -> None:
    filas = []
    for tema, etiqueta in ETIQUETAS.items():
        bloque = next(nombre for nombre, miembros in BLOQUES if tema in miembros)
        filas.append({"etiqueta": etiqueta, "textos": int(conteos.get(tema, 0)), "bloque": bloque})
    tabla = pd.DataFrame(filas).sort_values("textos", ascending=True)
    nombres = [nombre for nombre, _ in BLOQUES]
    colores = [COLORES[nombres.index(b) % len(COLORES)] for b in tabla["bloque"]]
    _estilo()
    fig, ax = plt.subplots(figsize=(10, 7.2))
    ax.barh(tabla["etiqueta"], tabla["textos"], color=colores)
    ax.set_xlabel("Textos")
    fig.tight_layout()
    _guardar(fig, ruta)


def notas(conteos: pd.Series, nodos_red: int, aristas_red: int, canales: int | None) -> str:
    total = int(conteos.sum())
    bloques = tabla_bloques(conteos)
    apartados = tabla_apartados(conteos)
    lineas = [
        f"textos_topicos={total}",
        f"en_bloques={int(bloques['textos'].sum())}",
        f"apartados={int(apartados['textos'].sum())}",
        f"red_nodos_dibujados={nodos_red}",
        f"red_aristas_dibujadas={aristas_red}",
        f"red_aristas_max={MAX_ARISTAS}",
    ]
    if canales is not None:
        lineas.append(f"canales_corpus={canales}")
    lineas.append("")
    for _, fila in bloques.sort_values("textos", ascending=False).iterrows():
        lineas.append(f"bloque\t{fila['bloque']}\t{int(fila['textos'])}\t{fila['pct']:.1f}")
    for _, fila in apartados.iterrows():
        lineas.append(f"apartado\t{fila['apartado']}\t{int(fila['textos'])}\t{fila['pct']:.1f}")
    lineas.extend([
        "",
        "Pies:",
        "Serie mensual: mensajes del corpus incluido, de septiembre de 2024 a diciembre de 2025. La línea cuenta los canales con al menos un mensaje ese mes.",
        "Serie por regla: los mismos mensajes, partidos por la regla del léxico v0.1 que los marcó.",
        "Red: las 250 aristas internas de mayor peso. El color es la comunidad. El tamaño suma los reenvíos internos. La etiqueta marca los 12 canales con más reenvíos.",
        "Canales: los 15 que más reenvíos reciben desde otros canales del corpus.",
        "Tópicos: bloques de la segunda pasada NMF. El porcentaje es sobre los textos usados en el modelo. El resto, el índice, el lema y el pie de canal no entran en las barras.",
        "",
    ])
    return "\n".join(lineas)


def _canales_corpus(analisis: Path) -> int | None:
    ruta = analisis / "red_resumen.txt"
    if not ruta.is_file():
        return None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("canales_corpus="):
            return int(linea.split("=", 1)[1])
    return None


def generar(analisis: Path, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    por_mes = pd.read_csv(analisis / "series_mes.csv")
    figura_serie(por_mes, out_dir / "serie_mensual.png")
    figura_reglas(pd.read_csv(analisis / "series_mes_regla.csv"), out_dir / "serie_regla.png")
    nodos = pd.read_csv(analisis / "red_nodos.csv")
    aristas = pd.read_csv(analisis / "red_aristas.csv")
    n_nodos, n_aristas = figura_red(nodos, aristas, out_dir / "red_reenvios.png")
    figura_canales(nodos, out_dir / "red_canales.png")
    conteos = conteos_topico(pd.read_csv(analisis / "topicos_asignacion.csv"))
    figura_bloques(conteos, out_dir / "topicos_bloques.png")
    figura_detalle(conteos, out_dir / "topicos_detalle.png")
    texto = notas(conteos, n_nodos, n_aristas, _canales_corpus(analisis))
    (out_dir / "figuras_notas.txt").write_text(texto, encoding="utf-8")
    return texto


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analisis", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    print(generar(args.analisis, args.out_dir), end="")
    print(f"Figuras en {args.out_dir}")


if __name__ == "__main__":
    main()
