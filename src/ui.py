"""Estilos custom de la app: reemplaza los indicadores de carga por defecto
de Streamlit (el iconito de "Running..." arriba a la derecha y el spinner
inline) por un overlay de vidrio esmerilado a pantalla completa con una
barra de progreso indeterminada centrada."""
from __future__ import annotations

import streamlit as st

_LOADING_OVERLAY_CSS = """
<style>
/* Oculta el indicador de "running" (icono arriba a la derecha) */
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* El spinner de Streamlit (st.spinner / cache_data show_spinner) pasa a ser
   un overlay de vidrio esmerilado que cubre toda la pantalla mientras la
   app esta procesando. */
[data-testid="stSpinner"] {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    margin: 0 !important;
    z-index: 999999 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: rgba(90, 100, 115, 0.55) !important;
    backdrop-filter: blur(16px) saturate(140%) !important;
    -webkit-backdrop-filter: blur(16px) saturate(140%) !important;
}

[data-testid="stSpinner"] > div {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    gap: 1.1rem !important;
}

/* Ocultamos el icono giratorio default */
[data-testid="stSpinnerIcon"] {
    display: none !important;
}

[data-testid="stSpinner"] [data-testid="stMarkdownContainer"] p {
    color: #ffffff !important;
    font-size: 1.05rem !important;
    font-weight: 500 !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
    margin: 0 !important;
}

/* Barra de carga indeterminada, centrada debajo del texto */
[data-testid="stSpinner"] > div::after {
    content: "";
    display: block;
    width: 240px;
    height: 6px;
    border-radius: 999px;
    overflow: hidden;
    background-color: rgba(255, 255, 255, 0.25);
    background-image: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.95), transparent);
    background-size: 55% 100%;
    background-repeat: no-repeat;
    background-position: -55% 0;
    animation: cf-loading-sweep 1.1s ease-in-out infinite;
}

@keyframes cf-loading-sweep {
    0%   { background-position: -55% 0; }
    100% { background-position: 155% 0; }
}
</style>
"""


def inject_loading_overlay() -> None:
    st.markdown(_LOADING_OVERLAY_CSS, unsafe_allow_html=True)
