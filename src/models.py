from __future__ import annotations

from dataclasses import dataclass, field

PRIMERA_VEZ = "primera_vez"
SUBE_REPS = "sube_reps"
RESET_REPS_SUBE_KG = "reset_reps_sube_kg"


@dataclass
class ExerciseProposal:
    posicion: str  # "A" | "B"
    nombre: str
    rol: str  # "troncal" | "auxiliar" | "" (patron desconocido)
    carga: str
    reps: str
    week_index: int
    tipo_ajuste: str  # PRIMERA_VEZ | SUBE_REPS | RESET_REPS_SUBE_KG
    reps_anterior: str
    carga_anterior: str
    ultima_vez: str = ""  # fecha (texto) de la ultima vez que se hizo este ejercicio, "" si nunca


@dataclass
class SlotProposal:
    slot: int
    ejercicio_a: ExerciseProposal | None
    ejercicio_b: ExerciseProposal | None
    series: str


@dataclass
class SessionProposal:
    categoria: str
    perfil_sesion: str
    basado_en_sesiones: int
    slots: list[SlotProposal] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
