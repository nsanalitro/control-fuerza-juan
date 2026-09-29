from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.data_source import append_sesion, load_historial_fuente, load_historial_registro
from src.engine import build_proposal
from src.models import SessionProposal

st.set_page_config(page_title="Control Fuerza - Juan", page_icon="🏋️", layout="centered")


def get_config() -> tuple[tuple[str, ...], str] | None:
    try:
        historial_ids = tuple(st.secrets["sheets"]["historial_ids"])
        registro_id = st.secrets["sheets"]["registro_id"]
        return historial_ids, registro_id
    except Exception:
        return None


def proposal_to_dataframe(proposal: SessionProposal) -> pd.DataFrame:
    rows = []
    for s in proposal.slots:
        rows.append(
            {
                "slot": s.slot,
                "ejercicio_a": s.ejercicio_a,
                "carga_a": s.carga_a_sugerida,
                "reps_a": s.reps_a_objetivo,
                "ejercicio_b": s.ejercicio_b,
                "carga_b": s.carga_b_sugerida,
                "reps_b": s.reps_b_objetivo,
                "series": s.series_objetivo,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
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

    historial_ids, registro_id = config

    with st.spinner("Leyendo historial..."):
        historial = list(load_historial_fuente(historial_ids))
        historial += load_historial_registro(registro_id)

    categorias = sorted({s.categoria for s in historial if s.categoria})
    if not categorias:
        st.warning("No se encontraron categorías en el historial. Revisá la configuración de las planillas.")
        st.stop()

    col1, col2 = st.columns([2, 1])
    with col1:
        categoria = st.selectbox("¿Con qué categoría trabajamos hoy?", categorias)
    with col2:
        fecha_sesion = st.date_input("Fecha", value=date.today())

    if st.button("Generar propuesta", type="primary"):
        st.session_state["proposal"] = build_proposal(historial, categoria)
        st.session_state["proposal_categoria"] = categoria

    proposal: SessionProposal | None = st.session_state.get("proposal")
    if proposal is not None and st.session_state.get("proposal_categoria") == categoria:
        st.divider()
        st.subheader(f"Propuesta para {proposal.categoria}")
        st.caption(
            f"Perfil de sesión sugerido: **{proposal.perfil_sesion or 'sin datos suficientes'}** "
            f"· basado en {proposal.basado_en_sesiones} sesiones anteriores"
        )

        for adv in proposal.advertencias:
            st.warning(adv)

        for s in proposal.slots:
            with st.expander(f"Ejercicio {s.slot} — {s.ejercicio_a} + {s.ejercicio_b}".rstrip(" +"), expanded=True):
                st.caption(f"Usado {s.veces_en_historial} vez/veces · última vez en {s.ultima_vez}")
                if s.carga_a_nota:
                    st.caption(f"A: {s.carga_a_nota}")
                if s.carga_b_nota:
                    st.caption(f"B: {s.carga_b_nota}")

        if proposal.slots:
            df = proposal_to_dataframe(proposal)
            st.markdown("**Ajustá lo que necesites antes de registrar la sesión:**")
            edited = st.data_editor(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "slot": st.column_config.NumberColumn("N°", disabled=True, width="small"),
                    "ejercicio_a": st.column_config.TextColumn("Ejercicio A"),
                    "carga_a": st.column_config.TextColumn("Carga A"),
                    "reps_a": st.column_config.TextColumn("Reps A"),
                    "ejercicio_b": st.column_config.TextColumn("Ejercicio B"),
                    "carga_b": st.column_config.TextColumn("Carga B"),
                    "reps_b": st.column_config.TextColumn("Reps B"),
                    "series": st.column_config.TextColumn("Series"),
                },
                key="editor",
            )

            horario = st.text_input("Horario de la sesión (opcional)", value="")

            if st.button("✅ Registrar esta sesión como ejecutada"):
                filas = edited.to_dict("records")
                append_sesion(
                    registro_id,
                    fecha=fecha_sesion.strftime("%d/%m/%Y"),
                    categoria=proposal.categoria,
                    perfil_sesion=proposal.perfil_sesion,
                    horario=horario,
                    filas=filas,
                )
                st.success("Sesión registrada. La próxima propuesta para esta categoría ya la va a tener en cuenta.")
                del st.session_state["proposal"]

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
