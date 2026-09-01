from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


REPO_ROOT = Path(__file__).resolve().parent
PORTAL_PARTES_PATH = REPO_ROOT / "portal_partes.html"


@dataclass(frozen=True)
class PortalPartesAnalysis:
    title: str
    tabs: list[str]
    panel_ids: list[str]
    default_category_count: int
    default_categories: list[str]
    capabilities: list[str]
    persistence_modes: list[str]
    admin_entities: list[str]
    reporting_outputs: list[str]
    limitations: list[str]


def portal_partes_path() -> Path:
    return PORTAL_PARTES_PATH


def load_portal_partes_html(path: Path | None = None) -> str:
    target = path or PORTAL_PARTES_PATH
    if not target.exists():
        raise FileNotFoundError(f"No se encontro el portal de partes: {target}")
    return target.read_text(encoding="utf-8")


def analyze_portal_partes(path: Path | None = None) -> PortalPartesAnalysis:
    html = load_portal_partes_html(path)
    title = _extract_title(html)
    tabs = re.findall(r'data-tab="([^"]+)"[^>]*>([^<]+)</button>', html)
    panel_ids = re.findall(r'<section class="panel(?: active)?" id="panel-([^"]+)">', html)
    default_categories = _extract_default_categories(html)

    capabilities: list[str] = []
    if 'id="btnLogin"' in html and "hashPin(" in html:
        capabilities.append("Login por trabajador con PIN hasheado en el navegador")
    if 'id="btnCargarParte"' in html:
        capabilities.append("Registro de partes por trabajador, OF/proyecto, fecha, categoria y horas")
    if 'id="tablaUltimos"' in html and 'data-edit="' in html:
        capabilities.append("Edicion y borrado de partes recientes por el propio usuario")
    if 'id="btnConsultar"' in html and "donutSVG(" in html:
        capabilities.append("Consulta operativa por OF con KPIs, timeline, reparto por categorias y trabajadores")
    if 'id="btnAddTrab"' in html and 'id="btnAddOf"' in html and 'id="btnAddCat"' in html:
        capabilities.append("Mantenimiento administrativo de trabajadores, OF/proyectos y categorias")
    if 'id="btnCsvOf"' in html and 'id="btnCsvTodo"' in html and 'id="btnInforme"' in html:
        capabilities.append("Exportacion a CSV y generacion de informe imprimible/PDF")

    persistence_modes: list[str] = []
    if "localStorage.setItem" in html:
        persistence_modes.append("Persistencia local en navegador")
    if "indexedDB.open" in html:
        persistence_modes.append("Recuperacion de manejador mediante IndexedDB")
    if "showSaveFilePicker" in html and "showOpenFilePicker" in html:
        persistence_modes.append("Sincronizacion de fichero JSON con OneDrive mediante File System Access API")

    limitations: list[str] = []
    if "el último que guarda manda" in html:
        limitations.append("Concurrencia basica: el ultimo guardado sobrescribe el estado compartido")
    if "SharePoint / Microsoft Graph" in html:
        limitations.append("No existe backend multiusuario real; el propio HTML recomienda evolucionar a SharePoint/Microsoft Graph")
    if "if(!FSA)" in html:
        limitations.append("La escritura en nube depende de Edge/Chrome con soporte File System Access")
    if "window.open" in html:
        limitations.append("El informe PDF depende de ventanas emergentes del navegador")

    return PortalPartesAnalysis(
        title=title,
        tabs=[label.strip() for _, label in tabs],
        panel_ids=panel_ids,
        default_category_count=len(default_categories),
        default_categories=default_categories,
        capabilities=capabilities,
        persistence_modes=persistence_modes,
        admin_entities=["Trabajadores", "OF / Proyectos", "Categorias de trabajo"],
        reporting_outputs=["Consulta SCADA por OF", "CSV filtrado", "CSV global", "Informe imprimible / PDF"],
        limitations=limitations,
    )


def _extract_title(html: str) -> str:
    match = re.search(r"<title>([^<]+)</title>", html)
    return match.group(1).strip() if match else "Portal de Partes"


def _extract_default_categories(html: str) -> list[str]:
    match = re.search(r"const CATS_DEFECTO=\[(.*?)\];", html, re.DOTALL)
    if not match:
        return []
    return re.findall(r"'([^']+)'", match.group(1))


@st.cache_data(show_spinner=False)
def _load_analysis():
    return analyze_portal_partes()


@st.cache_data(show_spinner=False)
def _load_portal_html() -> str:
    return load_portal_partes_html()


def _render_sidebar() -> None:
    st.sidebar.title("⏱️ IS Partes Trabajo")
    st.sidebar.caption("Standalone Streamlit app")
    st.sidebar.markdown(
        """
        **Incluye**
        - Portal HTML operativo
        - Analisis funcional
        - Checklist de publicacion
        """
    )


def main() -> None:
    st.set_page_config(
        page_title="Portal de Partes, Tiempos y Proyectos",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_sidebar()

    analysis = _load_analysis()
    portal_html = _load_portal_html()
    portal_file = portal_partes_path()

    st.title("⏱️ Portal de Partes, Tiempos y Proyectos")
    st.caption("Repositorio independiente listo para ejecutar y publicar en Streamlit desde GitHub.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pestañas", len(analysis.tabs))
    m2.metric("Categorias base", analysis.default_category_count)
    m3.metric("Salidas", len(analysis.reporting_outputs))
    m4.metric("Despliegue", "Listo")

    tab_app, tab_analysis, tab_publish = st.tabs(
        ["Aplicacion", "Analisis", "Publicacion"]
    )

    with tab_app:
        st.info(
            "El portal original se ejecuta embebido para mantener su comportamiento actual. "
            "Para guardar en OneDrive o generar informes PDF se necesita un navegador compatible."
        )
        st.download_button(
            "Descargar portal_partes.html",
            data=portal_html.encode("utf-8"),
            file_name=portal_file.name,
            mime="text/html",
            use_container_width=True,
        )
        components.html(portal_html, height=1900, scrolling=True)

    with tab_analysis:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Arquitectura detectada")
            st.write(f"**Titulo:** {analysis.title}")
            st.write(f"**Pestañas:** {', '.join(analysis.tabs)}")
            st.write(f"**Paneles:** {', '.join(analysis.panel_ids)}")
            st.markdown("#### Capacidades")
            for item in analysis.capabilities:
                st.markdown(f"- {item}")

        with c2:
            st.subheader("Persistencia y reporting")
            st.markdown("#### Persistencia")
            for item in analysis.persistence_modes:
                st.markdown(f"- {item}")
            st.markdown("#### Entidades maestras")
            for item in analysis.admin_entities:
                st.markdown(f"- {item}")
            st.markdown("#### Salidas")
            for item in analysis.reporting_outputs:
                st.markdown(f"- {item}")

        st.warning("Limitaciones actuales")
        for item in analysis.limitations:
            st.markdown(f"- {item}")

    with tab_publish:
        st.subheader("Checklist para Streamlit Community Cloud")
        st.markdown(
            """
            1. Sube este repositorio a GitHub.
            2. En Streamlit Community Cloud selecciona el repositorio y la rama principal.
            3. Define `streamlit_app.py` como archivo de entrada.
            4. Publica sin secretos adicionales: esta app no requiere variables de entorno.
            """
        )
        st.code(
            "pip install -r requirements.txt\nstreamlit run streamlit_app.py",
            language="bash",
        )
        st.markdown(
            """
            **Notas operativas**
            - En Streamlit embebido, el portal funciona como UI cliente.
            - Las funciones de OneDrive dependen del navegador del usuario final.
            - Si quieres multiusuario real, el siguiente paso es migrar la persistencia a backend/API.
            """
        )


if __name__ == "__main__":
    main()
