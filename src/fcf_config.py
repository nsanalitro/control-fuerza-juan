"""Mapeo categoria -> (grup_id, team_id) de la Federacio Catalana de Futbol,
para mostrar el proximo partido de cada equipo.

grup_id: lo paso Nico (link de fcf.cat/ca/competicio?...&grupId=...).
team_id: se busca en vivo dentro de ese grupId -- por /api/competition/classificacio
(nombre del equipo que contiene "perpe"), o si la clasificacion viene vacia
(grupo sin tabla publicada todavia, ej. 13B), por /api/competition/partidos
mirando CODEQUIPO_CASA/FUERA del NOMBRE_CASA/FUERA que contiene "perpe".

Las categorias que todavia no tienen datos cargados aca simplemente no
muestran el cartel de "proximo partido" -- no rompen nada.

Reutiliza los IDs ya verificados en AFA_Control_Carga_App/config/categorias.py
(13A, 14A, 14B, 15A). SEL. INF / SEL. CAD. / SEL. JUV. no tienen competicion
(selectivos, pedido de Nico) -- no van a tener entrada aca nunca, no es que
falte cargarlas.
"""
from __future__ import annotations

FCF_IDS: dict[str, dict[str, str]] = {
    "13A": {"grup_id": "58162480", "team_id": "50600901"},
    "13B": {"grup_id": "58162533", "team_id": "50600909"},
    "14A": {"grup_id": "58162462", "team_id": "50600910"},
    "14B": {"grup_id": "58162522", "team_id": "50600900"},
    "15A": {"grup_id": "59348507", "team_id": "54316937"},
    "15B": {"grup_id": "59816210", "team_id": "54320031"},
    "16A": {"grup_id": "59318046", "team_id": "54316935"},
    "16B": {"grup_id": "59814075", "team_id": "54320026"},
    "1EQM": {"grup_id": "58161864", "team_id": "36170"},
    "1EQF": {"grup_id": "58162322", "team_id": "58968261"},
    "FILIAL": {"grup_id": "58161903", "team_id": "43172"},
    "JA": {"grup_id": "58161979", "team_id": "36171"},
    "JB": {"grup_id": "58161978", "team_id": "36172"},
    "JAF": {"grup_id": "58162347", "team_id": "58968264"},
    "CAF": {"grup_id": "59923507", "team_id": "58968301"},
    "CBF": {"grup_id": "59923239", "team_id": "58968331"},
    "IAF": {"grup_id": "58162379", "team_id": "58968352"},
}


def fcf_ids_de(categoria: str) -> dict[str, str] | None:
    return FCF_IDS.get(categoria.strip().upper())
