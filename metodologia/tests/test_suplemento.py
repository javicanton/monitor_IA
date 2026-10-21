"""El suplemento junta mensaje, tópico y red sin perder la dirección del reenvío."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _cargar():
    ruta = ROOT / "metodologia" / "08_suplemento.py"
    spec = importlib.util.spec_from_file_location("suplemento_reco", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SUP = _cargar()


def test_clasifica_tema_apartado_y_texto_corto():
    assert SUP.clasificar(1)[2] == "tema"
    assert SUP.clasificar(1)[1] == "Agenda 2030 en España y gobierno"
    assert SUP.clasificar(13)[2] == "apartado"
    assert SUP.clasificar(None) == ("", "Sin texto suficiente", "sin_texto")


def test_el_mensaje_corto_queda_fuera_del_modelo_y_la_arista_conserva_el_sentido():
    corpus = pd.DataFrame(
        {
            "message_pk": [1, 2, 3],
            "message_id": [10, 20, 30],
            "channel": ["alfa", "beta", "alfa"],
            "date_sent": ["2024-09-15T00:00:00Z", "2024-10-02T00:00:00Z", "2026-03-01T00:00:00Z"],
            "regla": ["R2", "R3", "R2"],
            "message": ["texto de la agenda", "otro texto", "fuera de ventana"],
            "views": [5, 1, 0],
            "forwards": [2, 0, 0],
            "replies": [0, 0, 0],
            "url": ["https://t.me/alfa/10", "", ""],
        }
    )
    asignacion = pd.DataFrame({"message_pk": [1], "topico": [1]})
    mensajes = SUP.mensajes_suplemento(corpus, asignacion)
    assert list(mensajes["id_mensaje"]) == [1, 2]
    assert mensajes.loc[mensajes["id_mensaje"] == 1, "uso"].iloc[0] == "tema"
    assert mensajes.loc[mensajes["id_mensaje"] == 2, "uso"].iloc[0] == "sin_texto"
    assert "fuera de ventana" not in set(mensajes["texto"])
    nodos = pd.DataFrame(
        {
            "username": ["alfa", "beta"],
            "nombre": ["Alfa", "Beta"],
            "tipo": ["", ""],
            "pais": ["ES", ""],
            "origen": ["semilla", "snowball"],
            "comunidad": [0, -1],
            "grado_entrada": [1, 0],
            "grado_salida": [0, 1],
            "peso_entrada": [4, 0],
            "peso_salida": [0, 4],
        }
    )
    canales = SUP.canales_suplemento(nodos, mensajes)
    beta = canales.set_index("canal").loc["beta"]
    assert pd.isna(beta["comunidad"])
    assert int(beta["mensajes"]) == 1
    aristas = SUP.aristas_suplemento(
        pd.DataFrame({"origen": ["beta", "alfa"], "destino": ["alfa", "alfa"], "peso": [4, 2]})
    )
    assert list(aristas["origen"]) == ["beta"]
    assert list(aristas["destino"]) == ["alfa"]
    assert int(aristas["peso"].iloc[0]) == 4


def test_escribe_el_paquete(tmp_path):
    corpus = tmp_path / "corpus.csv"
    analisis = tmp_path / "analisis"
    analisis.mkdir()
    pd.DataFrame(
        {
            "message_pk": [1],
            "message_id": [10],
            "channel": ["alfa"],
            "date_sent": ["2024-09-15T00:00:00Z"],
            "regla": ["R2"],
            "message": ["La agenda 2030 y el pacto verde"],
            "views": [3],
            "forwards": [1],
            "replies": [0],
            "url": ["https://t.me/alfa/10"],
        }
    ).to_csv(corpus, index=False)
    pd.DataFrame(
        {"message_pk": [1], "channel": ["alfa"], "date_sent": ["2024-09-15"], "regla": ["R2"], "topico": [5]}
    ).to_csv(analisis / "topicos_asignacion.csv", index=False)
    pd.DataFrame({"topico": [5], "mensajes": [1], "terminos": ["cambio climatico"]}).to_csv(
        analisis / "topicos_info.csv", index=False
    )
    pd.DataFrame(
        {
            "username": ["alfa"],
            "nombre": ["Alfa"],
            "tipo": [""],
            "pais": ["ES"],
            "origen": ["semilla"],
            "comunidad": [0],
            "grado_entrada": [0],
            "grado_salida": [0],
            "peso_entrada": [0],
            "peso_salida": [0],
        }
    ).to_csv(analisis / "red_nodos.csv", index=False)
    pd.DataFrame({"origen": ["alfa"], "destino": ["beta"], "peso": [2]}).to_csv(
        analisis / "red_aristas.csv", index=False
    )
    paquete = SUP.generar(corpus, analisis, tmp_path / "suplemento")
    assert paquete.is_file()
    assert paquete.name == "reco_suplemento.tar.gz"
    leeme = (tmp_path / "suplemento" / "LEEME.txt").read_text(encoding="utf-8")
    assert "origen   Canal citado" in leeme
    assert "precisión 0,6" in leeme
    guardado = pd.read_csv(tmp_path / "suplemento" / "mensajes.csv", encoding="utf-8-sig")
    assert guardado.iloc[0]["bloque"] == "Clima y Pacto Verde"
    assert "pacto verde" in guardado.iloc[0]["texto"]
