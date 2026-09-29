"""Conexion a Google Sheets: lectura del historial (hojas "MICRO N" de las
planillas de gimnasio) y lectura/escritura del registro propio de la app
(sesiones que Juan confirma como ejecutadas).

Usa una cuenta de servicio de Google (credenciales en st.secrets), asi la
app puede leer/escribir sin que Juan tenga que loguearse con su cuenta.
"""
from __future__ import annotations

from datetime import date, datetime

import gspread
import streamlit as st

from src.fcf import partidos_del_equipo
from src.parser import SetSlot, parse_sheet, should_skip_sheet
from src.schedule_parser import ScheduleEntry, parse_gym_schedule

REGISTRO_WORKSHEET_NAME = "registro_sesiones"
REGISTRO_HEADERS = [
    "fecha",
    "categoria",
    "horario",
    "perfil_sesion",
    "slot",
    "ejercicio_a",
    "carga_a",
    "reps_a",
    "ejercicio_b",
    "carga_b",
    "reps_b",
    "series",
    "registrado_en",
]


@st.cache_resource(show_spinner=False)
def get_client() -> gspread.Client:
    creds_dict = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(creds_dict)


def _dev_fixture_path() -> str | None:
    try:
        return st.secrets["dev"]["local_fixture_path"]
    except Exception:
        return None


def _load_dev_fixture(path: str) -> list[SetSlot]:
    text = open(path, encoding="utf-8").read()
    rows = [line.split(",") for line in text.splitlines() if line.strip()]
    return parse_sheet("MICRO DEV", rows)


@st.cache_data(ttl=600, show_spinner=False)
def load_historial_fuente(spreadsheet_ids: tuple[str, ...]) -> list[SetSlot]:
    """Lee y parsea todas las hojas "MICRO N" de las planillas de gimnasio
    indicadas (las hojas de catalogo/plantilla se ignoran automaticamente)."""
    fixture = _dev_fixture_path()
    if fixture:
        return _load_dev_fixture(fixture)
    client = get_client()
    registros: list[SetSlot] = []
    for spreadsheet_id in spreadsheet_ids:
        sh = client.open_by_key(spreadsheet_id)
        for ws in sh.worksheets():
            if should_skip_sheet(ws.title):
                continue
            rows = ws.get_all_values()
            registros.extend(parse_sheet(ws.title, rows))
    return registros


@st.cache_data(ttl=600, show_spinner=False)
def load_gym_schedule(spreadsheet_id: str, sheet_name: str, reference_date: date) -> list[ScheduleEntry]:
    """Lee la planilla de horarios (que categoria entrena gym que dia, por
    microciclo) y la devuelve como lista de ScheduleEntry con fechas reales
    ya resueltas."""
    client = get_client()
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name)
    rows = ws.get_all_values()
    return parse_gym_schedule(rows, reference_date=reference_date)


@st.cache_data(ttl=3600, show_spinner=False)
def load_partidos_fcf(grup_id: str, team_id: str) -> list[dict]:
    """Partidos de la temporada del equipo en fcf.cat. Lista vacia si la FCF
    no responde -- no bloquea el resto de la app."""
    return partidos_del_equipo(grup_id, team_id)


def _ensure_registro_worksheet(spreadsheet_id: str) -> gspread.Worksheet:
    client = get_client()
    sh = client.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(REGISTRO_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=REGISTRO_WORKSHEET_NAME, rows=1000, cols=len(REGISTRO_HEADERS))
        ws.append_row(REGISTRO_HEADERS)
    return ws


_DEV_REGISTRO: list[dict] = []


@st.cache_data(ttl=120, show_spinner=False)
def load_historial_registro(spreadsheet_id: str) -> list[SetSlot]:
    """Lee las sesiones que la propia app ya guardo, para que entren en la
    rotacion de las proximas propuestas."""
    if _dev_fixture_path():
        return [
            SetSlot(
                microciclo="APP",
                fecha=str(row.get("fecha", "")),
                categoria=str(row.get("categoria", "")),
                horario=str(row.get("horario", "")),
                perfil_sesion=str(row.get("perfil_sesion", "")),
                slot=int(row.get("slot") or 0),
                ejercicio_a=row.get("ejercicio_a") or None,
                carga_a=row.get("carga_a") or None,
                reps_a=row.get("reps_a") or None,
                ejercicio_b=row.get("ejercicio_b") or None,
                carga_b=row.get("carga_b") or None,
                reps_b=row.get("reps_b") or None,
                series=row.get("series") or None,
            )
            for row in _DEV_REGISTRO
        ]
    client = get_client()
    try:
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet(REGISTRO_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        return []
    rows = ws.get_all_records()
    registros = []
    for row in rows:
        registros.append(
            SetSlot(
                microciclo="APP",
                fecha=str(row.get("fecha", "")),
                categoria=str(row.get("categoria", "")),
                horario=str(row.get("horario", "")),
                perfil_sesion=str(row.get("perfil_sesion", "")),
                slot=int(row.get("slot") or 0),
                ejercicio_a=str(row.get("ejercicio_a") or "") or None,
                carga_a=str(row.get("carga_a") or "") or None,
                reps_a=str(row.get("reps_a") or "") or None,
                ejercicio_b=str(row.get("ejercicio_b") or "") or None,
                carga_b=str(row.get("carga_b") or "") or None,
                reps_b=str(row.get("reps_b") or "") or None,
                series=str(row.get("series") or "") or None,
            )
        )
    return registros


def append_sesion(spreadsheet_id: str, fecha: str, categoria: str, perfil_sesion: str, horario: str, filas: list[dict]) -> None:
    """Guarda una sesion confirmada por Juan (una fila por ejercicio/slot)."""
    if _dev_fixture_path():
        for f in filas:
            _DEV_REGISTRO.append({"fecha": fecha, "categoria": categoria, "perfil_sesion": perfil_sesion, "horario": horario, **f})
        load_historial_registro.clear()
        return
    ws = _ensure_registro_worksheet(spreadsheet_id)
    timestamp = datetime.now().isoformat(timespec="seconds")
    rows_to_add = []
    for f in filas:
        rows_to_add.append(
            [
                fecha,
                categoria,
                horario,
                perfil_sesion,
                f.get("slot", ""),
                f.get("ejercicio_a", ""),
                f.get("carga_a", ""),
                f.get("reps_a", ""),
                f.get("ejercicio_b", ""),
                f.get("carga_b", ""),
                f.get("reps_b", ""),
                f.get("series", ""),
                timestamp,
            ]
        )
    ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
    load_historial_registro.clear()
