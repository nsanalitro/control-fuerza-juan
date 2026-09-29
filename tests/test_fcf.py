import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fcf import partido_por_fecha, proximo_partido  # noqa: E402


def make_partido(fecha_str, rival="RIVAL"):
    return {"fecha": datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S"), "rival": rival, "local": True, "campo": "Campo 1", "jornada": "1"}


def test_proximo_partido_elige_el_mas_cercano_en_el_futuro():
    partidos = [
        make_partido("2026-03-01 10:00:00", "A"),
        make_partido("2026-03-15 10:00:00", "B"),
        make_partido("2026-03-08 10:00:00", "C"),
    ]
    ahora = datetime(2026, 3, 5)
    p = proximo_partido(partidos, ahora)
    assert p["rival"] == "C"


def test_proximo_partido_ninguno_si_todos_pasaron():
    partidos = [make_partido("2026-01-01 10:00:00")]
    assert proximo_partido(partidos, datetime(2026, 3, 5)) is None


def test_partido_por_fecha_encuentra_el_del_dia():
    partidos = [make_partido("2026-03-08 10:00:00", "C")]
    p = partido_por_fecha(partidos, datetime(2026, 3, 8).date())
    assert p is not None
    assert p["rival"] == "C"
    assert partido_por_fecha(partidos, datetime(2026, 3, 9).date()) is None
