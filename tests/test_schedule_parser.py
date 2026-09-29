import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

from gym_schedule_sample import GYM_SCHEDULE_ROWS  # noqa: E402

from src.schedule_parser import categorias_de_hoy, parse_gym_schedule  # noqa: E402


def test_parse_gym_schedule_resolves_real_calendar_dates():
    entries = parse_gym_schedule(GYM_SCHEDULE_ROWS, reference_date=date(2026, 9, 29))
    fechas = {e.fecha for e in entries}
    assert date(2026, 9, 14) in fechas  # Lunes microciclo 5
    assert date(2026, 9, 29) in fechas  # Martes microciclo 7
    assert date(2026, 10, 1) not in fechas  # Jueves microciclo 7 esta vacio en la muestra
    assert date(2026, 10, 2) in fechas  # Viernes microciclo 7 (cruce de mes)


def test_categorias_de_hoy_matches_real_schedule():
    entries = parse_gym_schedule(GYM_SCHEDULE_ROWS, reference_date=date(2026, 9, 29))
    assert categorias_de_hoy(entries, date(2026, 9, 29)) == [("14A", "18"), ("15A", "19")]
    assert categorias_de_hoy(entries, date(2026, 10, 1)) == []


def test_categorias_de_hoy_respeta_orden_de_turno_no_alfabetico():
    # Miercoles del microciclo 5 (16/09): CAF a las 18, JAF a las 19, 1EQF a
    # las 20 -- el orden alfabetico daria 1EQF, CAF, JAF, que es incorrecto.
    entries = parse_gym_schedule(GYM_SCHEDULE_ROWS, reference_date=date(2026, 9, 29))
    assert categorias_de_hoy(entries, date(2026, 9, 16)) == [("CAF", "18"), ("JAF", "19"), ("1EQF", "20")]


def test_categorias_de_hoy_same_categoria_different_weekday_across_microciclos():
    # 13A entrena lunes en el microciclo 5, pero martes en el microciclo 6 y
    # miercoles en el microciclo 7 -- el parser tiene que reflejar eso, no un
    # dia fijo por categoria.
    entries = parse_gym_schedule(GYM_SCHEDULE_ROWS, reference_date=date(2026, 9, 29))
    cat_13a_fechas = sorted(e.fecha for e in entries if e.categoria == "13A")
    assert date(2026, 9, 14) in cat_13a_fechas  # microciclo 5, lunes
    assert date(2026, 9, 22) in cat_13a_fechas  # microciclo 6, martes
