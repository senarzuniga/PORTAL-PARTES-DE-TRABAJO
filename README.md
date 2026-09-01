# IS-PARTES-TRABAJO

Aplicación Streamlit independiente para partes de trabajo, control de tiempos y seguimiento por OF/proyecto.

## Arquitectura de persistencia

La app ya no depende de OneDrive como base principal. Ahora usa:

- `partes_horas_db.json` como base de datos operativa
- GitHub Contents API como backend de lectura/escritura
- `GITHUB_TOKEN` para guardar cambios desde Streamlit
- carga automática del JSON remoto cada vez que entra el usuario

Este patrón sigue el protocolo visto en `AI-FACTORY-v2`: credenciales por entorno/secrets, repositorio explícito y escritura mediante GitHub API.

## Archivos clave

- `streamlit_app.py`: aplicación principal autocontenida
- `partes_horas_db.json`: base de datos operativa remota
- `portal_partes.html`: portal legado de referencia
- `tests/test_portal_partes_service.py`: tests del modelo de datos y compatibilidad
- `.streamlit/config.toml`: configuración visual/base
- `.github/workflows/smoke.yml`: validación CI

## Requisitos

- Python 3.10 o superior
- pip

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Secrets requeridos en Streamlit Community Cloud

En **App settings → Secrets**:

```toml
GITHUB_TOKEN = "ghp_..."
GITHUB_REPOSITORY = "senarzuniga/PORTAL-PARTES-DE-TRABAJO"
GITHUB_BRANCH = "main"
GITHUB_DB_PATH = "partes_horas_db.json"
```

El token debe tener permisos de **Contents: write** sobre el repositorio.

## Publicación en Streamlit Community Cloud

1. Repositorio: `senarzuniga/PORTAL-PARTES-DE-TRABAJO`
2. Branch: `main`
3. Main file path: `streamlit_app.py`
4. Deploy

## Funcionamiento esperado

- al entrar en la app, se lee `partes_horas_db.json` desde GitHub
- cada alta/modificación/borrado reescribe el JSON en GitHub
- los demás usuarios ven los cambios al entrar o al sincronizar

## Limitaciones

- escribir en el mismo repositorio puede disparar redeploys de Streamlit Cloud
- la concurrencia sigue siendo de documento único; si dos usuarios editan a la vez puede haber conflicto de versión SHA
- el portal HTML legado se conserva solo como referencia

## Validación

```bash
python -m unittest tests.test_portal_partes_service -q
python -m py_compile streamlit_app.py tests/test_portal_partes_service.py
```
