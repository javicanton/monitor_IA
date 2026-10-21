"""La red se queda dentro del corpus y la serie corta por mes."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _cargar():
    ruta = ROOT / "metodologia" / "05_red_y_series.py"
    spec = importlib.util.spec_from_file_location("red_reco", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RED = _cargar()


def _corpus():
    return pd.DataFrame(
        {
            "message_pk": [1, 2, 3, 4],
            "channel": ["alfa", "alfa", "beta", "alfa"],
            "date_sent": [
                "2024-09-15T00:00:00Z",
                "2024-10-02T00:00:00Z",
                "2024-10-20T00:00:00Z",
                "2026-03-01T00:00:00Z",
            ],
            "regla": ["R2", "R2", "R3", "R2"],
        }
    )


def _semilla():
    return pd.DataFrame(
        {
            "handle_telegram": ["alfa", "beta", "gamma", "fuera"],
            "nombre_documentado": ["Alfa", "Beta", "Gamma", "Fuera"],
            "tipo_provisional": ["T1", "", "", ""],
            "pais_provisional": ["ES", "AR", "", ""],
            "incluir": ["1", "", "1", "0"],
            "origen": ["semilla", "semilla", "snowball", "semilla"],
        }
    )


def test_la_serie_excluye_2026_y_parte_por_mes():
    por_mes, por_regla = RED.serie_mensual(_corpus())
    assert list(por_mes["mes"]) == ["2024-09", "2024-10"]
    assert int(por_mes.loc[por_mes["mes"] == "2024-10", "mensajes"].iloc[0]) == 2
    assert int(por_mes.loc[por_mes["mes"] == "2024-10", "canales"].iloc[0]) == 2
    assert set(por_regla["regla"]) == {"R2", "R3"}


def test_la_arista_hacia_fuera_no_entra_y_el_excluido_no_es_nodo():
    nodos = RED.canales_corpus(_semilla())
    assert set(nodos["username"]) == {"alfa", "beta", "gamma"}
    con_cero = pd.DataFrame(
        {
            "handle_telegram": ["alfa", "fuera"],
            "nombre_documentado": ["a", "f"],
            "tipo_provisional": ["", ""],
            "pais_provisional": ["", ""],
            "incluir": [1.0, 0.0],
            "origen": ["semilla", "semilla"],
        }
    )
    assert set(RED.canales_corpus(con_cero)["username"]) == {"alfa"}
    aristas = pd.DataFrame(
        {
            "origen": ["alfa", "beta", "alfa"],
            "destino": ["beta", "alfa", "nadie"],
            "peso": [3, 1, 9],
        }
    )
    internas = RED.aristas_internas(aristas, set(nodos["username"]))
    assert len(internas) == 2
    assert int(internas["peso"].sum()) == 4
    metricas = RED.metricas_nodos(nodos, internas)
    alfa = metricas.set_index("username").loc["alfa"]
    assert int(alfa["peso_salida"]) == 3
    assert int(alfa["peso_entrada"]) == 1
    gamma = metricas.set_index("username").loc["gamma"]
    assert int(gamma["grado_entrada"]) == 0


def test_dos_pares_separados_son_dos_comunidades(tmp_path):
    aristas = pd.DataFrame(
        {
            "origen": ["alfa", "gamma"],
            "destino": ["beta", "delta"],
            "peso": [5, 4],
        }
    )
    mapa = RED.comunidades(aristas)
    assert mapa["alfa"] == mapa["beta"]
    assert mapa["gamma"] == mapa["delta"]
    assert mapa["delta"] != mapa["alfa"]
    semilla = pd.DataFrame(
        {
            "handle_telegram": ["alfa", "beta", "gamma", "delta"],
            "nombre_documentado": ["a", "b", "g", "d"],
            "tipo_provisional": ["", "", "", ""],
            "pais_provisional": ["", "", "", ""],
            "incluir": ["1", "1", "1", "1"],
            "origen": ["semilla", "semilla", "semilla", "semilla"],
        }
    )
    texto = RED.analizar(_corpus(), aristas, semilla, tmp_path)
    assert "aristas_internas=2" in texto
    assert (tmp_path / "series_mes.csv").is_file()
    assert (tmp_path / "red_nodos.csv").is_file()
