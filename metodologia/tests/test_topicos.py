"""El texto para tópicos pierde la URL y el mensaje corto."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _cargar():
    ruta = ROOT / "metodologia" / "06_topicos.py"
    spec = importlib.util.spec_from_file_location("topicos_reco", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TOP = _cargar()


def test_quita_la_url_y_descarta_lo_que_queda_corto():
    assert "eldiestro" not in TOP.texto_nlp("Coche eléctrico https://eldiestro.info/2024/09/nota y poco")
    df = pd.DataFrame(
        {
            "message_pk": [1, 2],
            "channel": ["alfa", "beta"],
            "date_sent": ["2024-10-01", "2024-10-02"],
            "regla": ["R2", "R3"],
            "message": [
                "https://t.me/algo",
                "La agenda climática y el pacto verde ocupan el mensaje entero de este canal",
            ],
        }
    )
    listo = TOP.preparar(df)
    assert len(listo) == 1
    assert listo.iloc[0]["channel"] == "beta"
    assert "https://" not in listo.iloc[0]["message_nlp"]


def test_nmf_separa_dos_temas_repetidos():
    clima = ["el pacto verde y la agenda climatica ocupan el discurso "] * 8
    campo = ["la guerra al campo y los agricultores rechazan el pacto "] * 8
    textos = pd.Series(clima + campo)
    info, etiquetas = TOP.topicos_nmf(textos, n=2, min_df=2)
    assert len(info) == 2
    assert len(set(etiquetas)) == 2
    assert set(etiquetas[:8]) != set(etiquetas[8:])
