#!/usr/bin/env python3
"""Arma el suplemento público: CSV para graficar y un tar.gz de un solo archivo.

No reentrena tópicos ni redibuja la red. Junta el corpus incluido, la
asignación NMF y la red interna.

En la EC2:
  .venv/bin/python metodologia/08_suplemento.py \
    --corpus out/corpus_reco_B.csv \
    --analisis out/analisis \
    --out-dir out/suplemento
"""
from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codigo_topicos import APARTADOS, BLOQUES, ETIQUETAS, clasificar

INICIO = "2024-09-01"
FIN = "2026-01-01"


def _limpio(valor) -> str:
    if valor is None or (isinstance(valor, float) and valor != valor):
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _entero(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce").fillna(0).astype(int)


def mensajes_suplemento(corpus: pd.DataFrame, asignacion: pd.DataFrame) -> pd.DataFrame:
    base = corpus.copy()
    base["id_mensaje"] = pd.to_numeric(base["message_pk"], errors="coerce").astype("Int64")
    fecha = pd.to_datetime(base["date_sent"], utc=True, errors="coerce")
    en_ventana = fecha.notna() & (fecha >= INICIO) & (fecha < FIN)
    base = base.loc[en_ventana].copy()
    fecha = fecha.loc[base.index]
    base["fecha"] = fecha.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    base["mes"] = fecha.dt.strftime("%Y-%m")
    asig = asignacion.copy()
    asig["id_mensaje"] = pd.to_numeric(asig["message_pk"], errors="coerce").astype("Int64")
    asig = asig.dropna(subset=["id_mensaje"]).drop_duplicates("id_mensaje")
    asig["topico"] = pd.to_numeric(asig["topico"], errors="coerce").astype("Int64")
    base = base.merge(asig[["id_mensaje", "topico"]], on="id_mensaje", how="left")
    etiquetas, bloques, usos = [], [], []
    for tema in base["topico"]:
        etiqueta, bloque, uso = clasificar(None if pd.isna(tema) else int(tema))
        etiquetas.append(etiqueta)
        bloques.append(bloque)
        usos.append(uso)
    salida = pd.DataFrame(
        {
            "id_mensaje": base["id_mensaje"],
            "id_telegram": base["message_id"] if "message_id" in base.columns else "",
            "canal": base["channel"].map(_limpio),
            "fecha": base["fecha"],
            "mes": base["mes"],
            "regla": base["regla"].map(_limpio) if "regla" in base.columns else "",
            "topico": base["topico"],
            "etiqueta": etiquetas,
            "bloque": bloques,
            "uso": usos,
            "vistas": _entero(base["views"]) if "views" in base.columns else 0,
            "reenvios": _entero(base["forwards"]) if "forwards" in base.columns else 0,
            "respuestas": _entero(base["replies"]) if "replies" in base.columns else 0,
            "url": base["url"].map(_limpio) if "url" in base.columns else "",
            "texto": base["message"].map(lambda t: "" if pd.isna(t) else str(t)) if "message" in base.columns else "",
        }
    )
    return salida.sort_values(["fecha", "id_mensaje"]).reset_index(drop=True)


def canales_suplemento(nodos: pd.DataFrame, mensajes: pd.DataFrame) -> pd.DataFrame:
    df = nodos.copy()
    df["canal"] = df["username"].map(_limpio)
    cuentas = mensajes.groupby("canal").size().rename("mensajes")
    df = df.merge(cuentas, left_on="canal", right_index=True, how="left")
    df["mensajes"] = df["mensajes"].fillna(0).astype(int)
    comunidad = pd.to_numeric(df["comunidad"], errors="coerce") if "comunidad" in df.columns else pd.Series(pd.NA, index=df.index)
    df["comunidad"] = comunidad.where(comunidad >= 0)
    salida = pd.DataFrame(
        {
            "canal": df["canal"],
            "nombre": df["nombre"].map(_limpio) if "nombre" in df.columns else df["canal"],
            "tipo": df["tipo"].map(_limpio) if "tipo" in df.columns else "",
            "pais": df["pais"].map(_limpio) if "pais" in df.columns else "",
            "origen": df["origen"].map(_limpio) if "origen" in df.columns else "",
            "comunidad": df["comunidad"].astype("Int64"),
            "grado_entrada": _entero(df["grado_entrada"]) if "grado_entrada" in df.columns else 0,
            "grado_salida": _entero(df["grado_salida"]) if "grado_salida" in df.columns else 0,
            "reenvios_recibidos": _entero(df["peso_entrada"]) if "peso_entrada" in df.columns else 0,
            "reenvios_emitidos": _entero(df["peso_salida"]) if "peso_salida" in df.columns else 0,
            "mensajes": df["mensajes"],
        }
    )
    return salida.sort_values(["reenvios_recibidos", "mensajes"], ascending=False).reset_index(drop=True)


def aristas_suplemento(aristas: pd.DataFrame) -> pd.DataFrame:
    df = aristas.copy()
    df["origen"] = df["origen"].map(_limpio)
    df["destino"] = df["destino"].map(_limpio)
    df["peso"] = _entero(df["peso"])
    df = df[(df["peso"] > 0) & (df["origen"] != "") & (df["destino"] != "") & (df["origen"] != df["destino"])]
    return df.sort_values("peso", ascending=False).reset_index(drop=True)


def topicos_suplemento(mensajes: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    modelo = mensajes[mensajes["uso"] != "sin_texto"]
    total = len(modelo)
    terminos = {}
    if info is not None and not info.empty and "topico" in info.columns:
        for _, fila in info.iterrows():
            if pd.isna(fila["topico"]):
                continue
            terminos[int(fila["topico"])] = _limpio(fila.get("terminos", ""))
    filas = []
    vistos = set()
    for nombre, miembros in BLOQUES:
        for tema in miembros:
            vistos.add(tema)
            textos = int((modelo["topico"] == tema).sum())
            filas.append(
                {
                    "topico": tema,
                    "etiqueta": ETIQUETAS[tema],
                    "bloque": nombre,
                    "uso": "tema",
                    "textos": textos,
                    "porcentaje": round(100 * textos / total, 1) if total else 0,
                    "terminos": terminos.get(tema, ""),
                }
            )
    for tema, nombre in APARTADOS.items():
        vistos.add(tema)
        textos = int((modelo["topico"] == tema).sum())
        filas.append(
            {
                "topico": tema,
                "etiqueta": nombre,
                "bloque": nombre,
                "uso": "apartado",
                "textos": textos,
                "porcentaje": round(100 * textos / total, 1) if total else 0,
                "terminos": terminos.get(tema, ""),
            }
        )
    return pd.DataFrame(filas)


def serie_mes(mensajes: pd.DataFrame) -> pd.DataFrame:
    if mensajes.empty:
        return pd.DataFrame(columns=["mes", "mensajes", "canales"])
    return (
        mensajes.groupby("mes", as_index=False)
        .agg(mensajes=("id_mensaje", "size"), canales=("canal", "nunique"))
        .sort_values("mes")
        .reset_index(drop=True)
    )


def serie_regla(mensajes: pd.DataFrame) -> pd.DataFrame:
    if mensajes.empty:
        return pd.DataFrame(columns=["mes", "regla", "mensajes"])
    return (
        mensajes.groupby(["mes", "regla"], as_index=False)
        .size()
        .rename(columns={"size": "mensajes"})
        .sort_values(["mes", "regla"])
        .reset_index(drop=True)
    )


def redactar_leeme(mensajes: pd.DataFrame, canales: pd.DataFrame, aristas: pd.DataFrame) -> str:
    temas = int((mensajes["uso"] == "tema").sum())
    apartados = int((mensajes["uso"] == "apartado").sum())
    cortos = int((mensajes["uso"] == "sin_texto").sum())
    return "\n".join(
        [
            "RECO. Suplemento del corpus incluido.",
            "Narrativa en español sobre la Agenda 2030 en Telegram.",
            "Ventana: 1 de septiembre de 2024 a 31 de diciembre de 2025.",
            "Léxico v0.1. Tópicos: NMF, 20 grupos, semilla 2026, segunda pasada.",
            "",
            f"mensajes={len(mensajes)}",
            f"mensajes_con_tema={temas}",
            f"mensajes_apartados={apartados}",
            f"mensajes_sin_texto_suficiente={cortos}",
            f"canales={len(canales)}",
            f"aristas_internas={len(aristas)}",
            "",
            "Ficheros",
            "mensajes.csv  Una fila por mensaje incluido. Series y tópicos salen de aquí.",
            "canales.csv   Una fila por canal del corpus, con su comunidad y sus reenvíos.",
            "aristas.csv   Reenvíos entre canales del corpus. Sirve para el grafo.",
            "topicos.csv   Los 20 tópicos, su bloque y sus términos.",
            "serie_mes.csv y serie_regla.csv  Agregados listos para una serie temporal.",
            "",
            "Columnas de mensajes.csv",
            "id_mensaje     Identificador interno. Une esta tabla con el modelo.",
            "id_telegram    Identificador del mensaje en Telegram.",
            "canal          Handle del canal, sin @.",
            "fecha          UTC, ISO-8601.",
            "mes            Año-mes, para la serie.",
            "regla          Regla del léxico v0.1 que lo incluyó: R1, R2 o R3.",
            "topico         Número de 0 a 19. Vacío si el texto se quedó corto.",
            "etiqueta       Nombre corto del tópico.",
            "bloque         Grupo temático, o el apartado que no se interpreta.",
            "uso            tema, apartado o sin_texto. Para graficar los temas, filtrar uso=tema.",
            "vistas, reenvios, respuestas  Cifras de Telegram en el momento de la recogida.",
            "url            Enlace al mensaje.",
            "texto          Texto público del mensaje.",
            "",
            "Columnas de aristas.csv",
            "origen   Canal citado: de ahí sale el mensaje reenviado.",
            "destino  Canal que reenvía.",
            "peso     Número de reenvíos en ese sentido.",
            "En Gephi: origen = source, destino = target, peso = weight.",
            "En canales.csv el identificador es canal.",
            "reenvios_recibidos suma el peso de las aristas que llegan al canal.",
            "comunidad vacía: el canal no tiene ningún reenvío interno.",
            "",
            "Uso de los tópicos",
            "tema      Entra en la lectura. bloque dice a qué familia pertenece.",
            "apartado  No se interpreta como tema: resto sin tema, índice de un canal, lema o pie.",
            "sin_texto El mensaje incluido tiene menos de 40 caracteres tras quitar la URL.",
            "El porcentaje de topicos.csv está calculado sobre los mensajes con tópico, apartados incluidos.",
            "",
            "Límites que acompañan al archivo",
            "La validación doble de 400 mensajes dio kappa 0,885, precisión 0,6 y exhaustividad 0,5.",
            "Los falsos positivos de esa muestra caían en ONU, Davos, geoingeniería y HAARP.",
            "La recogida de la ronda de snowball se detuvo antes de completar la lista: aquí solo están los canales recorridos.",
            "Los reenvíos hacia canales de fuera del corpus no están en aristas.csv.",
            "Los textos proceden de canales públicos de Telegram.",
            "",
            "Cómo abrirlo",
            "UTF-8, separador coma. En Excel: Datos, Desde texto o CSV, y elegir coma.",
            "Flourish, Datawrapper, R y Gephi leen estos CSV directamente.",
            "",
        ]
    )


def _escribir_csv(df: pd.DataFrame, ruta: Path) -> None:
    salida = df.copy()
    for col in salida.columns:
        if str(salida[col].dtype) == "Int64":
            salida[col] = salida[col].astype("object").where(salida[col].notna(), "")
    salida.to_csv(ruta, index=False, encoding="utf-8-sig")


def generar(corpus: Path, analisis: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    mensajes = mensajes_suplemento(
        pd.read_csv(corpus, low_memory=False),
        pd.read_csv(analisis / "topicos_asignacion.csv", low_memory=False),
    )
    canales = canales_suplemento(pd.read_csv(analisis / "red_nodos.csv"), mensajes)
    aristas = aristas_suplemento(pd.read_csv(analisis / "red_aristas.csv"))
    info_ruta = analisis / "topicos_info.csv"
    info = pd.read_csv(info_ruta) if info_ruta.is_file() else pd.DataFrame()
    tablas = {
        "mensajes.csv": mensajes,
        "canales.csv": canales,
        "aristas.csv": aristas,
        "topicos.csv": topicos_suplemento(mensajes, info),
        "serie_mes.csv": serie_mes(mensajes),
        "serie_regla.csv": serie_regla(mensajes),
    }
    for nombre, tabla in tablas.items():
        _escribir_csv(tabla, out_dir / nombre)
    (out_dir / "LEEME.txt").write_text(redactar_leeme(mensajes, canales, aristas), encoding="utf-8")
    paquete = out_dir.parent / "reco_suplemento.tar.gz"
    with tarfile.open(paquete, "w:gz") as tar:
        tar.add(out_dir, arcname="reco_suplemento")
    print(f"mensajes={len(mensajes)}")
    print(f"canales={len(canales)}")
    print(f"aristas={len(aristas)}")
    print(f"paquete={paquete}")
    return paquete


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--analisis", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    generar(args.corpus, args.analisis, args.out_dir)


if __name__ == "__main__":
    main()
