import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine import build_proposal, suggest_carga  # noqa: E402
from src.parser import SetSlot  # noqa: E402


def make_slot(microciclo, fecha, categoria, perfil, slot, ea, ca, ra, eb, cb, rb, series):
    return SetSlot(
        microciclo=microciclo,
        fecha=fecha,
        categoria=categoria,
        horario="19:00",
        perfil_sesion=perfil,
        slot=slot,
        ejercicio_a=ea,
        carga_a=ca,
        reps_a=ra,
        ejercicio_b=eb,
        carga_b=cb,
        reps_b=rb,
        series=series,
    )


def test_suggest_carga_progresses_kg():
    sugerido, nota = suggest_carga("20kg")
    assert sugerido == "22.5kg"
    assert "progresion" in nota.lower() or "progresión" in nota.lower()


def test_suggest_carga_keeps_isometric_time():
    sugerido, nota = suggest_carga('20"')
    assert sugerido == '20"'
    assert "mantener" in nota.lower()


def test_suggest_carga_keeps_bodyweight_dash():
    sugerido, nota = suggest_carga("-")
    assert sugerido == "-"


def test_build_proposal_no_history_returns_warning():
    proposal = build_proposal([], "14A")
    assert proposal.basado_en_sesiones == 0
    assert proposal.slots == []
    assert proposal.advertencias


def test_build_proposal_rotates_least_recent_pairing():
    # 3 microciclos consecutivos para 14A, slot 1, con 2 parejas distintas que se
    # alternan: MICRO 10 (mas antiguo) usa pareja A, MICRO 11 usa pareja B,
    # MICRO 12 (mas reciente) vuelve a usar pareja A.
    # Con rotacion_n=3, deberia proponer la pareja usada hace mas tiempo dentro
    # de las ultimas 3 sesiones -> pareja B (usada en MICRO 11).
    historial = [
        make_slot("MICRO 10", "1/03/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "10", "PRESS BANCO", "20kg", "8", "5"),
        make_slot("MICRO 11", "8/03/2026", "14A", "T. INF.", 1, "SENTADILLA FRONTAL", "15kg", "10", "PRESS MILITAR", "10kg", "8", "5"),
        make_slot("MICRO 12", "15/03/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "22.5kg", "10", "PRESS BANCO", "22.5kg", "8", "5"),
    ]
    proposal = build_proposal(historial, "14A", perfiles_recientes_n=4, rotacion_n=3)
    assert proposal.perfil_sesion == "T. INF."
    slot1 = next(s for s in proposal.slots if s.slot == 1)
    assert slot1.ejercicio_a == "SENTADILLA FRONTAL"
    assert slot1.ejercicio_b == "PRESS MILITAR"


def test_build_proposal_single_pairing_history_reuses_it():
    historial = [
        make_slot("MICRO 10", "1/03/2026", "16B", "FULL BODY", 2, "PESO MUERTO RUMANO", "30kg", "8", "REMO A 1BB", "17.5kg", "8", "5"),
    ]
    proposal = build_proposal(historial, "16B")
    slot2 = next(s for s in proposal.slots if s.slot == 2)
    assert slot2.ejercicio_a == "PESO MUERTO RUMANO"
    assert slot2.carga_a_sugerida == "32.5kg"
    assert slot2.veces_en_historial == 1
