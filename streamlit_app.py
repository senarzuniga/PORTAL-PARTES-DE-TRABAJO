from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


APP_ROOT = Path(__file__).resolve().parent
PORTAL_PATH = APP_ROOT / "portal_partes.html"
AUTO_REFRESH_MS = 120000


def load_portal_html() -> str:
    if not PORTAL_PATH.exists():
        raise FileNotFoundError(f"No se encuentra {PORTAL_PATH.name}")
    return PORTAL_PATH.read_text(encoding="utf-8")


def main() -> None:
    st.set_page_config(
        page_title="Portal de Partes de Horas",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        #MainMenu, header, footer {visibility:hidden;}
        .block-container {padding:0; max-width:none;}
        iframe {border:0;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.subheader("Actualización")
        if st.button("Recargar portal", use_container_width=True):
            st.rerun()
        st.caption("La vista se refresca automáticamente cada 2 minutos.")

    modified_at = datetime.fromtimestamp(PORTAL_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"Archivo cargado desde: {PORTAL_PATH.name} · última modificación detectada: {modified_at}")

    components.html(
        f"""
        <script>
        setTimeout(function () {{
          window.parent.location.reload();
        }}, {AUTO_REFRESH_MS});
        </script>
        """,
        height=0,
    )

    components.html(load_portal_html(), height=2200, scrolling=True)


if __name__ == "__main__":
    main()
