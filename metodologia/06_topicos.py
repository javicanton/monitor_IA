#!/usr/bin/env python3
"""Prepara el corpus incluido y entrena tópicos con pytopicgram.

Solo entran mensajes con incluido implícito (el CSV ya es el corpus filtrado)
y con texto suficiente después de quitar las URLs.

Uso, en la EC2:
  .venv/bin/python metodologia/06_topicos.py --corpus out/corpus_reco_B.csv --out-dir out/analisis
  .venv/bin/python metodologia/06_topicos.py --corpus out/corpus_reco_B.csv --out-dir out/analisis --entrenar
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
MIN_CHARS = 40


def texto_nlp(texto: str) -> str:
    limpio = URL_RE.sub(" ", texto or "")
    return re.sub(r"\s+", " ", limpio).strip()


def preparar(corpus: pd.DataFrame) -> pd.DataFrame:
    df = corpus.copy()
    df["message_nlp"] = df["message"].map(lambda t: texto_nlp("" if pd.isna(t) else str(t)))
    df = df[df["message_nlp"].str.len() >= MIN_CHARS]
    cols = [c for c in ("message_pk", "channel", "date_sent", "regla", "message_nlp") if c in df.columns]
    return df[cols].reset_index(drop=True)


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
    if args.entrenar:
        entrenar(destino, args.out_dir, args.num_topics)


if __name__ == "__main__":
    main()
