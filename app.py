from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.catalog import EXERCISE_PATTERNS
from src.data_source import append_sesion, load_gym_schedule, load_historial_fuente, load_historial_registro
from src.engine import build_proposal
from src.models import SessionProposal, SlotProposal
from src.schedule_parser import categorias_de_hoy
from src.ui import inject_loading_overlay

EJERCICIOS_CONOCIDOS = sorted(EXERCISE_PATTERNS.keys())

st.set_page_config(page_title="Control Fuerza - Juan", page_icon="🏋️", layout="centered")

WEEKDAY_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
ROL_LABEL = {"troncal": "troncal", "auxiliar": "auxiliar", "": ""}
HORARIO_LABEL = {"18": "18hs", "19": "19hs", "20": "20:20"}


def get_config() -> dict | None:
    try:
        return {
            "historial_ids": tuple(st.secrets["sheets"]["historial_ids"]),
            "registro_id": st.secrets["sheets"]["registro_id"],
            "gym_schedule_id": st.secrets["sheets"].get("gym_schedule_id"),
            "gym_schedule_sheet": st.secrets["sheets"].get("gym_schedule_sheet", "GYM"),
        }
    except Exception:
        return None


def proposal_to_dataframe(proposal: SessionProposal) -> pd.DataFrame:
    rows = []
    for s in proposal.slots:
        ea, eb = s.ejercicio_a, s.ejercicio_b
        rows.append(
            {
                "slot": s.slot,
                "ejercicio_a": ea.nombre if ea else "",
                "carga_a": ea.carga if ea else "",
                "reps_a": ea.reps if ea else "",
                "ejercicio_b": eb.nombre if eb else "",
                "carga_b": eb.carga if eb else "",
                "reps_b": eb.reps if eb else "",
                "series": s.series,
            }
        )
    return pd.DataFrame(rows)


def exercise_label(nombre: str, rol: str) -> str:
    if not nombre:
        return ""
    return f"{nombre} ({ROL_LABEL.get(rol, rol)})" if rol else nombre


def get_edited_cells(editor_key: str) -> dict[int, dict]:
    state = st.session_state.get(editor_key)
    if not state:
        return {}
    return {int(k): v for k, v in state.get("edited_rows", {}).items()}


def main() -> None:
    inject_loading_overlay()
    st.title("🏋️ Control Fuerza — Juan")
    st.markdown("### ¡Hola Juan! ¿Cómo andás? ¿Qué planificamos hoy?")

    config = get_config()
    if config is None:
        st.error(
            "Todavía no está configurada la conexión con Google Sheets.\n\n"
            "Falta `st.secrets['gcp_service_account']` y `st.secrets['sheets']` "
            "(ver README para el paso a paso)."
        )
        st.stop()

    with st.spinner("Leyendo historial..."):
        historial = list(load_historial_fuente(config["historial_ids"]))
        historial += load_historial_registro(config["registro_id"])

    categorias = sorted({s.categoria for s in historial if s.categoria})
    if not categorias:
        st.warning("No se encontraron categorías en el historial. Revisá la configuración de las planillas.")
        st.stop()

    fecha_sesion = st.date_input("Fecha", value=date.today())
    dia_nombre = WEEKDAY_ES[fecha_sesion.weekday()]

    categorias_hoy: list[tuple[str, str]] = []
    if config["gym_schedule_id"]:
        with st.spinner("Leyendo horario de gimnasio..."):
            try:
                schedule = load_gym_schedule(config["gym_schedule_id"], config["gym_schedule_sheet"], fecha_sesion)
                categorias_hoy = categorias_de_hoy(schedule, fecha_sesion)
            except Exception as e:
                st.caption(f"No pude leer la planilla de horarios ({e}).")

    if categorias_hoy:
        detalle = ", ".join(f"{cat} ({HORARIO_LABEL.get(hor, hor + 'hs')})" for cat, hor in categorias_hoy)
        st.info(f"📅 **{dia_nombre} {fecha_sesion.strftime('%d/%m')}** tienen gym programado: {detalle}")
    elif config["gym_schedule_id"]:
        st.caption(f"No encontré categorías con gym programado para el {dia_nombre.lower()} {fecha_sesion.strftime('%d/%m')} en la planilla de horarios.")

    default_index = 0
    if categorias_hoy:
        for cat, _hor in categorias_hoy:
            if cat in categorias:
                default_index = categorias.index(cat)
                break

    categoria = st.selectbox("¿Con qué categoría trabajamos hoy?", categorias, index=default_index)

    if st.button("Generar propuesta", type="primary"):
        st.session_state["proposal"] = build_proposal(historial, categoria, hoy=fecha_sesion)
        st.session_state["proposal_categoria"] = categoria
        st.session_state.pop("editor", None)

    proposal: SessionProposal | None = st.session_state.get("proposal")
    if proposal is not None and st.session_state.get("proposal_categoria") == categoria:
        st.divider()
        st.subheader(f"Propuesta para {proposal.categoria}")
        st.caption(
            f"Perfil de sesión: **{proposal.perfil_sesion or 'sin datos suficientes'}** "
            f"· basado en {proposal.basado_en_sesiones} sesiones anteriores"
        )

        for adv in proposal.advertencias:
            st.warning(adv)

        baseline_df = proposal_to_dataframe(proposal)
        edited_cells = get_edited_cells("editor")

        for row_idx, s in enumerate(proposal.slots):
            ea, eb = s.ejercicio_a, s.ejercicio_b
            cambios = edited_cells.get(row_idx, {})
            titulo = " + ".join(
                filter(None, [exercise_label(ea.nombre, ea.rol) if ea else "", exercise_label(eb.nombre, eb.rol) if eb else ""])
            )
            with st.expander(f"Ejercicio {s.slot} — {titulo}", expanded=True):
                if ea and "ejercicio_a" not in cambios:
                    st.caption(f"**A ({ROL_LABEL.get(ea.rol, ea.rol) or 'sin clasificar'}):** {ea.banner}")
                if eb and eb.nombre and "ejercicio_b" not in cambios:
                    st.caption(f"**B ({ROL_LABEL.get(eb.rol, eb.rol) or 'sin clasificar'}):** {eb.banner}")

        opciones_ejercicio = sorted(
            set(EJERCICIOS_CONOCIDOS) | set(baseline_df["ejercicio_a"]) | set(baseline_df["ejercicio_b"]) | {""}
        )

        st.markdown("**Ajustá lo que necesites antes de registrar la sesión:**")
        edited = st.data_editor(
            baseline_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "slot": st.column_config.NumberColumn("N°", disabled=True, width="small"),
                "ejercicio_a": st.column_config.SelectboxColumn("Ejercicio A ▾", options=opciones_ejercicio),
                "carga_a": st.column_config.TextColumn("Carga A"),
                "reps_a": st.column_config.TextColumn("Reps A"),
                "ejercicio_b": st.column_config.SelectboxColumn("Ejercicio B ▾", options=opciones_ejercicio),
                "carga_b": st.column_config.TextColumn("Carga B"),
                "reps_b": st.column_config.TextColumn("Reps B"),
                "series": st.column_config.TextColumn("Series"),
            },
            key="editor",
        )

        horario = st.text_input("Horario de la sesión (opcional)", value="")

        if st.button("✅ Registrar esta sesión como ejecutada"):
            with st.spinner("Guardando sesión..."):
                filas = edited.to_dict("records")
                append_sesion(
                    config["registro_id"],
                    fecha=fecha_sesion.strftime("%d/%m/%Y"),
                    categoria=proposal.categoria,
                    perfil_sesion=proposal.perfil_sesion,
                    horario=horario,
                    filas=filas,
                )
            st.success("Sesión registrada. La próxima propuesta para esta categoría ya la va a tener en cuenta.")
            del st.session_state["proposal"]
            st.session_state.pop("editor", None)

    with st.sidebar:
        st.subheader("Historial reciente")
        cat_hist = st.selectbox("Categoría", categorias, key="hist_categoria")
        registros_cat = sorted(
            [s for s in historial if s.categoria == cat_hist],
            key=lambda s: (s.fecha, s.microciclo),
            reverse=True,
        )[:20]
        if registros_cat:
            hist_df = pd.DataFrame(
                [
                    {
                        "fecha": s.fecha,
                        "slot": s.slot,
                        "ejercicio_a": s.ejercicio_a,
                        "carga_a": s.carga_a,
                        "ejercicio_b": s.ejercicio_b,
                        "carga_b": s.carga_b,
                    }
                    for s in registros_cat
                ]
            )
            st.dataframe(hist_df, hide_index=True, use_container_width=True)
        else:
            st.caption("Sin historial para esta categoría todavía.")


if __name__ == "__main__":
    main()
