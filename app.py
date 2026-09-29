from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from src.catalog import EXERCISE_PATTERNS, normalize_name
from src.data_source import append_sesion, load_gym_schedule, load_historial_fuente, load_historial_registro, load_partidos_fcf
from src.engine import build_proposal, compute_progression_for_exercise, parse_fecha
from src.fcf import proximo_partido
from src.fcf_config import fcf_ids_de
from src.models import PRIMERA_VEZ, SUBE_REPS, ExerciseProposal, SessionProposal, SlotProposal
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


def render_banner_compacto(e: ExerciseProposal, hoy: date) -> str:
    if e.tipo_ajuste == PRIMERA_VEZ:
        if not e.ultima_vez:
            return "nunca registrado antes para esta categoría · sin carga de referencia"
        ultima_fecha = parse_fecha(e.ultima_vez)
        if ultima_fecha is not None and ultima_fecha.weekday() == hoy.weekday():
            gap = (hoy - ultima_fecha).days
            motivo = f"hace {gap} días (mismo día de semana, pero hace mucho) — se retoma como rutina nueva"
        else:
            motivo = f"cayó en {WEEKDAY_ES[ultima_fecha.weekday()]}, distinto al día de hoy — sin ajuste automático" if ultima_fecha else "día distinto, sin ajuste automático"
        return f"última vez {e.ultima_vez} · {e.reps} reps · {e.carga} — {motivo}"

    flecha_reps = "⬆️" if e.tipo_ajuste == SUBE_REPS else "⬇️"
    if e.carga_anterior and e.carga != e.carga_anterior:
        carga_txt = f"{e.carga_anterior} ➡️ {e.carga}"
    else:
        carga_txt = e.carga
    return f"Semana {e.week_index} · reps {e.reps} {flecha_reps} · {carga_txt}"


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

    fcf_ids = fcf_ids_de(categoria)
    if fcf_ids:
        with st.spinner("Consultando calendario de la federación..."):
            partidos = load_partidos_fcf(fcf_ids["grup_id"], fcf_ids["team_id"])
        proximo = proximo_partido(partidos, datetime.combine(fecha_sesion, datetime.min.time()))
        if proximo:
            condicion = "local" if proximo["local"] else "visitante"
            lugar = f", en {proximo['campo']}" if proximo["campo"] else ""
            st.info(
                f"⚽ Próximo partido de **{categoria}**: vs **{proximo['rival']}** "
                f"({condicion}) — {WEEKDAY_ES[proximo['fecha'].weekday()]} {proximo['fecha'].strftime('%d/%m %H:%M')}hs{lugar}"
            )
        else:
            st.caption(f"No encontré próximo partido programado en la federación para {categoria}.")

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
        cat_norm = normalize_name(categoria)
        historial_categoria = [h for h in historial if normalize_name(h.categoria) == cat_norm]

        # Si Juan cambio el ejercicio de una fila, recalculamos SU propia
        # progresion (no la del ejercicio que reemplazo): el cartel de abajo
        # pasa a reflejar el historial real de ese ejercicio nuevo (o "nunca
        # registrado antes" si no tiene). Streamlit no permite reescribir la
        # carga/reps ya tipeadas en la tabla desde acá -- Juan las ajusta a
        # mano siguiendo lo que diga el cartel.
        mostrar: dict[int, dict[str, ExerciseProposal | None]] = {}
        for row_idx, s in enumerate(proposal.slots):
            cambios = edited_cells.get(row_idx, {})
            fila: dict[str, ExerciseProposal | None] = {"A": s.ejercicio_a, "B": s.ejercicio_b}
            for pos, col_ej in (("A", "ejercicio_a"), ("B", "ejercicio_b")):
                nuevo_nombre = cambios.get(col_ej)
                if nuevo_nombre:
                    fila[pos] = compute_progression_for_exercise(historial_categoria, nuevo_nombre, fecha_sesion, posicion=pos)
            mostrar[row_idx] = fila

        for row_idx, s in enumerate(proposal.slots):
            ea, eb = mostrar[row_idx]["A"], mostrar[row_idx]["B"]
            titulo = " + ".join(
                filter(None, [exercise_label(ea.nombre, ea.rol) if ea else "", exercise_label(eb.nombre, eb.rol) if eb else ""])
            )
            with st.expander(f"Ejercicio {s.slot} — {titulo}", expanded=True):
                if ea:
                    st.info(f"**A ({ROL_LABEL.get(ea.rol, ea.rol) or 'sin clasificar'}):** {render_banner_compacto(ea, fecha_sesion)}")
                if eb and eb.nombre:
                    st.info(f"**B ({ROL_LABEL.get(eb.rol, eb.rol) or 'sin clasificar'}):** {render_banner_compacto(eb, fecha_sesion)}")

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

        horario = next((hor for cat, hor in categorias_hoy if cat == categoria), "")

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
