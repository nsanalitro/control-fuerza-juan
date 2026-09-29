from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SlotProposal:
    slot: int
    ejercicio_a: str
    carga_a_sugerida: str
    carga_a_nota: str
    reps_a_objetivo: str
    ejercicio_b: str
    carga_b_sugerida: str
    carga_b_nota: str
    reps_b_objetivo: str
    series_objetivo: str
    veces_en_historial: int
    ultima_vez: str  # nombre del microciclo o "" si nunca se uso


@dataclass
class SessionProposal:
    categoria: str
    perfil_sesion: str
    basado_en_sesiones: int
    slots: list[SlotProposal] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
