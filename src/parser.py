"""
Parser para las hojas de gimnasio con formato "SANTA PERPETUA GYM".

Cada hoja (una por microciclo, ej. "MICRO 40") contiene varios bloques de sesion,
uno por categoria/dia/horario. Cada bloque tiene esta forma (columnas A-R del Sheet,
celdas combinadas incluidas):

    DIA, <fecha>, CAT., <categoria>, HORARIO, <horario>, PERFIL DE LA SESION, <perfil>
    CONTENIDOS A TRABAJAR
    ACTIVACION A1, BLOQUE DE CARGA
    1, <ejercicio_A>, <carga_A>, REPS, <ejercicio_B>, <carga_B>, REPS, REPS, SERIES, TIEMPO, PAUSA
    <reps_A>, <reps_B>, <series>
    2, <ejercicio_A>, <carga_A>, REPS, <ejercicio_B>, <carga_B>, REPS, REPS, SERIES, PAUSA
    <reps_A>, <reps_B>, <series>
    ACTIVACION A2, 3, <ejercicio_A>, <carga_A>, REPS, <ejercicio_B>, <carga_B>, REPS, REPS, SERIES, PAUSA
    <reps_A>, <reps_B>, <series>
    4, ...
    ...
    5, REPS, REPS, REPS, SERIES, PAUSA        <- casi siempre vacio (slot sin usar)

Este modulo no asume posiciones de columna fijas: filtra celdas vacias y etiquetas
conocidas, y trabaja por tokens. Esto lo hace robusto tanto a la representacion de
gspread (listas de 18 celdas, muchas vacias) como a exports de texto que colapsan
celdas vacias.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

SECTION_LABELS = {
    "CONTENIDOS A TRABAJAR",
    "ACTIVACION A1",
    "ACTIVACION A2",
    "BLOQUE DE CARGA",
}
VALUE_LABELS = {"REPS", "SERIES", "TIEMPO", "PAUSA"}
META_LABELS = {"DIA", "CAT.", "HORARIO", "PERFIL DE LA SESION"}
SKIP_SHEET_NAMES = {"EJERCICIOS", "EN BLANCO PARA COPIAR", "COPIA DE EN BLANCO PARA COPIAR"}

_NUM_RE = re.compile(r"^-?\d+([.,]\d+)?$")


def _is_number(token: str) -> bool:
    return bool(_NUM_RE.match(token.strip()))


def _clean_row(row: list[str]) -> list[str]:
    return [c.strip() for c in row if c is not None and c.strip() != ""]


def should_skip_sheet(sheet_name: str) -> bool:
    name = sheet_name.strip().upper()
    return name in SKIP_SHEET_NAMES or name.startswith("COPIA DE")


@dataclass
class SetSlot:
    microciclo: str
    fecha: str
    categoria: str
    horario: str
    perfil_sesion: str
    slot: int
    ejercicio_a: str | None = None
    carga_a: str | None = None
    reps_a: str | None = None
    ejercicio_b: str | None = None
    carga_b: str | None = None
    reps_b: str | None = None
    series: str | None = None


def _strip_leading_section_labels(tokens: list[str]) -> list[str]:
    """Quita etiquetas de seccion que a veces quedan pegadas al inicio de una fila
    de ejercicio (ej. "ACTIVACION A2,3,PESO MUERTO,...")."""
    while tokens and tokens[0].upper() in SECTION_LABELS:
        tokens = tokens[1:]
    return tokens


def _is_meta_row(tokens: list[str]) -> bool:
    return bool(tokens) and tokens[0].upper() == "DIA"


def _parse_meta_row(tokens: list[str]) -> dict:
    """Parsea una fila tipo DIA,<fecha>,CAT.,<cat>,HORARIO,<horario>,PERFIL DE LA SESION,<perfil>
    como pares etiqueta/valor, tolerando que falte alguno."""
    data = {"fecha": "", "categoria": "", "horario": "", "perfil_sesion": ""}
    i = 0
    while i < len(tokens):
        label = tokens[i].upper()
        value = tokens[i + 1] if i + 1 < len(tokens) else ""
        if label == "DIA":
            data["fecha"] = value
        elif label == "CAT.":
            data["categoria"] = value
        elif label == "HORARIO":
            data["horario"] = value
        elif label == "PERFIL DE LA SESION":
            data["perfil_sesion"] = value
        i += 2
    return data


def _is_pure_result_row(tokens: list[str]) -> bool:
    return 1 <= len(tokens) <= 3 and all(_is_number(t) for t in tokens)


def _is_slot_row(tokens: list[str]) -> bool:
    return bool(tokens) and tokens[0] in {"1", "2", "3", "4", "5"}


def parse_sheet(sheet_name: str, rows: list[list[str]]) -> list[SetSlot]:
    """Parsea todas las filas crudas (como las devuelve gspread get_all_values())
    de una hoja tipo "MICRO N" y devuelve una lista de SetSlot (uno por ejercicio
    dentro de cada sesion de categoria/dia)."""
    if should_skip_sheet(sheet_name):
        return []

    results: list[SetSlot] = []
    ctx: dict | None = None
    pending: SetSlot | None = None

    for raw_row in rows:
        tokens = _clean_row(raw_row)
        if not tokens:
            continue
        if tokens[0].upper() == "SANTA PERPETUA GYM":
            continue

        if _is_meta_row(tokens):
            ctx = _parse_meta_row(tokens)
            pending = None
            continue

        tokens = _strip_leading_section_labels(tokens)
        if not tokens:
            continue

        if ctx is None:
            # fila de contenido antes de encontrar el primer bloque DIA: ignorar
            continue

        if _is_pure_result_row(tokens) and pending is not None:
            nums = tokens
            if len(nums) >= 1:
                pending.reps_a = nums[0]
            if len(nums) >= 2:
                pending.reps_b = nums[1]
            if len(nums) >= 3:
                pending.series = nums[2]
            results.append(pending)
            pending = None
            continue

        if _is_slot_row(tokens):
            slot_idx = int(tokens[0])
            body = [t for t in tokens[1:] if t.upper() not in VALUE_LABELS]
            slot = SetSlot(
                microciclo=sheet_name,
                fecha=ctx["fecha"],
                categoria=ctx["categoria"],
                horario=ctx["horario"],
                perfil_sesion=ctx["perfil_sesion"],
                slot=slot_idx,
            )
            if len(body) >= 2:
                slot.ejercicio_a, slot.carga_a = body[0], body[1]
            if len(body) >= 4:
                slot.ejercicio_b, slot.carga_b = body[2], body[3]

            if slot.ejercicio_a is None:
                # slot vacio en la plantilla (ej. el "5" que casi nunca se usa)
                pending = None
                continue

            pending = slot
            continue

        # cualquier otra fila (etiquetas sueltas, ruido) se ignora
        pending = None

    return results
