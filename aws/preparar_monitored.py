#!/usr/bin/env python3
"""Convierte la semilla en la lista que importa monitorIA y en el INSERT de reco_canales.

Salida (por defecto, junto a este script):
  reco_monitored.csv       username,title,discontinued,status (sin cabecera)
  reco_canales_insert.sql  INSERT en <esquema>.reco_canales

Solo entran filas con handle y con incluir distinto de 0.
La columna origen es opcional (semilla por defecto, o snowball).
Uso:
  python3 aws/preparar_monitored.py metodologia/01_canales_semilla.csv
  python3 aws/preparar_monitored.py metodologia/01_canales_semilla.csv --schema reco_test
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ORIGENES = {"semilla", "snowball"}


def norm_handle(valor: str) -> str:
    h = (valor or "").strip().lstrip("@")
    h = re.sub(r"^https?://(t\.me|telegram\.me)/(s/)?", "", h, flags=re.I)
    h = h.split("/")[0].split("?")[0].strip().lower()
    return h


def sql_literal(valor: str) -> str:
    return "'" + (valor or "").replace("'", "''") + "'"


def validar_esquema(nombre: str) -> str:
    if not SCHEMA_RE.match(nombre or ""):
        raise SystemExit(f"Esquema no válido: {nombre!r}")
    return nombre


def filas_utiles(src: Path):
    with src.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            handle = norm_handle(r.get("handle_telegram", ""))
            if not handle or (r.get("incluir") or "").strip() == "0":
                continue
            origen = (r.get("origen") or "semilla").strip() or "semilla"
            if origen not in ORIGENES:
                raise SystemExit(f"origen no reconocido en {handle}: {origen}")
            ronda = (r.get("ronda_snowball") or "0").strip() or "0"
            if not re.fullmatch(r"\d+", ronda):
                raise SystemExit(f"ronda_snowball no numérica en {handle}: {ronda}")
            yield {
                "handle": handle,
                "nombre": (r.get("nombre_documentado") or handle).strip() or handle,
                "tipo": (r.get("tipo_provisional") or "").strip(),
                "pais": (r.get("pais_provisional") or "").strip(),
                "fuente": (r.get("fuente_documental") or "").strip(),
                "origen": origen,
                "ronda": int(ronda),
            }


def escribir(src: Path, out_dir: Path, schema: str) -> int:
    schema = validar_esquema(schema)
    utiles = list(filas_utiles(src))
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "reco_monitored.csv"
    sql_path = out_dir / "reco_canales_insert.sql"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for fila in utiles:
            writer.writerow([fila["handle"], fila["nombre"], "false", "active"])
    if not utiles:
        sql_path.write_text(
            f"-- {schema}.reco_canales: ninguna fila con handle. No hay INSERT.\n",
            encoding="utf-8",
        )
    else:
        valores = []
        for fila in utiles:
            valores.append(
                "("
                + ",".join(
                    [
                        sql_literal(fila["handle"]),
                        sql_literal(fila["nombre"]),
                        sql_literal(fila["tipo"]),
                        sql_literal(fila["pais"]),
                        sql_literal(fila["origen"]),
                        sql_literal(fila["fuente"]),
                        str(fila["ronda"]),
                    ]
                )
                + ")"
            )
        sql_path.write_text(
            f"\\set ON_ERROR_STOP on\n"
            f"SET search_path TO \"{schema}\";\n"
            "INSERT INTO reco_canales "
            "(username,nombre_documentado,tipo,pais,origen,fuente_documental,ronda_snowball) VALUES\n"
            + ",\n".join(valores)
            + "\nON CONFLICT (username) DO UPDATE SET "
            "tipo=EXCLUDED.tipo, pais=EXCLUDED.pais, origen=EXCLUDED.origen, "
            "fuente_documental=EXCLUDED.fuente_documental, ronda_snowball=EXCLUDED.ronda_snowball;\n",
            encoding="utf-8",
        )
    print(f"{len(utiles)} canales con handle -> {csv_path} y {sql_path}")
    return len(utiles)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("semilla", type=Path)
    ap.add_argument("--schema", default="reco")
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args(argv)
    if not args.semilla.is_file():
        raise SystemExit(f"No está la semilla: {args.semilla}")
    escribir(args.semilla, args.out_dir, args.schema)


if __name__ == "__main__":
    main()
