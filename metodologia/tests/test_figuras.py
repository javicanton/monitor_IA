"""Las figuras salen de los CSV y los veinte tópicos entran en un solo sitio."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _cargar():
    ruta = ROOT / "metodologia" / "07_figuras.py"
    spec = importlib.util.spec_from_file_location("figuras_reco", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FIG = _cargar()


def test_los_veinte_topicos_entran_una_vez():
    ids = []
    for _, miembros in FIG.BLOQUES:
        ids.extend(miembros)
    ids.extend(FIG.APARTADOS)
    assert sorted(ids) == list(range(20))
    assert set(FIG.ETIQUETAS) == {i for _, miembros in FIG.BLOQUES for i in miembros}


def test_la_serie_rellena_los_dieciseis_meses():
    por_mes = pd.DataFrame({"mes": ["2024-09", "2024-11"], "mensajes": [10, 4], "canales": [2, 1]})
    completa = FIG.serie_completa(por_mes)
    assert list(completa["mes"]) == FIG.MESES
    assert len(completa) == 16
    assert int(completa.loc[completa["mes"] == "2024-10", "mensajes"].iloc[0]) == 0
    assert int(completa["mensajes"].sum()) == 14


def test_el_ranking_se_queda_con_quien_mas_reenvios_recibe():
    nodos = pd.DataFrame(
        {
            "username": ["alfa", "beta", "gamma"],
            "nombre": ["Alfa", "Beta", "Gamma"],
            "peso_entrada": [1, 9, 4],
            "peso_salida": [0, 0, 0],
        }
    )
    assert list(FIG.canales_visibles(nodos, n=2)["username"]) == ["beta", "gamma"]


def test_la_red_se_queda_con_las_aristas_mas_pesadas():
    aristas = pd.DataFrame({"origen": ["a", "b", "c"], "destino": ["b", "c", "a"], "peso": [1, 9, 4]})
    visibles = FIG.aristas_visibles(aristas, max_aristas=2)
    assert list(visibles["peso"]) == [9, 4]


def test_los_bloques_dejan_fuera_el_resto():
    conteos = pd.Series(0, index=range(20))
    conteos[1] = 10
    conteos[13] = 30
    bloques = FIG.tabla_bloques(conteos)
    assert int(bloques.loc[bloques["bloque"].str.startswith("Agenda"), "textos"].iloc[0]) == 10
    assert int(bloques["textos"].sum()) == 10
    apartados = FIG.tabla_apartados(conteos)
    assert int(apartados.loc[apartados["topico"] == 13, "textos"].iloc[0]) == 30


def test_genera_los_png(tmp_path):
    analisis = tmp_path / "analisis"
    analisis.mkdir()
    pd.DataFrame(
        {"mes": ["2024-09", "2024-10"], "mensajes": [5, 8], "canales": [1, 2]}
    ).to_csv(analisis / "series_mes.csv", index=False)
    pd.DataFrame(
        {"mes": ["2024-09", "2024-09", "2024-10"], "regla": ["R2", "R3", "R2"], "mensajes": [4, 1, 8]}
    ).to_csv(analisis / "series_mes_regla.csv", index=False)
    pd.DataFrame(
        {
            "username": ["alfa", "beta", "gamma"],
            "nombre": ["Alfa", "Beta", "Gamma"],
            "peso_entrada": [3, 1, 0],
            "peso_salida": [1, 3, 0],
            "comunidad": [0, 0, 1],
        }
    ).to_csv(analisis / "red_nodos.csv", index=False)
    pd.DataFrame(
        {"origen": ["alfa", "beta"], "destino": ["beta", "alfa"], "peso": [3, 1]}
    ).to_csv(analisis / "red_aristas.csv", index=False)
    pd.DataFrame({"topico": [1, 1, 13, 5]}).to_csv(analisis / "topicos_asignacion.csv", index=False)
    (analisis / "red_resumen.txt").write_text("canales_corpus=3\n", encoding="utf-8")
    destino = tmp_path / "figuras"
    texto = FIG.generar(analisis, destino)
    for nombre in (
        "serie_mensual.png",
        "serie_regla.png",
        "red_reenvios.png",
        "red_canales.png",
        "topicos_bloques.png",
        "topicos_detalle.png",
    ):
        assert (destino / nombre).stat().st_size > 1000
        assert (destino / nombre).with_suffix(".pdf").is_file()
    assert "canales_corpus=3" in texto
    assert "en_bloques=3" in texto
