from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExerciseProposal:
    posicion: str  # "A" | "B"
    nombre: str
    rol: str  # "troncal" | "auxiliar" | "" (patron desconocido)
    carga: str
    reps: str
    week_index: int
    banner: str


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
