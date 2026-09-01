from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests
import streamlit as st
import streamlit.components.v1 as components


REPO_ROOT = Path(__file__).resolve().parent
PORTAL_PARTES_PATH = REPO_ROOT / "portal_partes.html"
DEFAULT_DB_PATH = REPO_ROOT / "partes_horas_db.json"
DEFAULT_REPOSITORY = "senarzuniga/PORTAL-PARTES-DE-TRABAJO"
DEFAULT_BRANCH = "main"
DEFAULT_REMOTE_DB_PATH = "partes_horas_db.json"
DEFAULT_CATEGORIES = [
    "Ingeniería mecánica",
    "Ingeniería eléctrica",
    "Ingeniería de automatización / control",
    "Diseño / CAD / Delineación",
    "Programación PLC / SCADA / HMI",
    "Comercial / Ofertas / Negociación",
    "Gestión de proyecto (PM)",
    "Compras / Gestión con proveedores",
    "Puesta en marcha / Comisionado",
    "Montaje / Taller / Fabricación",
    "Documentación / Marcado CE / Calidad",
    "Reuniones / Coordinación",
    "Desplazamientos",
    "Formación",
    "Otros",
]


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


@dataclass(frozen=True)
class GitHubRepoConfig:
    token: str
    repository: str
    branch: str
    db_path: str

    @property
    def has_write_access(self) -> bool:
        return bool(self.token)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return uuid.uuid4().hex


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


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
        capabilities.append("Login por trabajador con PIN hasheado")
    if 'id="btnCargarParte"' in html:
        capabilities.append("Registro de partes por trabajador, OF/proyecto, fecha, categoria y horas")
    if 'id="btnConsultar"' in html:
        capabilities.append("Consulta operativa por OF con filtros, KPIs y detalle")
    if 'id="btnAddTrab"' in html and 'id="btnAddOf"' in html and 'id="btnAddCat"' in html:
        capabilities.append("Administracion de trabajadores, OF/proyectos y categorias")
    if 'id="btnCsvOf"' in html and 'id="btnCsvTodo"' in html and 'id="btnInforme"' in html:
        capabilities.append("Exportacion CSV e informe imprimible")

    persistence_modes: list[str] = []
    if "localStorage.setItem" in html:
        persistence_modes.append("Persistencia local en navegador")
    if "indexedDB.open" in html:
        persistence_modes.append("Persistencia auxiliar en IndexedDB")
    if "showSaveFilePicker" in html and "showOpenFilePicker" in html:
        persistence_modes.append("Sincronizacion local con OneDrive via File System Access API")

    limitations: list[str] = []
    if "el último que guarda manda" in html:
        limitations.append("Concurrencia basica: el ultimo guardado sobrescribe")
    if "SharePoint / Microsoft Graph" in html:
        limitations.append("El propio HTML recomienda evolucionar a backend real o Graph")
    if "window.open" in html:
        limitations.append("La impresion PDF depende del navegador")

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


def _secret_or_env(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value is not None:
                return str(value).strip()
    except Exception:
        pass
    return os.environ.get(name, default).strip()


def get_github_config() -> GitHubRepoConfig:
    return GitHubRepoConfig(
        token=_secret_or_env("GITHUB_TOKEN"),
        repository=_secret_or_env("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        branch=_secret_or_env("GITHUB_BRANCH", DEFAULT_BRANCH),
        db_path=_secret_or_env("GITHUB_DB_PATH", DEFAULT_REMOTE_DB_PATH),
    )


def default_db_state(repository: str = DEFAULT_REPOSITORY, branch: str = DEFAULT_BRANCH, db_path: str = DEFAULT_REMOTE_DB_PATH) -> dict[str, Any]:
    return {
        "meta": {
            "version": 3,
            "backend": "github-contents-json",
            "repository": repository,
            "branch": branch,
            "db_path": db_path,
            "last_saved": now_utc(),
        },
        "trabajadores": [
            {
                "id": "trab-admin",
                "nombre": "Administrador",
                "usuario": "admin",
                "pinHash": hash_pin("1234"),
                "rol": "admin",
            }
        ],
        "ofs": [
            {
                "id": "of-ejemplo",
                "codigo": "OF-EJEMPLO",
                "desc": "Proyecto de ejemplo",
                "empresa": "IS Backoffice",
                "cliente": "",
                "distribuidor": "",
                "horasPrev": 0.0,
            }
        ],
        "categorias": [
            {"id": f"cat-{index + 1:02d}", "nombre": name}
            for index, name in enumerate(DEFAULT_CATEGORIES)
        ],
        "partes": [],
    }


def normalize_state(raw: dict[str, Any] | None, config: GitHubRepoConfig) -> dict[str, Any]:
    state = copy.deepcopy(raw or {})
    default = default_db_state(config.repository, config.branch, config.db_path)

    meta = state.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("version", 3)
    meta["backend"] = "github-contents-json"
    meta["repository"] = config.repository
    meta["branch"] = config.branch
    meta["db_path"] = config.db_path
    meta.setdefault("last_saved", now_utc())
    state["meta"] = meta

    trabajadores = state.get("trabajadores")
    if not isinstance(trabajadores, list):
        trabajadores = []
    cleaned_workers = []
    for worker in trabajadores:
        if not isinstance(worker, dict):
            continue
        cleaned_workers.append(
            {
                "id": str(worker.get("id") or uid()),
                "nombre": str(worker.get("nombre") or "Sin nombre"),
                "usuario": str(worker.get("usuario") or "").strip(),
                "pinHash": str(worker.get("pinHash") or ""),
                "rol": str(worker.get("rol") or "trabajador"),
            }
        )
    if not any(w["rol"] == "admin" and w["pinHash"] for w in cleaned_workers):
        cleaned_workers.append(default["trabajadores"][0])
    state["trabajadores"] = cleaned_workers

    raw_ofs = state.get("ofs")
    if not isinstance(raw_ofs, list):
        raw_ufs = state.get("ufs")
        raw_ofs = raw_ufs if isinstance(raw_ufs, list) else []
    cleaned_ofs = []
    for item in raw_ofs:
        if not isinstance(item, dict):
            continue
        cleaned_ofs.append(
            {
                "id": str(item.get("id") or uid()),
                "codigo": str(item.get("codigo") or "OF-SIN-CODIGO"),
                "desc": str(item.get("desc") or ""),
                "empresa": str(item.get("empresa") or ""),
                "cliente": str(item.get("cliente") or ""),
                "distribuidor": str(item.get("distribuidor") or ""),
                "horasPrev": float(item.get("horasPrev") or 0.0),
            }
        )
    if not cleaned_ofs:
        cleaned_ofs = default["ofs"]
    state["ofs"] = cleaned_ofs

    raw_categories = state.get("categorias")
    cleaned_categories = []
    if isinstance(raw_categories, list):
        for item in raw_categories:
            if not isinstance(item, dict):
                continue
            cleaned_categories.append(
                {
                    "id": str(item.get("id") or uid()),
                    "nombre": str(item.get("nombre") or ""),
                }
            )
    if not cleaned_categories:
        cleaned_categories = default["categorias"]
    state["categorias"] = cleaned_categories

    raw_parts = state.get("partes")
    cleaned_parts = []
    if isinstance(raw_parts, list):
        for item in raw_parts:
            if not isinstance(item, dict):
                continue
            cleaned_parts.append(
                {
                    "id": str(item.get("id") or uid()),
                    "fecha": str(item.get("fecha") or date.today().isoformat()),
                    "trabId": str(item.get("trabId") or ""),
                    "ofId": str(item.get("ofId") or item.get("ufId") or ""),
                    "catId": str(item.get("catId") or ""),
                    "horas": float(item.get("horas") or 0.0),
                    "obs": str(item.get("obs") or ""),
                    "creado": str(item.get("creado") or now_utc()),
                }
            )
    state["partes"] = cleaned_parts
    return state


class GitHubJsonDatabase:
    BASE_URL = "https://api.github.com"

    def __init__(self, config: GitHubRepoConfig):
        if "/" not in config.repository:
            raise ValueError("GITHUB_REPOSITORY debe tener el formato owner/repo")
        self.config = config
        self.owner, self.repo = config.repository.split("/", 1)
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self.session.headers.update(headers)

    def _request(self, method: str, path: str, expected: set[int], **kwargs) -> requests.Response:
        url = f"{self.BASE_URL}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.request(method, url, timeout=30, **kwargs)
                if response.status_code in expected:
                    return response
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                    time.sleep(0.4 * attempt)
                    continue
                raise RuntimeError(
                    f"GitHub API {method.upper()} {path} devolvio {response.status_code}: {response.text[:300]}"
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= 3:
                    break
                time.sleep(0.4 * attempt)
        raise RuntimeError(f"No se pudo conectar con GitHub: {last_exc}")

    def load_state(self) -> tuple[dict[str, Any], str | None]:
        response = self._request(
            "get",
            f"/repos/{self.owner}/{self.repo}/contents/{self.config.db_path}",
            {200, 404},
            params={"ref": self.config.branch},
        )
        if response.status_code == 404:
            state = default_db_state(self.config.repository, self.config.branch, self.config.db_path)
            return normalize_state(state, self.config), None
        payload = response.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        state = json.loads(content)
        return normalize_state(state, self.config), payload.get("sha")

    def save_state(self, state: dict[str, Any], sha: str | None, message: str) -> dict[str, Any]:
        if not self.config.has_write_access:
            raise RuntimeError(
                "Falta GITHUB_TOKEN con permisos de escritura. Configuralo en Streamlit Secrets para guardar cambios."
            )
        normalized = normalize_state(state, self.config)
        normalized["meta"]["last_saved"] = now_utc()
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(
                json.dumps(normalized, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("utf-8"),
            "branch": self.config.branch,
        }
        if sha:
            payload["sha"] = sha
        response = self._request(
            "put",
            f"/repos/{self.owner}/{self.repo}/contents/{self.config.db_path}",
            {200, 201},
            json=payload,
        )
        return response.json()


def find_worker(state: dict[str, Any], worker_id: str) -> dict[str, Any] | None:
    return next((worker for worker in state["trabajadores"] if worker["id"] == worker_id), None)


def find_of(state: dict[str, Any], of_id: str) -> dict[str, Any] | None:
    return next((item for item in state["ofs"] if item["id"] == of_id), None)


def find_category(state: dict[str, Any], cat_id: str) -> dict[str, Any] | None:
    return next((item for item in state["categorias"] if item["id"] == cat_id), None)


def part_label(state: dict[str, Any], part: dict[str, Any]) -> str:
    worker = find_worker(state, part["trabId"])
    of_item = find_of(state, part["ofId"])
    return f'{part["fecha"]} · {worker["nombre"] if worker else "—"} · {of_item["codigo"] if of_item else "—"} · {part["horas"]} h'


def safe_name(item: dict[str, Any] | None, key: str, fallback: str = "—") -> str:
    if not item:
        return fallback
    value = str(item.get(key) or "").strip()
    return value or fallback


def option_index(values: list[str], target: str) -> int:
    return values.index(target) if target in values else 0


def filter_parts(
    state: dict[str, Any],
    of_id: str,
    worker_id: str,
    category_id: str,
    from_date: date | None,
    to_date: date | None,
) -> list[dict[str, Any]]:
    rows = []
    for item in state["partes"]:
        if of_id != "__all" and item["ofId"] != of_id:
            continue
        if worker_id != "__all" and item["trabId"] != worker_id:
            continue
        if category_id != "__all" and item["catId"] != category_id:
            continue
        item_date = date.fromisoformat(item["fecha"])
        if from_date and item_date < from_date:
            continue
        if to_date and item_date > to_date:
            continue
        rows.append(item)
    return sorted(rows, key=lambda row: (row["fecha"], row["creado"]), reverse=True)


def apply_remote_change(
    config: GitHubRepoConfig,
    commit_message: str,
    mutator: Callable[[dict[str, Any]], None],
) -> None:
    db = GitHubJsonDatabase(config)
    state, sha = db.load_state()
    mutator(state)
    db.save_state(state, sha, commit_message)


@st.cache_data(show_spinner=False)
def _analysis_cache() -> PortalPartesAnalysis:
    return analyze_portal_partes()


@st.cache_data(show_spinner=False)
def _legacy_portal_cache() -> str:
    return load_portal_partes_html()


def _set_flash(message: str) -> None:
    st.session_state["flash_message"] = message


def _show_flash() -> None:
    message = st.session_state.pop("flash_message", "")
    if message:
        st.success(message)


def _render_sidebar(config: GitHubRepoConfig, state: dict[str, Any], sha: str | None, current_user: dict[str, Any] | None) -> None:
    st.sidebar.title("⏱️ Portal de Partes")
    st.sidebar.caption("Base de datos GitHub sincronizada")
    st.sidebar.write(f"**Repositorio:** `{config.repository}`")
    st.sidebar.write(f"**Rama:** `{config.branch}`")
    st.sidebar.write(f"**Archivo DB:** `{config.db_path}`")
    st.sidebar.write(f"**SHA actual:** `{(sha or 'pendiente')[:12]}`")
    st.sidebar.write(f"**Escritura:** {'habilitada' if config.has_write_access else 'solo lectura'}")
    st.sidebar.write(f"**Usuarios:** {len(state['trabajadores'])}")
    st.sidebar.write(f"**OF / proyectos:** {len(state['ofs'])}")
    st.sidebar.write(f"**Partes:** {len(state['partes'])}")
    st.sidebar.write(
        f"**Horas totales:** {sum(float(item['horas']) for item in state['partes']):.1f}"
    )
    if current_user:
        st.sidebar.success(f"Sesión: {current_user['nombre']} ({current_user['rol']})")
        if st.sidebar.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("current_user_id", None)
            st.rerun()
    if st.sidebar.button("Sincronizar con GitHub", use_container_width=True):
        st.rerun()


def _login_screen(state: dict[str, Any]) -> None:
    st.subheader("Acceso")
    workers = [worker for worker in state["trabajadores"] if worker["pinHash"]]
    if not workers:
        st.error("No existe ningun usuario con PIN configurado.")
        return
    options = {f"{worker['nombre']} ({worker['usuario']})": worker["id"] for worker in workers}
    with st.form("login_form"):
        selected_label = st.selectbox("Usuario", list(options.keys()))
        pin = st.text_input("PIN", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted:
        worker = find_worker(state, options[selected_label])
        if not worker or worker["pinHash"] != hash_pin(pin):
            st.error("Usuario o PIN incorrecto.")
            return
        st.session_state["current_user_id"] = worker["id"]
        _set_flash(f"Bienvenido, {worker['nombre']}.")
        st.rerun()


def _render_new_part_tab(config: GitHubRepoConfig, state: dict[str, Any], current_user: dict[str, Any]) -> None:
    st.subheader("Nuevo parte")
    of_options = {f"{item['codigo']} — {item['desc']}": item["id"] for item in state["ofs"]}
    cat_options = {item["nombre"]: item["id"] for item in state["categorias"]}
    with st.form("new_part_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Trabajador", value=current_user["nombre"], disabled=True)
        with c2:
            selected_of = st.selectbox("OF / Proyecto", list(of_options.keys()))
        with c3:
            selected_date = st.date_input("Fecha", value=date.today())
        c4, c5 = st.columns(2)
        with c4:
            selected_category = st.selectbox("Categoría", list(cat_options.keys()))
        with c5:
            hours = st.number_input("Horas", min_value=0.5, step=0.5, value=1.0)
        notes = st.text_area("Observaciones")
        submitted = st.form_submit_button("Guardar parte", type="primary")
    if submitted:
        def mutate(remote_state: dict[str, Any]) -> None:
            remote_state["partes"].append(
                {
                    "id": uid(),
                    "fecha": selected_date.isoformat(),
                    "trabId": current_user["id"],
                    "ofId": of_options[selected_of],
                    "catId": cat_options[selected_category],
                    "horas": float(hours),
                    "obs": notes.strip(),
                    "creado": now_utc(),
                }
            )
        try:
            apply_remote_change(
                config,
                f"Registrar parte de {current_user['usuario']} · {selected_date.isoformat()}",
                mutate,
            )
        except Exception as exc:
            st.error(str(exc))
        else:
            _set_flash("Parte guardado en GitHub correctamente.")
            st.rerun()

    st.markdown("#### Mis últimos partes")
    own_parts = [
        item for item in sorted(state["partes"], key=lambda row: row["creado"], reverse=True)
        if item["trabId"] == current_user["id"]
    ]
    if not own_parts:
        st.info("Todavía no has cargado partes.")
        return
    preview_rows = []
    for item in own_parts[:15]:
        of_item = find_of(state, item["ofId"])
        category = find_category(state, item["catId"])
        preview_rows.append(
            {
                "Fecha": item["fecha"],
                "OF": of_item["codigo"] if of_item else "—",
                "Categoría": category["nombre"] if category else "—",
                "Horas": item["horas"],
                "Observaciones": item["obs"],
            }
        )
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

    editable_options = {part_label(state, item): item["id"] for item in own_parts}
    selected_part_label = st.selectbox("Editar o borrar parte", list(editable_options.keys()))
    selected_part = next(item for item in own_parts if item["id"] == editable_options[selected_part_label])
    with st.form("edit_own_part_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            edit_of_label = st.selectbox(
                "OF / Proyecto",
                list(of_options.keys()),
                index=option_index(list(of_options.values()), selected_part["ofId"]),
                key="edit_own_of",
            )
        with c2:
            edit_date = st.date_input(
                "Fecha",
                value=date.fromisoformat(selected_part["fecha"]),
                key="edit_own_date",
            )
        with c3:
            edit_hours = st.number_input(
                "Horas",
                min_value=0.5,
                step=0.5,
                value=float(selected_part["horas"]),
                key="edit_own_hours",
            )
        edit_category_label = st.selectbox(
            "Categoría",
            list(cat_options.keys()),
            index=option_index(list(cat_options.values()), selected_part["catId"]),
            key="edit_own_category",
        )
        edit_notes = st.text_area("Observaciones", value=selected_part["obs"], key="edit_own_notes")
        save = st.form_submit_button("Guardar cambios")
    col_save, col_delete = st.columns(2)
    with col_delete:
        delete = st.button("Borrar parte seleccionado", type="secondary", use_container_width=True)
    if save:
        def mutate(remote_state: dict[str, Any]) -> None:
            target = next((item for item in remote_state["partes"] if item["id"] == selected_part["id"]), None)
            if not target:
                raise RuntimeError("El parte ya no existe en la base de datos remota.")
            target.update(
                {
                    "fecha": edit_date.isoformat(),
                    "ofId": of_options[edit_of_label],
                    "catId": cat_options[edit_category_label],
                    "horas": float(edit_hours),
                    "obs": edit_notes.strip(),
                }
            )
        try:
            apply_remote_change(config, f"Editar parte {selected_part['id']}", mutate)
        except Exception as exc:
            st.error(str(exc))
        else:
            _set_flash("Parte actualizado correctamente.")
            st.rerun()
    if delete:
        def mutate(remote_state: dict[str, Any]) -> None:
            before = len(remote_state["partes"])
            remote_state["partes"] = [item for item in remote_state["partes"] if item["id"] != selected_part["id"]]
            if len(remote_state["partes"]) == before:
                raise RuntimeError("El parte ya no existe en la base de datos remota.")
        try:
            apply_remote_change(config, f"Borrar parte {selected_part['id']}", mutate)
        except Exception as exc:
            st.error(str(exc))
        else:
            _set_flash("Parte eliminado correctamente.")
            st.rerun()


def _render_query_tab(config: GitHubRepoConfig, state: dict[str, Any], current_user: dict[str, Any]) -> None:
    st.subheader("Consulta por OF / proyecto")
    of_lookup = {"Todas las OF": "__all"} | {f"{item['codigo']} — {item['desc']}": item["id"] for item in state["ofs"]}
    worker_lookup = {"Todos los trabajadores": "__all"} | {item["nombre"]: item["id"] for item in state["trabajadores"]}
    category_lookup = {"Todas las categorías": "__all"} | {item["nombre"]: item["id"] for item in state["categorias"]}

    c1, c2, c3 = st.columns(3)
    with c1:
        of_label = st.selectbox("OF / Proyecto", list(of_lookup.keys()))
    with c2:
        worker_label = st.selectbox("Trabajador", list(worker_lookup.keys()))
    with c3:
        category_label = st.selectbox("Categoría", list(category_lookup.keys()))
    c4, c5 = st.columns(2)
    with c4:
        use_from_date = st.checkbox("Filtrar desde fecha", key="use_from_date")
        from_date = st.date_input("Desde", value=date.today(), key="from_date") if use_from_date else None
    with c5:
        use_to_date = st.checkbox("Filtrar hasta fecha", key="use_to_date")
        to_date = st.date_input("Hasta", value=date.today(), key="to_date") if use_to_date else None

    rows = filter_parts(
        state,
        of_lookup[of_label],
        worker_lookup[worker_label],
        category_lookup[category_label],
        from_date,
        to_date,
    )
    if not rows:
        st.info("No hay partes para los filtros seleccionados.")
        return

    total_hours = sum(float(item["horas"]) for item in rows)
    unique_days = len({item["fecha"] for item in rows})
    unique_workers = len({item["trabId"] for item in rows})
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Horas totales", f"{total_hours:.1f}")
    m2.metric("Partes", len(rows))
    m3.metric("Días", unique_days)
    m4.metric("Trabajadores", unique_workers)

    hours_by_worker = defaultdict(float)
    hours_by_category = defaultdict(float)
    for item in rows:
        hours_by_worker[safe_name(find_worker(state, item["trabId"]), "nombre", "Trabajador eliminado")] += float(item["horas"])
        hours_by_category[safe_name(find_category(state, item["catId"]), "nombre", "Categoría eliminada")] += float(item["horas"])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Horas por trabajador")
        st.dataframe(
            [{"Trabajador": name, "Horas": round(hours, 1)} for name, hours in sorted(hours_by_worker.items(), key=lambda row: row[1], reverse=True)],
            use_container_width=True,
            hide_index=True,
        )
    with c2:
        st.markdown("#### Horas por categoría")
        st.dataframe(
            [{"Categoría": name, "Horas": round(hours, 1)} for name, hours in sorted(hours_by_category.items(), key=lambda row: row[1], reverse=True)],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Detalle")
    detail_rows = []
    for item in rows:
        worker = find_worker(state, item["trabId"])
        of_item = find_of(state, item["ofId"])
        category = find_category(state, item["catId"])
        detail_rows.append(
            {
                "Fecha": item["fecha"],
                "Trabajador": safe_name(worker, "nombre"),
                "OF": safe_name(of_item, "codigo"),
                "Proyecto": safe_name(of_item, "desc"),
                "Categoría": safe_name(category, "nombre"),
                "Horas": item["horas"],
                "Observaciones": item["obs"],
            }
        )
    st.dataframe(detail_rows, use_container_width=True, hide_index=True)

    if current_user["rol"] == "admin":
        selection = {part_label(state, item): item["id"] for item in rows}
        selected_label = st.selectbox("Edición administrativa de parte", list(selection.keys()))
        selected = next(item for item in rows if item["id"] == selection[selected_label])
        if st.button("Eliminar parte seleccionado", key="admin_delete_part"):
            def mutate(remote_state: dict[str, Any]) -> None:
                before = len(remote_state["partes"])
                remote_state["partes"] = [item for item in remote_state["partes"] if item["id"] != selected["id"]]
                if len(remote_state["partes"]) == before:
                    raise RuntimeError("El parte seleccionado ya no existe.")
            try:
                apply_remote_change(config, f"Admin borra parte {selected['id']}", mutate)
            except Exception as exc:
                st.error(str(exc))
            else:
                _set_flash("Parte borrado por administración.")
                st.rerun()


def _render_admin_tab(config: GitHubRepoConfig, state: dict[str, Any], current_user: dict[str, Any]) -> None:
    if current_user["rol"] != "admin":
        st.info("Solo administradores.")
        return

    st.subheader("Administración")
    workers_tab, ofs_tab, categories_tab = st.tabs(["Trabajadores", "OF / Proyectos", "Categorías"])

    with workers_tab:
        with st.form("add_worker_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                name = st.text_input("Nombre")
            with c2:
                username = st.text_input("Usuario")
            with c3:
                pin = st.text_input("PIN", type="password")
            with c4:
                role = st.selectbox("Rol", ["trabajador", "admin"])
            submitted = st.form_submit_button("Añadir trabajador", type="primary")
        if submitted:
            def mutate(remote_state: dict[str, Any]) -> None:
                if not name.strip() or not username.strip() or not pin.strip():
                    raise RuntimeError("Nombre, usuario y PIN son obligatorios.")
                if any(item["usuario"] == username.strip() for item in remote_state["trabajadores"]):
                    raise RuntimeError("Ese usuario ya existe.")
                remote_state["trabajadores"].append(
                    {
                        "id": uid(),
                        "nombre": name.strip(),
                        "usuario": username.strip(),
                        "pinHash": hash_pin(pin.strip()),
                        "rol": role,
                    }
                )
            try:
                apply_remote_change(config, f"Alta trabajador {username.strip()}", mutate)
            except Exception as exc:
                st.error(str(exc))
            else:
                _set_flash("Trabajador añadido.")
                st.rerun()

        for worker in state["trabajadores"]:
            with st.expander(f"{worker['nombre']} · {worker['usuario']} · {worker['rol']}"):
                c1, c2 = st.columns(2)
                with c1:
                    new_pin = st.text_input("Nuevo PIN", type="password", key=f"pin_{worker['id']}")
                    if st.button("Actualizar PIN", key=f"pin_button_{worker['id']}"):
                        def mutate(remote_state: dict[str, Any]) -> None:
                            if not new_pin.strip():
                                raise RuntimeError("El PIN no puede estar vacío.")
                            target = find_worker(remote_state, worker["id"])
                            if not target:
                                raise RuntimeError("El trabajador ya no existe.")
                            target["pinHash"] = hash_pin(new_pin.strip())
                        try:
                            apply_remote_change(config, f"Actualizar PIN {worker['usuario']}", mutate)
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            _set_flash("PIN actualizado.")
                            st.rerun()
                with c2:
                    if st.button("Cambiar rol", key=f"role_button_{worker['id']}"):
                        def mutate(remote_state: dict[str, Any]) -> None:
                            target = find_worker(remote_state, worker["id"])
                            if not target:
                                raise RuntimeError("El trabajador ya no existe.")
                            target["rol"] = "admin" if target["rol"] != "admin" else "trabajador"
                        try:
                            apply_remote_change(config, f"Cambiar rol {worker['usuario']}", mutate)
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            _set_flash("Rol actualizado.")
                            st.rerun()
                    if worker["id"] != current_user["id"] and st.button("Eliminar trabajador", key=f"delete_worker_{worker['id']}"):
                        def mutate(remote_state: dict[str, Any]) -> None:
                            if any(part["trabId"] == worker["id"] for part in remote_state["partes"]):
                                raise RuntimeError("No se puede eliminar: el trabajador tiene partes asociados.")
                            remote_state["trabajadores"] = [
                                item for item in remote_state["trabajadores"] if item["id"] != worker["id"]
                            ]
                        try:
                            apply_remote_change(config, f"Eliminar trabajador {worker['usuario']}", mutate)
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            _set_flash("Trabajador eliminado.")
                            st.rerun()

    with ofs_tab:
        with st.form("add_of_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                code = st.text_input("Código OF")
            with c2:
                desc = st.text_input("Descripción")
            with c3:
                company = st.text_input("Empresa")
            c4, c5, c6 = st.columns(3)
            with c4:
                customer = st.text_input("Cliente")
            with c5:
                distributor = st.text_input("Distribuidor")
            with c6:
                budget_hours = st.number_input("Horas previstas", min_value=0.0, step=0.5)
            submitted = st.form_submit_button("Añadir OF", type="primary")
        if submitted:
            def mutate(remote_state: dict[str, Any]) -> None:
                if not code.strip() or not desc.strip():
                    raise RuntimeError("Código y descripción son obligatorios.")
                if any(item["codigo"] == code.strip() for item in remote_state["ofs"]):
                    raise RuntimeError("Ese código OF ya existe.")
                remote_state["ofs"].append(
                    {
                        "id": uid(),
                        "codigo": code.strip(),
                        "desc": desc.strip(),
                        "empresa": company.strip(),
                        "cliente": customer.strip(),
                        "distribuidor": distributor.strip(),
                        "horasPrev": float(budget_hours),
                    }
                )
            try:
                apply_remote_change(config, f"Alta OF {code.strip()}", mutate)
            except Exception as exc:
                st.error(str(exc))
            else:
                _set_flash("OF añadida.")
                st.rerun()

        for item in state["ofs"]:
            with st.expander(f"{item['codigo']} — {item['desc']}"):
                st.write(
                    f"Empresa: {item['empresa'] or '—'} · Cliente: {item['cliente'] or '—'} · "
                    f"Distribuidor: {item['distribuidor'] or '—'} · Horas previstas: {item['horasPrev']}"
                )
                if st.button("Eliminar OF", key=f"delete_of_{item['id']}"):
                    def mutate(remote_state: dict[str, Any]) -> None:
                        if any(part["ofId"] == item["id"] for part in remote_state["partes"]):
                            raise RuntimeError("No se puede eliminar: la OF tiene partes asociados.")
                        remote_state["ofs"] = [row for row in remote_state["ofs"] if row["id"] != item["id"]]
                    try:
                        apply_remote_change(config, f"Eliminar OF {item['codigo']}", mutate)
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        _set_flash("OF eliminada.")
                        st.rerun()

    with categories_tab:
        with st.form("add_category_form", clear_on_submit=True):
            name = st.text_input("Nueva categoría")
            submitted = st.form_submit_button("Añadir categoría", type="primary")
        if submitted:
            def mutate(remote_state: dict[str, Any]) -> None:
                if not name.strip():
                    raise RuntimeError("La categoría no puede estar vacía.")
                remote_state["categorias"].append({"id": uid(), "nombre": name.strip()})
            try:
                apply_remote_change(config, f"Alta categoria {name.strip()}", mutate)
            except Exception as exc:
                st.error(str(exc))
            else:
                _set_flash("Categoría añadida.")
                st.rerun()

        for item in state["categorias"]:
            parts_count = sum(1 for part in state["partes"] if part["catId"] == item["id"])
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(f"**{item['nombre']}** · {parts_count} partes")
            with c2:
                if st.button("Eliminar", key=f"delete_cat_{item['id']}"):
                    def mutate(remote_state: dict[str, Any]) -> None:
                        if any(part["catId"] == item["id"] for part in remote_state["partes"]):
                            raise RuntimeError("No se puede eliminar: la categoría tiene partes asociados.")
                        remote_state["categorias"] = [
                            row for row in remote_state["categorias"] if row["id"] != item["id"]
                        ]
                    try:
                        apply_remote_change(config, f"Eliminar categoria {item['nombre']}", mutate)
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        _set_flash("Categoría eliminada.")
                        st.rerun()


def _render_database_tab(config: GitHubRepoConfig, state: dict[str, Any], sha: str | None) -> None:
    st.subheader("Base de datos GitHub")
    st.write(
        "Esta aplicación ya no usa OneDrive para persistencia principal. "
        "Al entrar, carga `partes_horas_db.json` desde GitHub y cada cambio se intenta guardar en el mismo archivo."
    )
    st.json(
        {
            "repository": config.repository,
            "branch": config.branch,
            "db_path": config.db_path,
            "write_access": config.has_write_access,
            "sha": sha,
            "last_saved": state["meta"].get("last_saved"),
        }
    )
    st.download_button(
        "Descargar copia JSON",
        data=json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="partes_horas_db.json",
        mime="application/json",
        use_container_width=True,
    )
    st.markdown("#### Secrets requeridos en Streamlit")
    st.code(
        '\n'.join(
            [
                'GITHUB_TOKEN = "ghp_..."',
                f'GITHUB_REPOSITORY = "{config.repository}"',
                f'GITHUB_BRANCH = "{config.branch}"',
                f'GITHUB_DB_PATH = "{config.db_path}"',
            ]
        ),
        language="toml",
    )
    if not config.has_write_access:
        st.error(
            "La aplicación está en modo solo lectura. Añade `GITHUB_TOKEN` en Streamlit Secrets "
            "con permisos de Contents: write sobre el repositorio."
        )


def _render_legacy_tab() -> None:
    st.subheader("Portal HTML legado")
    st.info("Se mantiene embebido como referencia funcional del diseño original orientado a OneDrive.")
    components.html(_legacy_portal_cache(), height=1100, scrolling=True)


def main() -> None:
    st.set_page_config(
        page_title="Portal de Partes, Tiempos y Proyectos",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    config = get_github_config()
    analysis = _analysis_cache()
    try:
        db = GitHubJsonDatabase(config)
        state, sha = db.load_state()
    except Exception as exc:
        st.title("⏱️ Portal de Partes, Tiempos y Proyectos")
        st.error(f"No se pudo cargar la base de datos remota: {exc}")
        st.info("Revisa `GITHUB_REPOSITORY`, `GITHUB_BRANCH` y `GITHUB_DB_PATH`.")
        return

    current_user = None
    current_user_id = st.session_state.get("current_user_id")
    if current_user_id:
        current_user = find_worker(state, current_user_id)
        if not current_user:
            st.session_state.pop("current_user_id", None)

    _render_sidebar(config, state, sha, current_user)

    st.title("⏱️ Portal de Partes, Tiempos y Proyectos")
    st.caption(
        "Sincronización basada en GitHub sobre `partes_horas_db.json`, siguiendo el patrón de credenciales por entorno de AI-FACTORY v2."
    )
    _show_flash()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pestañas originales", len(analysis.tabs))
    m2.metric("Categorías base", len(state["categorias"]))
    m3.metric("Partes registrados", len(state["partes"]))
    m4.metric("Modo de persistencia", "GitHub JSON")

    if not current_user:
        _login_screen(state)
        st.markdown("#### Arquitectura actual")
        st.write(", ".join(analysis.capabilities))
        return

    tabs = st.tabs(["Nuevo parte", "Consulta", "Administración", "Base de datos", "Portal legado"])
    with tabs[0]:
        _render_new_part_tab(config, state, current_user)
    with tabs[1]:
        _render_query_tab(config, state, current_user)
    with tabs[2]:
        _render_admin_tab(config, state, current_user)
    with tabs[3]:
        _render_database_tab(config, state, sha)
    with tabs[4]:
        _render_legacy_tab()


if __name__ == "__main__":
    main()
