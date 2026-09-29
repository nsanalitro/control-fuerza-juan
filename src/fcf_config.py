"""Mapeo categoria -> (grup_id, team_id) de la Federacio Catalana de Futbol,
para mostrar el proximo partido de cada equipo.

grup_id/team_id se sacan a mano de fcf.cat (ver core/fcf.py de
AFA_Control_Carga_App para el detalle de como se verificaron). Las
categorias que todavia no tienen datos cargados aca simplemente no muestran
el cartel de "proximo partido" -- no rompen nada.

Reutiliza los IDs ya verificados en AFA_Control_Carga_App/config/categorias.py
(13A, 14A, 14B, 15A). Faltan cargar el resto de las categorias que van al
gimnasio (13B, 16A, 16B, JA, JB, JAF, JBF, CAF, CBF, 1EQM, 1EQF, FILIAL,
SEL. INF, SEL. CAD., SEL. JUV.) -- pedirselas a Nico.
"""
from __future__ import annotations

FCF_IDS: dict[str, dict[str, str]] = {
    "13A": {"grup_id": "58162480", "team_id": "50600901"},
    "14A": {"grup_id": "58162462", "team_id": "50600910"},
    "14B": {"grup_id": "58162522", "team_id": "50600900"},
    "15A": {"grup_id": "59348507", "team_id": "54316937"},
}


def fcf_ids_de(categoria: str) -> dict[str, str] | None:
    return FCF_IDS.get(categoria.strip().upper())
