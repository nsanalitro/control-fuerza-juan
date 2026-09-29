import sys
from datetime import date
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
    assert suggest_carga("20kg") == "22.5kg"


def test_suggest_carga_keeps_isometric_time():
    assert suggest_carga('20"') == '20"'


def test_suggest_carga_keeps_bodyweight_dash():
    assert suggest_carga("-") == "-"


def test_build_proposal_no_history_returns_warning():
    proposal = build_proposal([], "14A", hoy=date(2026, 3, 24))
    assert proposal.basado_en_sesiones == 0
    assert proposal.slots == []
    assert proposal.advertencias


def test_primera_vez_cuando_no_hay_historial_previo():
    # Martes 3/3, unica sesion registrada. Si hoy tambien es martes pero es
    # la unica sesion previa, la propuesta es "semana 2" (ya hubo 1 antes).
    # Si en cambio el dia no coincide, tiene que marcar "primera vez".
    historial = [
        make_slot("MICRO 10", "3/03/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "10", "PRESS BANCO", "20kg", "8", "5"),
    ]
    # 3/03/2026 es martes; probamos con un miercoles (dia distinto)
    proposal = build_proposal(historial, "14A", hoy=date(2026, 3, 11))
    slot1 = next(s for s in proposal.slots if s.slot == 1)
    assert slot1.ejercicio_a.week_index == 1
    assert "primera vez" in slot1.ejercicio_a.banner.lower()
    assert slot1.ejercicio_a.nombre == "SENTADILLA TRASERA"
    assert slot1.ejercicio_a.carga == "20kg"  # sin ajuste


def test_semana_2_aumenta_reps_troncal_y_auxiliar_distinto():
    # Unica sesion previa, martes. Hoy tambien martes -> continuidad, semana 2.
    historial = [
        make_slot("MICRO 10", "3/03/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "10", "TWIST RUSO", "5kg", "12", "5"),
    ]
    hoy = date(2026, 3, 10)  # martes siguiente
    proposal = build_proposal(historial, "14A", hoy=hoy)
    slot1 = next(s for s in proposal.slots if s.slot == 1)

    assert slot1.ejercicio_a.rol == "troncal"
    assert slot1.ejercicio_a.week_index == 2
    assert slot1.ejercicio_a.reps == "12"  # 10 + 2
    assert slot1.ejercicio_a.carga == "20kg"  # sin cambio de kilaje

    assert slot1.ejercicio_b.rol == "auxiliar"
    assert slot1.ejercicio_b.week_index == 2
    assert slot1.ejercicio_b.reps == "13"  # 12 + 1
    assert slot1.ejercicio_b.carga == "5kg"


def test_semana_3_resetea_reps_y_sube_kilaje():
    historial = [
        make_slot("MICRO 8", "17/02/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "10", "TWIST RUSO", "5kg", "12", "5"),
        make_slot("MICRO 9", "24/02/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "12", "TWIST RUSO", "5kg", "13", "5"),
    ]
    hoy = date(2026, 3, 3)  # martes siguiente (3ra semana seguida)
    proposal = build_proposal(historial, "14A", hoy=hoy)
    slot1 = next(s for s in proposal.slots if s.slot == 1)

    assert slot1.ejercicio_a.week_index == 3
    assert slot1.ejercicio_a.reps == "10"  # vuelve a la linea base (semana 1)
    assert slot1.ejercicio_a.carga == "22.5kg"  # sube de 20kg


def test_semana_3_sin_carga_no_dice_sube_el_kilaje():
    historial = [
        make_slot("MICRO 8", "17/02/2026", "14A", "T. INF.", 4, "SALTOS AL CAJÓN", "-", "8", "DEAD BUG", "-", "15", "5"),
        make_slot("MICRO 9", "24/02/2026", "14A", "T. INF.", 4, "SALTOS AL CAJÓN", "-", "10", "DEAD BUG", "-", "16", "5"),
    ]
    hoy = date(2026, 3, 3)
    proposal = build_proposal(historial, "14A", hoy=hoy)
    slot4 = next(s for s in proposal.slots if s.slot == 4)
    assert slot4.ejercicio_a.week_index == 3
    assert slot4.ejercicio_a.carga == "-"
    assert "sube el kilaje" not in slot4.ejercicio_a.banner.lower()


def test_dia_distinto_rompe_continuidad_aunque_el_ejercicio_sea_el_mismo():
    # 14A entreno martes en microciclo 5, pero jueves en microciclo 6 con el
    # mismo ejercicio -- no deberia contar como semana 2.
    historial = [
        make_slot("MICRO 5", "3/03/2026", "14A", "T. INF.", 2, "PESO MUERTO RUMANO", "30kg", "8", "REMO A 1BB", "15kg", "8", "5"),
    ]
    hoy_jueves = date(2026, 3, 12)  # jueves
    proposal = build_proposal(historial, "14A", hoy=hoy_jueves)
    slot2 = next(s for s in proposal.slots if s.slot == 2)
    assert slot2.ejercicio_a.week_index == 1
    assert "primera vez" in slot2.ejercicio_a.banner.lower()
    assert slot2.ejercicio_a.carga == "30kg"  # se mantiene, sin bump


def test_continuidad_se_corta_si_cambia_el_ejercicio_en_medio():
    # semana1: SENTADILLA (martes). semana2: PRESS MILITAR (martes, cambio
    # de ejercicio -- juan lo edito). semana3 (hoy, martes): como el ultimo
    # registrado es PRESS MILITAR con una sola aparicion, es semana 2 de esa
    # rutina nueva, no semana 3 de sentadilla.
    historial = [
        make_slot("MICRO 8", "17/02/2026", "14A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "10", "-", "-", "-", "5"),
        make_slot("MICRO 9", "24/02/2026", "14A", "T. INF.", 1, "PRESS MILITAR", "15kg", "8", "-", "-", "-", "5"),
    ]
    hoy = date(2026, 3, 3)
    proposal = build_proposal(historial, "14A", hoy=hoy)
    slot1 = next(s for s in proposal.slots if s.slot == 1)
    assert slot1.ejercicio_a.nombre == "PRESS MILITAR"
    assert slot1.ejercicio_a.week_index == 2
    assert slot1.ejercicio_a.reps == "10"  # 8 + 2 (troncal)
