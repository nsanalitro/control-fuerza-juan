"""Motor de propuesta de sesion (reglas explicitas, sin LLM).

Por defecto, cada ejercicio se propone IGUAL al que se uso la ultima vez en
ese lugar de la sesion (slot + A o B) -- ya no rota automaticamente para dar
variedad, porque eso rompia el seguimiento semana a semana que describe esta
funcion. La variedad la decide Juan a mano, editando el ejercicio en la
tabla.

El seguimiento de progresion es por IDENTIDAD del ejercicio (nombre), no por
la posicion donde aparece: si Juan cambia "SENTADILLA TRASERA" por
"SENTADILLA UNIPODAL", la app busca el historial propio de "SENTADILLA
UNIPODAL" para esa categoria (en cualquier slot donde haya aparecido antes),
no arrastra la carga/semana del ejercicio que reemplazo. Si nunca se hizo,
no hay carga de referencia -- no se inventa un punto de partida.

Esquema de progresion (por cada ejercicio, troncal o auxiliar, de forma
independiente entre si):
- Se compara contra la ULTIMA vez que se registro ESE ejercicio para esa
  categoria (en cualquier slot).
- Si nunca se registro antes, o si el dia de la semana de hoy no coincide
  con el de esa ultima vez, se trata como rutina nueva: mismo dato que la
  ultima vez (o sin carga si nunca se hizo), sin ajuste, con aviso de
  "primera vez" que incluye cuando fue la ultima vez (si la hubo).
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
from src.season_mapping import categorias_anteriores_de


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

# Cuanto margen se tolera entre dos apariciones del mismo ejercicio (mismo
# dia de semana) para contarlas como semanas consecutivas de la misma racha.
# Un poco mas de 7 dias para tolerar que la categoria se corra un dia o dos
# de una semana a la otra; si el hueco es mayor, no es "la semana pasada",
# es un ejercicio retomado despues de un tiempo -> se trata como primera vez.
MAX_DIAS_CONTINUIDAD = 10


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


def _ultimo_ejercicio_de_slot(registros_slot: list[SetSlot], posicion: str) -> str | None:
    """Que ejercicio ocupaba este slot+posicion la ultima vez -- solo para
    decidir que proponer HOY por defecto. La progresion en si se calcula
    aparte, siguiendo al ejercicio (ver compute_progression_for_exercise)."""

    def nombre_de(s: SetSlot) -> str | None:
        return s.ejercicio_a if posicion == "A" else s.ejercicio_b

    registros = sorted((s for s in registros_slot if nombre_de(s)), key=_sort_key, reverse=True)
    return nombre_de(registros[0]) if registros else None


def compute_progression_for_exercise(
    historial_pool: list[SetSlot],
    nombre: str | None,
    hoy: date_cls,
    categoria_actual: str = "",
    posicion: str = "",
) -> ExerciseProposal | None:
    """Progresion de UN ejercicio para esta categoria, buscando su historial
    en cualquier slot/posicion donde haya aparecido (no solo donde esta hoy).

    `historial_pool` puede incluir registros de categorias equivalentes de
    temporadas anteriores (ver season_mapping.py) ademas de la categoria
    actual -- por eso se recibe `categoria_actual`: sirve para detectar
    cuando el dato mas reciente en realidad viene de otra categoria, y
    dejarlo marcado en `categoria_origen` para que quede claro en el cartel."""
    nombre = (nombre or "").strip()
    if not nombre:
        return None

    rol = classify_troncal_auxiliar(nombre) or ""
    nombre_norm = normalize_name(nombre)
    cat_actual_norm = normalize_name(categoria_actual)

    instancias: list[tuple[SetSlot, str, str]] = []
    for s in historial_pool:
        if s.ejercicio_a and normalize_name(s.ejercicio_a) == nombre_norm:
            instancias.append((s, s.carga_a or "-", s.reps_a or ""))
        if s.ejercicio_b and normalize_name(s.ejercicio_b) == nombre_norm:
            instancias.append((s, s.carga_b or "-", s.reps_b or ""))

    if not instancias:
        return ExerciseProposal(
            posicion=posicion, nombre=nombre, rol=rol, carga="-", reps="", week_index=1,
            tipo_ajuste=PRIMERA_VEZ, reps_anterior="", carga_anterior="", ultima_vez="",
        )

    instancias.sort(key=lambda t: _sort_key(t[0]), reverse=True)
    ultimo_registro, ultima_carga, ultimas_reps = instancias[0]
    ultima_fecha = parse_fecha(ultimo_registro.fecha)
    ultima_vez = ultimo_registro.fecha
    categoria_origen = (
        "" if normalize_name(ultimo_registro.categoria) == cat_actual_norm else ultimo_registro.categoria
    )

    dia_coincide = (
        ultima_fecha is not None
        and ultima_fecha.weekday() == hoy.weekday()
        and 0 <= (hoy - ultima_fecha).days <= MAX_DIAS_CONTINUIDAD
    )

    if not dia_coincide:
        return ExerciseProposal(
            posicion=posicion, nombre=nombre, rol=rol, carga=ultima_carga, reps=ultimas_reps, week_index=1,
            tipo_ajuste=PRIMERA_VEZ, reps_anterior=ultimas_reps, carga_anterior=ultima_carga,
            ultima_vez=ultima_vez, categoria_origen=categoria_origen,
        )

    streak = 1
    baseline_reps = ultimas_reps
    fecha_referencia = ultima_fecha
    for reg, _carga, reps in instancias[1:]:
        fecha = parse_fecha(reg.fecha)
        if (
            fecha is not None
            and fecha.weekday() == hoy.weekday()
            and 0 <= (fecha_referencia - fecha).days <= MAX_DIAS_CONTINUIDAD
        ):
            streak += 1
            baseline_reps = reps or baseline_reps
            fecha_referencia = fecha
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
            ultima_vez=ultima_vez, categoria_origen=categoria_origen,
        )

    nueva_carga = suggest_carga(ultima_carga)
    return ExerciseProposal(
        posicion, nombre, rol, nueva_carga, baseline_reps, week_index,
        RESET_REPS_SUBE_KG, reps_anterior=ultimas_reps, carga_anterior=ultima_carga,
        ultima_vez=ultima_vez, categoria_origen=categoria_origen,
    )


def build_proposal(historial: list[SetSlot], categoria: str, hoy: date_cls | None = None) -> SessionProposal:
    hoy = hoy or date_cls.today()
    cat_norm = normalize_name(categoria)
    # La categoria de este año puede ser la misma cohorte de jugadores que
    # entrenaba el año pasado con otro nombre (ver season_mapping.py) -- se
    # pool-ea su historial para no arrancar de cero apenas cambia la
    # temporada. compute_progression_for_exercise se encarga de aclarar
    # cuando un dato viene de la categoria anterior.
    categorias_pool = {cat_norm} | {normalize_name(c) for c in categorias_anteriores_de(categoria)}
    registros = [s for s in historial if normalize_name(s.categoria) in categorias_pool]

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

        nombre_a = _ultimo_ejercicio_de_slot(registros_slot, "A")
        nombre_b = _ultimo_ejercicio_de_slot(registros_slot, "B")
        ex_a = compute_progression_for_exercise(registros_ordenados, nombre_a, hoy, categoria_actual=categoria, posicion="A")
        ex_b = compute_progression_for_exercise(registros_ordenados, nombre_b, hoy, categoria_actual=categoria, posicion="B")
        series = next((s.series for s in registros_slot if s.series), "")

        slots_out.append(SlotProposal(slot=slot_num, ejercicio_a=ex_a, ejercicio_b=ex_b, series=series))

    return SessionProposal(
        categoria=categoria,
        perfil_sesion=perfil_propuesto,
        basado_en_sesiones=len(sesiones_vistas),
        slots=slots_out,
        advertencias=advertencias,
    )
