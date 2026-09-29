import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parser import parse_sheet, should_skip_sheet  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "micro40_sample.txt"


def load_rows() -> list[list[str]]:
    text = FIXTURE.read_text(encoding="utf-8")
    return [line.split(",") for line in text.splitlines() if line.strip()]


def test_should_skip_sheet():
    assert should_skip_sheet("EJERCICIOS")
    assert should_skip_sheet("EN BLANCO PARA COPIAR")
    assert should_skip_sheet("Copia de EN BLANCO PARA COPIAR")
    assert not should_skip_sheet("MICRO 40")


def test_parse_sheet_extracts_all_sessions():
    rows = load_rows()
    slots = parse_sheet("MICRO 40", rows)

    categorias = {s.categoria for s in slots}
    assert categorias == {"14B", "15B", "1EQM", "14A"}

    # 4 categorias x 4 slots usados (el slot 5 siempre vacio) = 16
    assert len(slots) == 16


def test_parse_sheet_first_slot_values():
    rows = load_rows()
    slots = parse_sheet("MICRO 40", rows)

    s = next(s for s in slots if s.categoria == "14B" and s.slot == 1)
    assert s.fecha == "1/06/2026"
    assert s.horario == "18:00/15"
    assert s.perfil_sesion == "T. INF."
    assert s.ejercicio_a == "SENTADILLA TRASERA"
    assert s.carga_a == "35kg"
    assert s.ejercicio_b == "PRESS A 1BB"
    assert s.carga_b == "10kg"
    assert s.reps_a == "12"
    assert s.reps_b == "8"
    assert s.series == "5"


def test_parse_sheet_handles_activacion_a2_prefix():
    rows = load_rows()
    slots = parse_sheet("MICRO 40", rows)

    s = next(s for s in slots if s.categoria == "14B" and s.slot == 3)
    assert s.ejercicio_a == "ALCANCE LATERAL"
    assert s.ejercicio_b == "FLEXIONES CON DISCO"
    assert s.carga_b == "-"


def test_parse_sheet_slot_5_is_never_emitted_when_empty():
    rows = load_rows()
    slots = parse_sheet("MICRO 40", rows)
    assert all(s.slot != 5 for s in slots)


def test_parse_sheet_isometric_and_time_loads():
    rows = load_rows()
    slots = parse_sheet("MICRO 40", rows)

    s = next(s for s in slots if s.categoria == "15B" and s.slot == 1)
    assert s.ejercicio_a == 'SENTADILLA ISOMÉTRICA'
    assert s.carga_a == '20"'
