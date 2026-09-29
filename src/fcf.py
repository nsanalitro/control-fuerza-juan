"""Partidos desde la API (no documentada) de la Federacio Catalana de Futbol.

Mismo enfoque que en AFA_Control_Carga_App/core/fcf.py (proyecto hermano de
Nico, ya verificado en vivo contra fcf.cat): /api/competition/partidos
devuelve todos los partidos de la temporada agrupados por jornada; se filtran
los que juega nuestro equipo (fcf_config.py: team_id) por
CODEQUIPO_CASA/CODEQUIPO_FUERA, que es estable (a diferencia del nombre, que
cambia de formato).

Es una API interna de la web, no publica ni documentada por la FCF - puede
cambiar de forma sin aviso. Por eso cualquier fallo se atrapa y se devuelve
una lista vacia en vez de romper la pantalla.
"""
from __future__ import annotations

from datetime import date, datetime

import requests

URL_PARTIDOS = "https://www.fcf.cat/api/competition/partidos"
TIMEOUT_SEG = 10


def _fecha_partido(texto: str) -> datetime | None:
    try:
        return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _normalizar(p: dict) -> dict | None:
    fecha = _fecha_partido(p.get("COMIENZO1"))
    if fecha is None:
        return None
    es_local = str(p.get("CODEQUIPO_CASA")) == str(p.get("_team_id"))
    rival = p.get("NOMBRE_FUERA") if es_local else p.get("NOMBRE_CASA")
    return {
        "jornada": p.get("JORNADA", ""),
        "fecha": fecha,
        "local": es_local,
        "rival": (rival or "").strip(),
        "campo": (p.get("CAMPO") or "").strip(),
        "goles_favor": p.get("GOLES_CASA") if es_local else p.get("GOLES_FUERA"),
        "goles_contra": p.get("GOLES_FUERA") if es_local else p.get("GOLES_CASA"),
    }


def partidos_del_equipo(grup_id: str, team_id: str) -> list[dict]:
    """Todos los partidos de la temporada de nuestro equipo, ordenados por fecha.

    Lista vacia si la FCF no responde o cambio el formato -- nunca lanza.
    """
    try:
        respuesta = requests.get(URL_PARTIDOS, params={"grupId": grup_id}, timeout=TIMEOUT_SEG)
        respuesta.raise_for_status()
        jornadas = respuesta.json()
    except (requests.RequestException, ValueError):
        return []

    partidos = []
    for lista in jornadas.values():
        if not isinstance(lista, list):
            continue
        for p in lista:
            if str(p.get("CODEQUIPO_CASA")) != str(team_id) and str(p.get("CODEQUIPO_FUERA")) != str(team_id):
                continue
            p = {**p, "_team_id": team_id}
            normalizado = _normalizar(p)
            if normalizado:
                partidos.append(normalizado)
    return sorted(partidos, key=lambda p: p["fecha"])


def partido_por_fecha(partidos: list[dict], fecha: date) -> dict | None:
    """El partido de nuestro equipo en esa fecha exacta, si lo hay."""
    for p in partidos:
        if p["fecha"].date() == fecha:
            return p
    return None


def proximo_partido(partidos: list[dict], ahora: datetime) -> dict | None:
    futuros = [p for p in partidos if p["fecha"] >= ahora]
    return min(futuros, key=lambda p: p["fecha"]) if futuros else None
