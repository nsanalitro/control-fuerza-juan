"""Motor de propuesta de sesion (reglas explicitas, sin LLM).

Filosofia: esta app no inventa metodologia de entrenamiento. Reutiliza las
parejas de ejercicios que Juan/Nico ya programaron para cada categoria y
perfil de sesion, rota entre ellas para dar variedad, y sugiere una
progresion de carga conservadora (+5%, redondeada a 2.5kg) SOLO cuando la
carga anterior es un peso claro en kg. Todo lo demas (tiempos isometricos,
"-", pesos corporales) se deja igual y marcado para que Juan lo ajuste segun
como responda el jugador ese dia — la app no tiene forma de saber el RIR/RPE
real de la sesion anterior.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import re

from src.catalog import normalize_name
from src.models import SessionProposal, SlotProposal
from src.parser import SetSlot


def parse_fecha(fecha: str):
    fecha = (fecha or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(fecha, fmt).date()
        except ValueError:
            continue
    return None


def source_order_key(slot: SetSlot):
    """Orden cronologico aproximado: primero por fecha real (mas confiable
    entre temporadas), y si falta, por el numero de microciclo como
    desempate dentro de la misma hoja."""
    fecha = parse_fecha(slot.fecha)
    micro_match = re.search(r"(\d+)", slot.microciclo)
    micro_num = int(micro_match.group(1)) if micro_match else 0
    return (fecha or datetime.min.date(), micro_num)


_CARGA_KG_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*kg$", re.IGNORECASE)
_CARGA_TIME_RE = re.compile(r'^(\d+(?:[.,]\d+)?)\s*"$')


def suggest_carga(ultima_carga: str) -> tuple[str, str]:
    """A partir de la ultima carga registrada, devuelve (carga_sugerida, nota).
    Solo propone progresion numerica cuando el dato anterior es un peso claro
    en kg; para el resto, mantiene el valor y deja la decision a Juan."""
    c = (ultima_carga or "").strip()
    if not c or c == "-":
        return "-", "sin carga registrada antes"

    m = _CARGA_KG_RE.match(c)
    if m:
        valor = float(m.group(1).replace(",", "."))
        sugerido = round((valor * 1.05) / 2.5) * 2.5
        if sugerido <= valor:
            sugerido = valor + 2.5
        return f"{sugerido:g}kg", f"progresion sugerida sobre {c} (última vez) — ajustar según cómo respondió"

    m = _CARGA_TIME_RE.match(c)
    if m:
        return c, f"mantener {c} (última vez) — ajustar según técnica"

    return c, f"mantener {c} (última vez)"


def build_proposal(
    historial: list[SetSlot],
    categoria: str,
    perfiles_recientes_n: int = 4,
    rotacion_n: int = 3,
) -> SessionProposal:
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

    registros_ordenados = sorted(registros, key=source_order_key, reverse=True)

    sesiones_vistas: list[tuple[str, str, str]] = []
    perfiles_recientes: list[str] = []
    vistos: set[tuple[str, str, str]] = set()
    for s in registros_ordenados:
        key = (s.microciclo, s.fecha, s.horario)
        if key in vistos:
            continue
        vistos.add(key)
        sesiones_vistas.append(key)
        if s.perfil_sesion and len(perfiles_recientes) < perfiles_recientes_n:
            perfiles_recientes.append(s.perfil_sesion)

    advertencias: list[str] = []
    if perfiles_recientes:
        perfil_propuesto = Counter(perfiles_recientes).most_common(1)[0][0]
    else:
        perfil_propuesto = ""
        advertencias.append("No se encontró 'perfil de la sesión' en el historial reciente; elegí uno manualmente.")

    slots_out: list[SlotProposal] = []
    for slot_num in (1, 2, 3, 4):
        pool = [s for s in registros_ordenados if s.slot == slot_num and s.ejercicio_a and s.perfil_sesion == perfil_propuesto]
        fallback_used = False
        if not pool:
            pool = [s for s in registros_ordenados if s.slot == slot_num and s.ejercicio_a]
            fallback_used = True

        if not pool:
            advertencias.append(f"Sin historial para el ejercicio {slot_num}; agregalo manualmente.")
            continue

        pairing_last_seen: dict[tuple[str, str], SetSlot] = {}
        pairing_count: Counter = Counter()
        for s in pool:  # pool va de mas reciente a mas antiguo
            key = (normalize_name(s.ejercicio_a), normalize_name(s.ejercicio_b or ""))
            pairing_count[key] += 1
            if key not in pairing_last_seen:
                pairing_last_seen[key] = s

        parejas_recientes_orden = list(pairing_last_seen.keys())[: max(rotacion_n, 1)]
        pareja_elegida = parejas_recientes_orden[-1]

        ultimo_uso = pairing_last_seen[pareja_elegida]
        carga_a_sug, nota_a = suggest_carga(ultimo_uso.carga_a or "")
        carga_b_sug, nota_b = ("", "")
        if ultimo_uso.ejercicio_b:
            carga_b_sug, nota_b = suggest_carga(ultimo_uso.carga_b or "")

        if fallback_used:
            advertencias.append(
                f"Ejercicio {slot_num}: no hay historial con perfil '{perfil_propuesto}', se usó el historial general de la categoría."
            )

        slots_out.append(
            SlotProposal(
                slot=slot_num,
                ejercicio_a=ultimo_uso.ejercicio_a or "",
                carga_a_sugerida=carga_a_sug,
                carga_a_nota=nota_a,
                reps_a_objetivo=ultimo_uso.reps_a or "",
                ejercicio_b=ultimo_uso.ejercicio_b or "",
                carga_b_sugerida=carga_b_sug,
                carga_b_nota=nota_b,
                reps_b_objetivo=ultimo_uso.reps_b or "",
                series_objetivo=ultimo_uso.series or "",
                veces_en_historial=pairing_count[pareja_elegida],
                ultima_vez=ultimo_uso.microciclo,
            )
        )

    return SessionProposal(
        categoria=categoria,
        perfil_sesion=perfil_propuesto,
        basado_en_sesiones=len(sesiones_vistas),
        slots=slots_out,
        advertencias=advertencias,
    )
