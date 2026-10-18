#!/usr/bin/env python3
"""Aplica el filtro léxico a messages del esquema RECO y guarda reco_flags.

No modifica messages. Antes de escribir comprueba search_path y, al terminar,
que public.messages no haya cambiado de conteo.

El léxico y 03_filtro_lexico.py se leen del mismo directorio (--lexico).
Uso:
  python3 aws/reco_filtro_db.py --lexico metodologia/02_lexico.yaml --version v0.1
  python3 aws/reco_filtro_db.py --export out/corpus_reco.csv --solo-incluidos
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def cargar_filtro(lexico: Path):
    ruta = lexico.resolve().parent / "03_filtro_lexico.py"
    if not ruta.is_file():
        raise SystemExit(f"No está el filtro junto al léxico: {ruta}")
    spec = importlib.util.spec_from_file_location("filtro_reco", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def conectar():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("ABORTO: falta DATABASE_URL")
    url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return psycopg2.connect(url)


def esquema_esperado() -> str:
    nombre = os.environ.get("RECO_SCHEMA", "reco")
    if not SCHEMA_RE.match(nombre):
        raise SystemExit(f"ABORTO: RECO_SCHEMA no válido ({nombre})")
    return nombre


def search_path_actual(con) -> str:
    with con.cursor() as cur:
        cur.execute("SHOW search_path")
        bruto = cur.fetchone()[0] or ""
    return bruto.replace(" ", "").replace('"', "")


def exigir_search_path(con, esperado: str) -> None:
    actual = search_path_actual(con)
    if actual != esperado:
        raise SystemExit(f"ABORTO: search_path={actual or 'vacio'} (debe ser {esperado})")
    with con.cursor() as cur:
        cur.execute("SELECT set_config('search_path', %s, false)", (esperado,))


def contar_public(con) -> int:
    with con.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.messages")
        return int(cur.fetchone()[0])


def exigir_public_igual(antes: int, despues: int) -> None:
    if antes != despues:
        raise SystemExit(f"ALERTA: public.messages cambió ({antes} -> {despues})")


def volcar(cursor, lote) -> None:
    psycopg2.extras.execute_values(
        cursor,
        """INSERT INTO reco_flags
           (message_pk, regla, incluido, hits_a, hits_b, hits_veto, lexico_version)
           VALUES %s
           ON CONFLICT (message_pk) DO UPDATE SET
             regla=EXCLUDED.regla,
             incluido=EXCLUDED.incluido,
             hits_a=EXCLUDED.hits_a,
             hits_b=EXCLUDED.hits_b,
             hits_veto=EXCLUDED.hits_veto,
             lexico_version=EXCLUDED.lexico_version,
             flagged_at=now()""",
        lote,
    )


def marcar(args) -> None:
    import yaml

    filtro = cargar_filtro(Path(args.lexico))
    compilado = filtro.compilar(yaml.safe_load(Path(args.lexico).read_text(encoding="utf-8")))
    capa_a, capa_b, veto = compilado
    con = conectar()
    try:
        con.autocommit = False
        exigir_search_path(con, esquema_esperado())
        antes = contar_public(con)
        # WITH HOLD: el commit de cada lote no cierra el cursor de servidor.
        cur = con.cursor(name="reco_lectura", withhold=True)
        cur.itersize = 2000
        escritura = con.cursor()
        extra = "" if args.rehacer else "AND (fl.message_pk IS NULL OR fl.lexico_version <> %s)"
        params = [args.inicio, args.fin] + ([] if args.rehacer else [args.version])
        cur.execute(
            f"""SELECT m.id, m.message_text
                FROM messages m
                LEFT JOIN reco_flags fl ON fl.message_pk = m.id
                WHERE m.date_sent >= %s AND m.date_sent < (%s::date + 1)
                {extra}""",
            params,
        )
        n = 0
        lote = []
        for pk, texto in cur:
            regla, incluido, ha, hb, hv = filtro.clasificar(texto or "", capa_a, capa_b, veto)
            lote.append((pk, regla, incluido, "|".join(ha), "|".join(hb), "|".join(hv), args.version))
            if len(lote) >= 2000:
                volcar(escritura, lote)
                con.commit()
                n += len(lote)
                lote = []
                print(n, "marcados", flush=True)
        if lote:
            volcar(escritura, lote)
            n += len(lote)
        con.commit()
        despues = contar_public(con)
        exigir_public_igual(antes, despues)
        print("Total marcados:", n)
        print(f"public.messages sin cambios ({despues})")
    finally:
        con.close()


def exportar(args) -> None:
    import pandas as pd

    con = conectar()
    try:
        con.autocommit = False
        exigir_search_path(con, esquema_esperado())
        q = """SELECT 'RECO' AS corpus, m.id AS message_pk, m.message_id,
                      c.username AS channel, rc.tipo, rc.pais,
                      m.date_sent, m.message_text AS message, m.views, m.forwards,
                      m.replies, m.url, fl.regla, fl.incluido, fl.hits_a, fl.hits_b, fl.hits_veto
               FROM messages m
               JOIN channels c ON c.id = m.channel_id
               LEFT JOIN reco_canales rc ON lower(rc.username) = lower(c.username)
               LEFT JOIN reco_flags fl ON fl.message_pk = m.id
               WHERE m.date_sent >= %(i)s AND m.date_sent < (%(f)s::date + 1)"""
        if args.solo_incluidos:
            q += " AND fl.incluido = 1"
        df = pd.read_sql(q, con, params={"i": args.inicio, "f": args.fin})
        destino = Path(args.export)
        destino.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(destino, index=False)
        print(len(df), "filas ->", destino)
    finally:
        con.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    defecto_lex = Path(__file__).resolve().parent.parent / "metodologia" / "02_lexico.yaml"
    ap.add_argument("--lexico", default=str(defecto_lex))
    ap.add_argument("--version", default=os.environ.get("LEXICO_VERSION", "v0.1"))
    ap.add_argument("--rehacer", action="store_true")
    ap.add_argument("--inicio", default=os.environ.get("RECO_VENTANA_INICIO", "2024-09-01"))
    ap.add_argument("--fin", default=os.environ.get("RECO_VENTANA_FIN", "2025-12-31"))
    ap.add_argument("--export")
    ap.add_argument("--solo-incluidos", action="store_true")
    args = ap.parse_args(argv)
    if args.export:
        exportar(args)
    else:
        marcar(args)


if __name__ == "__main__":
    main()
