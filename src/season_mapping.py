"""Mapeo de categoria actual -> categoria(s) de la temporada anterior.

Una categoria que recien arranca temporada (ej. 16A en 26-27, con poco o
ningun historial propio todavia) es la MISMA cohorte de jugadores que el año
pasado entrenaba bajo otro nombre. Para que la propuesta y las referencias de
carga no arranquen de cero en cada cambio de temporada, se busca tambien en
el historial de esa categoria anterior.

Confirmado por Nico (29/09/2026):
- Las categorias numericas suben un año y mantienen la letra:
  13A->14A->15A->16A, igual para B (13B->14B->15B->16B).
- 16A pasa a JA y JB al año siguiente (el equipo se divide en dos).
- CAF y CBF pasan a JAF al año siguiente (los dos equipos se unen en uno).
- El resto de las categorias (13A/13B sin antecedente, 1EQM, 1EQF, FILIAL,
  JBF, CAF, CBF, SEL. INF/CAD/JUV) no tiene equivalente de temporada
  anterior: se manejan solo con su propio historial.
"""
from __future__ import annotations

CATEGORIA_ANTERIOR: dict[str, tuple[str, ...]] = {
    "14A": ("13A",),
    "15A": ("14A",),
    "16A": ("15A",),
    "14B": ("13B",),
    "15B": ("14B",),
    "16B": ("15B",),
    "JA": ("16A",),
    "JB": ("16A",),
    "JAF": ("CAF", "CBF"),
}


def categorias_anteriores_de(categoria: str) -> tuple[str, ...]:
    return CATEGORIA_ANTERIOR.get(categoria.strip().upper(), ())
