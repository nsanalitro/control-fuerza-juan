import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine import build_proposal, compute_progression_for_exercise, suggest_carga  # noqa: E402
from src.models import PRIMERA_VEZ, RESET_REPS_SUBE_KG, SUBE_REPS  # noqa: E402
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
    assert slot1.ejercicio_a.tipo_ajuste == PRIMERA_VEZ
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
    assert slot1.ejercicio_a.tipo_ajuste == SUBE_REPS
    assert slot1.ejercicio_a.reps == "12"  # 10 + 2
    assert slot1.ejercicio_a.reps_anterior == "10"
    assert slot1.ejercicio_a.carga == "20kg"  # sin cambio de kilaje

    assert slot1.ejercicio_b.rol == "auxiliar"
    assert slot1.ejercicio_b.week_index == 2
    assert slot1.ejercicio_b.tipo_ajuste == SUBE_REPS
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
    assert slot4.ejercicio_a.tipo_ajuste == RESET_REPS_SUBE_KG
    assert slot4.ejercicio_a.carga == "-"
    assert slot4.ejercicio_a.carga_anterior == "-"  # sin cambio real: nada que progresar


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
    assert slot2.ejercicio_a.tipo_ajuste == PRIMERA_VEZ
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


def test_ejercicio_editado_a_uno_nunca_hecho_no_hereda_carga_del_anterior():
    # Caso real reportado: 15A viene con SENTADILLA TRASERA progresando a
    # 25kg. Juan la cambia a mano por SENTADILLA UNIPODAL, que nunca se hizo
    # para esta categoria -- no puede heredar los 25kg (unilateral, mas
    # exigente), tiene que arrancar sin carga de referencia.
    historial = [
        make_slot("MICRO 8", "17/02/2026", "15A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "10", "-", "-", "-", "5"),
        make_slot("MICRO 9", "24/02/2026", "15A", "T. INF.", 1, "SENTADILLA TRASERA", "20kg", "12", "-", "-", "-", "5"),
    ]
    hoy = date(2026, 3, 3)
    ep = compute_progression_for_exercise(historial, "SENTADILLA UNIPODAL", hoy, posicion="A")
    assert ep.tipo_ajuste == PRIMERA_VEZ
    assert ep.carga == "-"
    assert ep.reps == ""
    assert ep.ultima_vez == ""  # nunca se hizo, no solo "distinto dia"


def test_ejercicio_editado_a_uno_ya_hecho_antes_muestra_cuando_fue():
    historial = [
        make_slot("MICRO 3", "10/02/2026", "15A", "T. INF.", 3, "SENTADILLA UNIPODAL", "12.5kg", "8", "-", "-", "-", "5"),
    ]
    hoy = date(2026, 3, 3)  # mismo dia de semana (martes) que 10/02/2026, pero no consecutivo
    ep = compute_progression_for_exercise(historial, "SENTADILLA UNIPODAL", hoy, posicion="A")
    assert ep.tipo_ajuste == PRIMERA_VEZ
    assert ep.ultima_vez == "10/02/2026"
    assert ep.carga == "12.5kg"
    assert ep.reps == "8"


def test_progresion_sigue_al_ejercicio_aunque_cambie_de_slot():
    # PRESS MILITAR estuvo en el slot 1 la primera semana y en el slot 3 la
    # segunda (p.ej. Juan reordeno la sesion) -- la progresion tiene que
    # seguir contando semana 3, no resetear por el cambio de slot.
    historial = [
        make_slot("MICRO 8", "17/02/2026", "14A", "T. INF.", 1, "PRESS MILITAR", "15kg", "8", "-", "-", "-", "5"),
        make_slot("MICRO 9", "24/02/2026", "14A", "T. INF.", 3, "-", "-", "-", "PRESS MILITAR", "15kg", "10", "5"),
    ]
    hoy = date(2026, 3, 3)
    ep = compute_progression_for_exercise(historial, "PRESS MILITAR", hoy, posicion="A")
    assert ep.week_index == 3
    assert ep.tipo_ajuste == RESET_REPS_SUBE_KG
    assert ep.reps == "8"  # vuelve a la base
    assert ep.carga == "17.5kg"  # sube desde 15kg


def test_categoria_nueva_temporada_usa_historial_de_la_anterior():
    # Caso real: 16A esta temporada es la misma cohorte que 15A la temporada
    # pasada. Si 16A todavia no tiene historial propio, la propuesta tiene
    # que apoyarse en el de 15A, y avisar de donde sale el dato.
    historial = [
        make_slot("MICRO 40", "22/06/2026", "15A", "FULL BODY", 1, "SENTADILLA TRASERA", "25kg", "12", "SALTABILIDAD VERTICAL", "-", "12", "5"),
    ]
    proposal = build_proposal(historial, "16A", hoy=date(2026, 9, 29))
    assert proposal.basado_en_sesiones == 1
    slot1 = next(s for s in proposal.slots if s.slot == 1)
    assert slot1.ejercicio_a.nombre == "SENTADILLA TRASERA"
    assert slot1.ejercicio_a.tipo_ajuste == PRIMERA_VEZ
    assert slot1.ejercicio_a.carga == "25kg"
    assert slot1.ejercicio_a.categoria_origen == "15A"


def test_categoria_sin_mapeo_no_mezcla_con_otras():
    # 1EQM no tiene equivalente de temporada anterior: no debe traer nada de
    # otra categoria aunque el nombre se parezca.
    historial = [
        make_slot("MICRO 8", "17/02/2026", "1EQF", "FULL BODY", 1, "SENTADILLA TRASERA", "40kg", "8", "-", "-", "-", "5"),
    ]
    proposal = build_proposal(historial, "1EQM", hoy=date(2026, 3, 3))
    assert proposal.basado_en_sesiones == 0
    assert proposal.slots == []
    assert proposal.advertencias
