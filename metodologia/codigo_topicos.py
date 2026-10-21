"""Código de la segunda pasada NMF (20 tópicos, random_state 2026).

Lo comparten las figuras y el suplemento para que el bloque de un tópico
no cambie de un archivo a otro.
"""
from __future__ import annotations

BLOQUES = (
    ("Agenda 2030 en España y gobierno", (1, 12)),
    ("Guerras dentro del corpus", (14, 16)),
    ("Foros y orden mundial", (4, 7, 0, 10)),
    ("Clima y Pacto Verde", (5, 18)),
    ("Actores y programas", (6, 8)),
    ("Geoingeniería", (17,)),
    ("Control cotidiano", (19, 15, 2)),
)
APARTADOS = {
    13: "Resto sin tema",
    11: "Índice de canal",
    3: "Lema de canal",
    9: "Pie de canal",
}
ETIQUETAS = {
    1: "Agenda 2030, PP, agricultores",
    12: "Sánchez, PSOE, Davos",
    14: "Gaza, Israel, Irán, ONU",
    16: "Ucrania, Rusia, Trump",
    4: "Nuevo orden mundial",
    7: "Davos y Schwab",
    0: "Naciones Unidas y Rockefeller",
    10: "Unión Europea",
    5: "Cambio climático e IPCC",
    18: "Pacto Verde, von der Leyen, Vox",
    6: "Soros, USAID, Musk",
    8: "Vidal, Ramírez, gran reseteo",
    17: "Geoingeniería, HAARP, estelas",
    19: "Ciudades de 15 minutos y ZBE",
    15: "«No tendrás nada y serás feliz»",
    2: "Dinero físico y crédito social",
}


def _vacio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str) and not valor.strip():
        return True
    if isinstance(valor, float) and valor != valor:
        return True
    return False


def clasificar(topico) -> tuple[str, str, str]:
    """Devuelve etiqueta, bloque y uso (tema, apartado o sin_texto)."""
    if _vacio(topico):
        return "", "Sin texto suficiente", "sin_texto"
    tema = int(topico)
    if tema in APARTADOS:
        return APARTADOS[tema], APARTADOS[tema], "apartado"
    for nombre, miembros in BLOQUES:
        if tema in miembros:
            return ETIQUETAS[tema], nombre, "tema"
    return "", "", "desconocido"
