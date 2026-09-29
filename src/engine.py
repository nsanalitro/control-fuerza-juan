"""Motor de propuesta de sesion (reglas explicitas, sin LLM).

Por defecto, cada ejercicio se propone IGUAL al que se uso la ultima vez
para esa categoria/ejercicio/lado (A o B) -- ya no rota automaticamente para
dar variedad, porque eso rompia el seguimiento semana a semana que describe
esta funcion. La variedad la decide Juan a mano, editando el ejercicio en la
tabla; en cuanto lo hace, esa continuidad se corta (se trata como "primera
vez" la proxima vez).

Esquema de progresion (por cada ejercicio individual, troncal o auxiliar,
de forma independiente entre si):
- Se compara contra la ULTIMA sesion registrada para esa categoria+ejercicio.
- Si el dia de la semana de hoy no coincide con el de esa ultima sesion (la
  categoria cambio de dia), se trata como rutina nueva: mismo ejercicio y
  carga que la ultima vez, sin ajuste, con aviso de "primera vez".
- Si el dia coincide, se cuenta cuantas veces seguidas (mismo dia de semana,
  mismo ejercicio) se viene sosteniendo, para saber la "semana" del ciclo:
    * semana par (2, 4, 6...): +2 reps si es troncal, +1 si es auxiliar,
      mismo kilaje que la ultima vez.
    * semana impar >= 3 (3, 5, 7...): las repeticiones vuelven a la linea
      base de la semana 1 de esa racha, y sube el kilaje (+5%, redondeado a
      2.5kg) sobre el ultimo kilaje usado.
"""
from __future__ import annotations

import re
from datetime import date as date_cls
from datetime import datetime

from src.catalog import TRONCAL, classify_troncal_auxiliar, normalize_name
from src.models import (
    PRIMERA_VEZ,
    RESET_REPS_SUBE_KG,
    SUBE_REPS,
    ExerciseProposal,
    SessionProposal,
    SlotProposal,
)
from src.parser import SetSlot


def parse_fecha(fecha: str) -> date_cls | None:
    fecha = (fecha or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(fecha, fmt).date()
        except ValueError:
            continue
    return None


def _sort_key(slot: SetSlot):
    fecha = parse_fecha(slot.fecha)
    micro_match = re.search(r"(\d+)", slot.microciclo)
    micro_num = int(micro_match.group(1)) if micro_match else 0
    return (fecha or date_cls.min, micro_num)


_CARGA_KG_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*kg$", re.IGNORECASE)


def suggest_carga(ultima_carga: str) -> str:
    """+5% sobre la ultima carga, redondeado a 2.5kg, solo si es un peso
    claro en kg. Tiempos isometricos o "-" (peso corporal) se mantienen
    igual: no hay forma de inferir progresion ahi sin inventar datos."""
    c = (ultima_carga or "").strip()
    if not c:
        return "-"
    m = _CARGA_KG_RE.match(c)
    if not m:
        return c
    valor = float(m.group(1).replace(",", "."))
    sugerido = round((valor * 1.05) / 2.5) * 2.5
    if sugerido <= valor:
        sugerido = valor + 2.5
    return f"{sugerido:g}kg"


def _parse_reps(reps: str | None) -> int | None:
    reps = (reps or "").strip()
    return int(reps) if reps.isdigit() else None


def _compute_exercise_progression(
    registros_slot: list[SetSlot],
    posicion: str,
    hoy: date_cls,
) -> ExerciseProposal | None:
    def nombre_de(s: SetSlot) -> str | None:
        return s.ejercicio_a if posicion == "A" else s.ejercicio_b

    def carga_de(s: SetSlot) -> str | None:
        return s.carga_a if posicion == "A" else s.carga_b

    def reps_de(s: SetSlot) -> str | None:
        return s.reps_a if posicion == "A" else s.reps_b

    registros = sorted((s for s in registros_slot if nombre_de(s)), key=_sort_key, reverse=True)
    if not registros:
        return None

    ultimo = registros[0]
    ultimo_fecha = parse_fecha(ultimo.fecha)
    nombre = nombre_de(ultimo) or ""
    rol = classify_troncal_auxiliar(nombre) or ""
    ultima_carga = carga_de(ultimo) or "-"
    ultimas_reps = reps_de(ultimo) or ""

    dia_coincide = ultimo_fecha is not None and ultimo_fecha.weekday() == hoy.weekday()

    if not dia_coincide:
        return ExerciseProposal(
            posicion=posicion,
            nombre=nombre,
            rol=rol,
            carga=ultima_carga,
            reps=ultimas_reps,
            week_index=1,
            tipo_ajuste=PRIMERA_VEZ,
            reps_anterior=ultimas_reps,
            carga_anterior=ultima_carga,
        )

    streak = 1
    baseline_reps = ultimas_reps
    for rec in registros[1:]:
        rec_fecha = parse_fecha(rec.fecha)
        if nombre_de(rec) == nombre and rec_fecha is not None and rec_fecha.weekday() == hoy.weekday():
            streak += 1
            baseline_reps = reps_de(rec) or baseline_reps
        else:
            break

    week_index = streak + 1
    delta = 2 if rol == TRONCAL else 1

    if week_index % 2 == 0:
        reps_num = _parse_reps(ultimas_reps)
        nueva_reps = str(reps_num + delta) if reps_num is not None else ultimas_reps
        return ExerciseProposal(
            posicion, nombre, rol, ultima_carga, nueva_reps, week_index,
            SUBE_REPS, reps_anterior=ultimas_reps, carga_anterior=ultima_carga,
        )

    nueva_carga = suggest_carga(ultima_carga)
    return ExerciseProposal(
        posicion, nombre, rol, nueva_carga, baseline_reps, week_index,
        RESET_REPS_SUBE_KG, reps_anterior=ultimas_reps, carga_anterior=ultima_carga,
    )


def build_proposal(historial: list[SetSlot], categoria: str, hoy: date_cls | None = None) -> SessionProposal:
    hoy = hoy or date_cls.today()
    cat_norm = normalize_name(categoria)
    registros = [s for s in historial if normalize_name(s.categoria) == cat_norm]

    if not registros:
        return SessionProposal(
            categoria=categoria,
            perfil_sesion="",
            basado_en_sesiones=0,
            slots=[],
            advertencias=[
                f"No hay historial registrado todavía para la categoría '{categoria}'. "
                "Cargá al menos una sesión manualmente para que la app pueda empezar a proponer."
            ],
        )

    registros_ordenados = sorted(registros, key=_sort_key, reverse=True)

    sesiones_vistas: list[tuple[str, str, str]] = []
    for s in registros_ordenados:
        key = (s.microciclo, s.fecha, s.horario)
        if key not in sesiones_vistas:
            sesiones_vistas.append(key)

    perfil_propuesto = next((s.perfil_sesion for s in registros_ordenados if s.perfil_sesion), "")

    advertencias: list[str] = []
    slots_out: list[SlotProposal] = []

    for slot_num in (1, 2, 3, 4):
        registros_slot = [s for s in registros_ordenados if s.slot == slot_num]
        if not registros_slot:
            advertencias.append(f"Sin historial para el ejercicio {slot_num}; agregalo manualmente.")
            continue

        ex_a = _compute_exercise_progression(registros_slot, "A", hoy)
        ex_b = _compute_exercise_progression(registros_slot, "B", hoy)
        series = next((s.series for s in registros_slot if s.series), "")

        slots_out.append(SlotProposal(slot=slot_num, ejercicio_a=ex_a, ejercicio_b=ex_b, series=series))

    return SessionProposal(
        categoria=categoria,
        perfil_sesion=perfil_propuesto,
        basado_en_sesiones=len(sesiones_vistas),
        slots=slots_out,
        advertencias=advertencias,
    )
