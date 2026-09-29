"""Parser de la planilla "GYM 26-27" (hoja "GYM"): el horario semanal real de
que categoria entrena en el gimnasio que dia, por microciclo. A diferencia del
historial (PLANIFICACION FUERZA), esta planilla es un calendario a futuro —
por eso categorias que un microciclo entrenan martes pueden pasar a jueves el
siguiente, y este parser respeta eso en vez de asumir un dia fijo.

Formato real (filas crudas de gspread, columnas A-L):
    MICROCICLO 5, HORARIO, LUNES, 14, MARTES, 15, MIERCOLES, 16, JUEVES, 17, VIERNES, 18
    (fila en blanco salvo columnas C,E,G,I,K = "ROTACION")
    , 18, 13A, , 14A, , CAF, , 13A, , 14B,
    (fila en blanco)
    , 19, 16A, , 15A, , JAF, , 15A, , 15B,
    ...

Las columnas de dia-del-mes (14,15,16...) no traen el mes: se resuelve
probando que mes/año hace que cada (nombre-de-dia, numero-de-dia) sea
consistente con el calendario real (ver `_resolve_week_dates`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls

WEEKDAY_NAMES = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"]
_CATEGORIA_COL = {0: 2, 1: 4, 2: 6, 3: 8, 4: 10}
_DAYNUM_COL = {0: 3, 1: 5, 2: 7, 3: 9, 4: 11}


@dataclass
class ScheduleEntry:
    microciclo: str
    fecha: date_cls
    horario: str
    categoria: str


def _resolve_week_dates(day_numbers: list[int], reference_date: date_cls) -> list[date_cls | None]:
    """Dados los 5 numeros de dia-del-mes (Lunes..Viernes) de un bloque,
    encuentra el año/mes real que los hace consistentes con sus nombres de
    dia de la semana. Maneja el caso en que la semana cruza de un mes a otro
    (el numero de dia deja de ser creciente).

    "Dia X es Lunes" por si solo es un dato debil (~1 de cada 7 meses lo
    cumple), asi que probamos un rango amplio de años/meses y nos quedamos
    con el resultado cuya fecha quede mas cerca de `reference_date` — la
    planilla siempre describe semanas cercanas a la fecha real de uso."""
    segments: list[list[int]] = [[0]]
    for k in range(1, 5):
        if day_numbers[k] > day_numbers[k - 1]:
            segments[-1].append(k)
        else:
            segments.append([k])

    best: list[date_cls | None] | None = None
    best_delta: int | None = None

    for candidate_year in (reference_date.year - 1, reference_date.year, reference_date.year + 1):
        for start_month in range(1, 13):
            year_cursor, month_cursor = candidate_year, start_month
            trial: list[date_cls | None] = [None] * 5
            ok = True
            for seg in segments:
                for k in seg:
                    try:
                        d = date_cls(year_cursor, month_cursor, day_numbers[k])
                    except ValueError:
                        ok = False
                        break
                    if d.weekday() != k:
                        ok = False
                        break
                    trial[k] = d
                if not ok:
                    break
                month_cursor += 1
                if month_cursor > 12:
                    month_cursor = 1
                    year_cursor += 1
            if ok:
                delta = abs((trial[0] - reference_date).days)  # type: ignore[operator]
                if best_delta is None or delta < best_delta:
                    best, best_delta = trial, delta

    return best if best is not None else [None] * 5


def _clean_row(row: list[str], min_len: int = 12) -> list[str]:
    row = list(row)
    if len(row) < min_len:
        row = row + [""] * (min_len - len(row))
    return row


def parse_gym_schedule(rows: list[list[str]], reference_date: date_cls) -> list[ScheduleEntry]:
    entries: list[ScheduleEntry] = []
    i = 0
    n = len(rows)
    while i < n:
        row0 = (rows[i][0] if rows[i] else "").strip()
        if not row0.upper().startswith("MICROCICLO"):
            i += 1
            continue

        microciclo = row0
        header = _clean_row(rows[i])
        day_numbers: list[int | None] = []
        for k in range(5):
            val = header[_DAYNUM_COL[k]].strip()
            day_numbers.append(int(val) if val.isdigit() else None)

        dates: list[date_cls | None] = [None] * 5
        if all(d is not None for d in day_numbers):
            dates = _resolve_week_dates(day_numbers, reference_date)  # type: ignore[arg-type]

        i += 1
        while i < n and not (rows[i][0] if rows[i] else "").strip().upper().startswith("MICROCICLO"):
            row_i = _clean_row(rows[i])
            horario = row_i[1].strip()
            if horario.isdigit():
                for k in range(5):
                    categoria = row_i[_CATEGORIA_COL[k]].strip()
                    if categoria and dates[k] is not None:
                        entries.append(
                            ScheduleEntry(microciclo=microciclo, fecha=dates[k], horario=horario, categoria=categoria)
                        )
            i += 1

    return entries


def categorias_de_hoy(entries: list[ScheduleEntry], hoy: date_cls) -> list[str]:
    vistas: list[str] = []
    for e in entries:
        if e.fecha == hoy and e.categoria not in vistas:
            vistas.append(e.categoria)
    return sorted(vistas)
