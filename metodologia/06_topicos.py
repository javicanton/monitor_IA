#!/usr/bin/env python3
"""Prepara el corpus incluido y saca tópicos.

Solo entran mensajes del CSV filtrado con texto suficiente después de quitar
las URLs. En la EC2 el camino es NMF (scikit-learn): no instala torch.

  .venv/bin/python metodologia/06_topicos.py --corpus out/corpus_reco_B.csv --out-dir out/analisis --nmf

`--entrenar` llama a pytopicgram/BERTopic. Hace falta otra máquina: en este
disco la instalación de torch se queda sin espacio.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pandas as pd

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
MIN_CHARS = 40
STOP = frozenset(
    """a al algo alguna algunas alguno algunos ante aquel aquella aquellas aquellos
    como con contra de del desde donde durante e el ella ellas ellos en entre era
    es esa esas ese eso esos esta estas este esto estos esta estan ha han hasta
    hay la las le les lo los mas me mi mis mucho muy ni no nos o para pero porque
    por que se sin sobre su sus te tu un una unas unos y ya si ser son fue fueron
    esta estan cuando tambien aqui hay mas les les""".split()
)


def texto_nlp(texto: str) -> str:
    limpio = URL_RE.sub(" ", texto or "")
    return re.sub(r"\s+", " ", limpio).strip()


def preparar(corpus: pd.DataFrame) -> pd.DataFrame:
    df = corpus.copy()
    df["message_nlp"] = df["message"].map(lambda t: texto_nlp("" if pd.isna(t) else str(t)))
    df = df[df["message_nlp"].str.len() >= MIN_CHARS]
    cols = [c for c in ("message_pk", "channel", "date_sent", "regla", "message_nlp") if c in df.columns]
    return df[cols].reset_index(drop=True)


def _sin_tildes(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def topicos_nmf(textos: pd.Series, n: int, min_df: int = 5) -> tuple[pd.DataFrame, list[int]]:
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer

    if len(textos) < n:
        raise SystemExit(f"Hay {len(textos)} textos y se piden {n} tópicos")
    vector = TfidfVectorizer(
        preprocessor=_sin_tildes,
        stop_words=list(STOP),
        ngram_range=(1, 2),
        min_df=min_df,
        max_df=0.6,
        max_features=20000,
    )
    matriz = vector.fit_transform(textos.tolist())
    modelo = NMF(n_components=n, random_state=2026, max_iter=400, init="nndsvda")
    pesos = modelo.fit_transform(matriz)
    etiquetas = pesos.argmax(axis=1).astype(int)
    terminos = vector.get_feature_names_out()
    filas = []
    for i, componente in enumerate(modelo.components_):
        orden = componente.argsort()[::-1][:12]
        filas.append(
            {
                "topico": i,
                "mensajes": int((etiquetas == i).sum()),
                "terminos": " ".join(terminos[j] for j in orden),
            }
        )
    return pd.DataFrame(filas), etiquetas.tolist()


def entrenar(entrada: Path, out_dir: Path, num_topics: int) -> None:
    modelo = out_dir / "modelo_topicos"
    usados = out_dir / "topicos_mensajes_usados.csv"
    cmd = [
        sys.executable,
        "-m",
        "pytopicgram.extractor",
        "--file",
        str(entrada),
        "--column",
        "message_nlp",
        "--output",
        str(modelo),
        "--num_topics",
        str(num_topics),
        "--messages_used",
        str(usados),
    ]
    subprocess.run(cmd, check=True)
    from bertopic import BERTopic

    info = BERTopic.load(str(modelo)).get_topic_info()
    info.to_csv(out_dir / "topicos_info.csv", index=False)
    print(f"{len(info)} filas de tópicos -> {out_dir / 'topicos_info.csv'}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--entrenar", action="store_true")
    ap.add_argument("--nmf", action="store_true")
    ap.add_argument("--num-topics", type=int, default=20)
    args = ap.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    corpus = pd.read_csv(args.corpus, low_memory=False)
    listo = preparar(corpus)
    destino = args.out_dir / "topicos_entrada.csv"
    listo.to_csv(destino, index=False)
    print(f"mensajes_corpus={len(corpus)}")
    print(f"mensajes_para_topicos={len(listo)}")
    print(f"entrada={destino}")
    if args.entrenar and args.nmf:
        raise SystemExit("Elige uno: --entrenar (pytopicgram) o --nmf")
    if args.nmf:
        info, etiquetas = topicos_nmf(listo["message_nlp"], args.num_topics)
        info.to_csv(args.out_dir / "topicos_info.csv", index=False)
        asig = listo[["message_pk", "channel", "date_sent", "regla"]].copy()
        asig["topico"] = etiquetas
        asig.to_csv(args.out_dir / "topicos_asignacion.csv", index=False)
        print(f"{len(info)} tópicos -> {args.out_dir / 'topicos_info.csv'}")
        for _, fila in info.iterrows():
            print(f"T{int(fila['topico'])} n={int(fila['mensajes'])} {fila['terminos']}")
    elif args.entrenar:
        entrenar(destino, args.out_dir, args.num_topics)


if __name__ == "__main__":
    main()
