# IS-PARTES-TRABAJO

Aplicación Streamlit independiente para partes de trabajo, control de tiempos y seguimiento por OF/proyecto.

La visualización principal conserva el portal original [portal_partes.html](C:/Users/isena/Documents/GitHub/IS-PARTES-TRABAJO/portal_partes.html) y solo cambia la capa de persistencia.

## Arquitectura de persistencia

La app ya no depende de OneDrive como base principal. Ahora usa:

- `partes_horas_db.json` como base de datos operativa
- GitHub Contents API como backend de lectura/escritura
- un token de GitHub introducido en la pestaña **Base de datos** del propio portal para guardar cambios
- carga automática del JSON remoto cada vez que entra el usuario

Este patrón sigue el protocolo visto en `AI-FACTORY-v2`: repositorio explícito, archivo de datos explícito y escritura mediante GitHub API, pero sin exponer secrets del servidor de Streamlit al navegador.

## Archivos clave

- `streamlit_app.py`: contenedor Streamlit mínimo que embebe el portal original
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

## Publicación en Streamlit Community Cloud

1. Repositorio: `senarzuniga/PORTAL-PARTES-DE-TRABAJO`
2. Branch: `main`
3. Main file path: `streamlit_app.py`
4. Deploy

## Configuración de GitHub dentro de la app

En la pestaña **Base de datos** del portal:

1. Repositorio GitHub: `senarzuniga/PORTAL-PARTES-DE-TRABAJO`
2. Rama: `main`
3. Archivo JSON: `partes_horas_db.json`
4. Pega un token de GitHub con permisos de escritura de contenidos
5. Pulsa **Guardar configuración GitHub**

Si despliegas en Streamlit Community Cloud, puedes definir `github_token` en `st.secrets` o `GITHUB_TOKEN` como variable de entorno para que el token se aplique igual en todas las PCs.

## Funcionamiento esperado

- al entrar en la app, se lee `partes_horas_db.json` desde GitHub
- cada alta/modificación/borrado reescribe el JSON en GitHub si el navegador tiene token configurado
- los demás usuarios ven los cambios al entrar o al sincronizar

## Limitaciones

- escribir en el mismo repositorio puede disparar redeploys de Streamlit Cloud
- la concurrencia sigue siendo de documento único; si dos usuarios editan a la vez puede haber conflicto de versión SHA
- el token puede quedar guardado en el navegador o venir del secreto del despliegue

## Validación

```bash
python -m unittest tests.test_portal_partes_service -q
python -m py_compile streamlit_app.py tests/test_portal_partes_service.py
```
