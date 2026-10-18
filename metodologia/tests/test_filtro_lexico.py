"""Reglas R1-R4 sobre el léxico v0.1, sin modificar los patrones.

Los casos de falso positivo documentan el comportamiento actual.
No son el ajuste propuesto: el yaml no se ha tocado.
"""
from pathlib import Path

import importlib.util

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FILTRO = _cargar("filtro_reco", ROOT / "metodologia" / "03_filtro_lexico.py")


@pytest.fixture(scope="module")
def compilado():
    cfg = yaml.safe_load((ROOT / "metodologia" / "02_lexico.yaml").read_text(encoding="utf-8"))
    return FILTRO.compilar(cfg)


def regla(texto, compilado):
    return FILTRO.clasificar(texto, *compilado)


def test_banco_de_la_guia(compilado):
    assert FILTRO.self_test(*compilado)


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("El Gran Reseteo y la Agenda 2030 quieren que no tengas nada", "R1"),
        ("La #Agend@2030 avanza en el pleno", "R2"),
        ("Es una estafa climática, el CO2 es vida", "R3"),
        ("España presenta su candidatura al Mundial 2030", "R4"),
        ("Hoy hace sol en Granada", "NONE"),
        ("Visión 2030 de Arabia Saudí", "R4"),
        ("Mundial 2030 pagado por el Nuevo Orden Mundial", "R3"),
    ],
)
def test_r1_a_r4(texto, esperado, compilado):
    r, incluido, *_ = regla(texto, compilado)
    assert r == esperado
    assert incluido == int(esperado in ("R1", "R2", "R3"))


def test_normaliza_tildes_y_deja_r2(compilado):
    r, incluido, hits_a, _, _ = regla("La Ágenda 2030 sigue su curso", compilado)
    assert r == "R2"
    assert incluido == 1
    assert "agenda_2030" in hits_a


def test_2030_suelto_sin_veto_es_r2(compilado):
    r, _, hits_a, _, veto = regla("El plan 2030 sigue adelante", compilado)
    assert r == "R2"
    assert hits_a == ["2030_suelto"]
    assert veto == []


def test_veto_anula_el_2030_suelto(compilado):
    r, incluido, hits_a, _, veto = regla("Candidatura para el mundial 2030", compilado)
    assert r == "R4"
    assert incluido == 0
    assert hits_a == []
    assert veto


def test_agenda_mas_mundial_sin_capa_b_cae_en_r4(compilado):
    """El veto gana a la capa A cuando no hay capa B. Comportamiento actual, no el deseado."""
    r, incluido, hits_a, _, _ = regla("La Agenda 2030 y el Mundial 2030", compilado)
    assert r == "R4"
    assert incluido == 0
    assert "agenda_2030" in hits_a


def test_veinte_espacio_treinta_se_vuelve_2030(compilado):
    assert regla("horizonte 20 30", compilado)[0] == "R2"


def test_hashtag_con_arroba_entra(compilado):
    assert regla("La #Agend@2030 avanza", compilado)[0] == "R2"


def test_arroba_sustituye_la_a_o_cae_en_a2030(compilado):
    # agend@2030 -> agenda2030 (el patrón agenda ?2030).
    # agenda@2030 -> agendaa2030, que casa por el patrón suelto a2030.
    assert regla("la agend@2030 avanza", compilado)[0] == "R2"
    assert regla("la agenda@2030 avanza", compilado)[0] == "R2"


def test_nombre_y_todos_no_disparan_los_limites_de_palabra(compilado):
    assert regla("El nombre del canal es otro", compilado)[0] == "NONE"
    assert regla("Todos los días hace sol en Lima", compilado)[0] == "NONE"
    assert regla("Nomás llegamos al centro", compilado)[0] == "NONE"
    assert regla("El bonus del mes llegó", compilado)[0] == "NONE"


@pytest.mark.parametrize(
    "texto,regla_esperada",
    [
        ("Publicat en nom de l'associacio", "R3"),
        ("La NOM-051 obliga al etiquetado frontal", "R3"),
        ("Revisa la agenda 21 de octubre, hay pleno", "R3"),
        ("La agenda 21:30 es la reunion de vecinos", "R3"),
        ("La agenda 2100 no es un plan", "R3"),
        ("Me han multado en la ZBE de Madrid", "R2"),
        ("Te mando el presupuesto.ods del año", "R2"),
        ("Mi fondo ESG ha caído un 3 por ciento", "R2"),
        ("La ONU pide un alto el fuego en la región", "R2"),
    ],
)
def test_falsos_positivos_actuales_sin_ajustar(texto, regla_esperada, compilado):
    assert regla(texto, compilado)[0] == regla_esperada
