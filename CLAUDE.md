# CLAUDE.md

Guía para Claude Code (y para quien se sume al equipo) en el repositorio de Tessera. Si algo de aquí contradice una instrucción directa del usuario, gana la instrucción del usuario.

## Qué es Tessera

Cotizador comercial con IA para empresas de construcción y suministro de materiales (piloto planteado en Mérida). El vendedor pide una cotización en lenguaje natural; el sistema recupera historial parecido, propone tres escenarios (económico, recomendado, premium) con números calculados por código, una persona los revisa y aprueba, y se genera un PDF con las fuentes citadas.

**Contexto real:** es un proyecto universitario de aprendizaje, planteado como si saliera al mercado. No hay empresa ni datos reales; todo se prueba con datos sintéticos o públicos. El objetivo es aprender sobre modelos de IA (RAG, evaluación, memoria, tool calling). Equipo de 5 personas.

**Alcance del MVP (un mes):** cotizador vertical primero. La plataforma de búsqueda y memoria se generaliza después.

## Reglas que no se rompen

1. **El modelo no calcula.** Precios, márgenes, impuestos y totales salen de SQL y de código determinista (herramienta `calcular_cotizacion`). El LLM redacta, decide qué herramienta usar y explica.
2. **Todo número y toda afirmación llevan fuente.** Cada respuesta cita los documentos o filas usadas. Sin fuente, se dice que no hay.
3. **Nada sale sin aprobación humana.** No existe ruta de código que genere el PDF final sin una aprobación registrada.
4. **No se entrena ni se ajusta el modelo en el MVP.** El «aprendizaje» es RAG, memoria persistente y retroalimentación de cotizaciones aprobadas o editadas. El ajuste fino (LoRA) es un ejercicio opcional de la semana 4, solo para comparar.
5. **La memoria es visible y editable.** Cada hecho guardado tiene origen y fecha, y el usuario puede verlo, corregirlo y borrarlo.
6. **Permisos antes de recuperar.** Se filtra por fecha y por permisos del usuario antes de buscar; el agente no usa lo que el usuario no puede abrir.
7. **Nada de datos reales ni secretos en el repositorio.** Solo datos sintéticos o públicos. Nunca subir claves, tokens ni archivos de una empresa real.
8. **Licencias permisivas.** No usar dependencias AGPL (por ejemplo iText, MinIO). Revisar la licencia de cada modelo y librería nueva antes de agregarla y anotarla en `docs/licencias.md`.
9. **No se promete lo que no se midió.** Latencia, exactitud y calidad de recuperación se reportan con números del script de evaluación y el hardware usado.

## Estructura del repositorio

| Ruta | Contenido | Responsable |
|---|---|---|
| `data/synthetic/` | Datos sintéticos «sucios» y su generador | A |
| `data/eval/` | 50 casos de evaluación escritos a mano | Todos (10 c/u) |
| `ingest/` | Lectores de Excel, PDF, chats; sincronización incremental | A |
| `db/` | Esquema SQL (`schema.sql`) y migraciones ligeras (`_migrar` en `database.py`) | A |
| `retrieval/` | Embeddings, búsqueda híbrida, reranking | B |
| `eval/` | Script de evaluación, latencia y comparativa de modelos | B |
| `agent/tools/` | Herramientas del agente | C |
| `agent/memory/` | Memoria persistente y retroalimentación | C |
| `api/` | API | D |
| `web/` | Interfaz web (ver `docs/UI-ESTRUCTURA-VISUAL-v2.md`; el original `UI-ESTRUCTURA-VISUAL.md` se conserva) | D |
| `documents/` | Generación de PDF y plantillas | D |
| `tests/e2e/` | Pruebas de extremo a extremo | E |
| `docs/` | Documentación, licencias, decisiones | E |

Roles: A datos e ingesta, B búsqueda y evaluación, C agente y memoria, D producto y despliegue, E negocio, privacidad y calidad. Si una tarea cruza capas, se acuerda el contrato primero y se escribe en `docs/contratos.md`.

## Stack (propuesta, aún por confirmar)

- Base de datos: SQLite (archivo único) con FTS5 para texto y FAISS para vectores, según el «Plan de Prototipado a Escala» [Certeza: lo define el plan, 23/11/2026]. PostgreSQL con pgvector queda como camino para escalar, no para el prototipo.
- Modelos: LLM abierto cuantizado y modelo de embeddings multilingüe, servidos localmente con llama.cpp u Ollama. Se eligen con el set de evaluación propio, no por popularidad.
- Lenguaje de backend: Python 3.11+ con FastAPI [Certeza: ya implementado y elegido en el plan].
- Interfaz: web con React, TypeScript y Vite [Certeza: ya implementada y elegida en el plan].
- Despliegue: Docker Compose, un solo comando para levantar todo.
- PDF: ReportLab (BSD) [Certeza: ya es dependencia del proyecto].

Pendiente de confirmar: el LLM local (ver licencia de Qwen2.5-3B en `docs/licencias.md`).

## Comandos

Interfaz (`web/`; consume la API, así que necesita el backend arriba para tener datos):

```
cd web
npm install
npm run dev      # http://localhost:5173
npm run build    # revisa tipos y empaqueta
npm test         # pruebas de cálculo, paridad con el backend, mapeo de la API y formato
```

Configuración de la API de IA (Python; `agent/llm/`, ver `docs/contratos.md`):

```
py -3.13 -m venv .venv                   # una sola vez (cualquier Python 3.11+)
.venv\Scripts\activate                   # Windows; en Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                   # y llena .env localmente; nunca se versiona
python -m pytest                         # pruebas con mocks, sin red
python scripts/verificar_llm.py          # envía una pregunta de prueba al proveedor de LLM_PROVIDER
python scripts/probar_llm.py             # chat por terminal; /archivo <ruta> adjunta txt, csv, xlsx, pdf o imágenes (/ayuda)
python scripts/probar_llm.py --proveedor openrouter --modelo <id>:free -a archivo -p "pregunta"   # una sola pregunta
```

Nota: `baidu/ernie-5.5-flash-preview:free` solo acepta texto (verificado en el catálogo de OpenRouter el 22/11/2026);
para imágenes usa `--modelo` con uno de visión, p. ej. `nvidia/nemotron-3.5-super-vl:free`.

Búsqueda y cotización (Hito 2; ver `docs/hitos.md` y `docs/contratos.md`):

```
pip install -r requirements.txt          # incluye faiss-cpu y sentence-transformers (la primera vez baja multilingual-e5-small, ~0.5 GB)
python scripts/indexar.py                # reindexa la base actual (fragmentos + FTS5 + vectores); --embedder hash para no usar el modelo
python eval/evaluar.py                   # 50 casos: latencia, exactitud de totales, top-5 y fuentes; guarda eval/resultados/*.json
python eval/evaluar.py --demo --con-llm  # además prueba la redacción con MODO_DEMO y con el LLM de .env (fuera del veredicto)
python eval/referencia.py --actualizar   # recalcula los totales esperados de data/eval/casos.json (si el equipo edita los casos)
```

La API reindexa sola, en segundo plano, después de cargar fuentes. `TESSERA_EMBEDDER=hash` evita cargar el modelo (solo para pruebas).

Levantar la aplicación completa (dos terminales, desde la raíz del repositorio):

```
# Terminal 1 · backend (http://127.0.0.1:8000, documentación en /docs)
.venv\Scripts\python -m uvicorn api.main:app --port 8000
# Terminal 2 · interfaz (http://localhost:5173; /api se redirige al backend)
cd web && npm install && npm run dev
# Compilar la interfaz para producción: cd web && npm run build   (genera web/dist)
```

El chat usa el proveedor de `LLM_PROVIDER` en `.env` (con OpenRouter: `LLM_PROVIDER=openrouter`). Las cotizaciones las calcula código; el modelo solo redacta notas (con `MODO_DEMO=true` usa respuestas precargadas y no gasta cuota).

Primer recorrido (Hito 3): en el selector de usuario de la barra superior elige **Laura Canché (Administrador)** → Fuentes → «Cargar dataset sintético». Luego, en el chat, pide «Cotiza 20 gabinetes NEMA 4X 40x30x20 con instalación y flete a Mérida», abre la revisión, edita una cantidad y, como **Marcos Díaz (Responsable comercial)**, aprueba y descarga el PDF. Los permisos por rol están en `docs/permisos.md`; elegir usuario no es iniciar sesión.

Para el resto del sistema, documentar aquí (y mantener al día):

```
# Por definir
# levantar todo:        docker compose up
# migraciones:          <comando>
# cargar datos de prueba: <comando>
# evaluación:           <comando>
```

Regla: cualquier persona debe poder levantar el proyecto desde cero con un solo comando y datos sintéticos.

## Convenciones

- **Idioma:** documentación, interfaz y mensajes al usuario en español de México. Nombres de código (variables, funciones, rutas de API) en español o inglés, pero consistentes dentro del módulo; las rutas de API ya están definidas en español (`/cotizaciones`, `/fuentes`).
- **Formato:** moneda `$12,400.00 MXN`, fechas `dd/mm/aaaa` en interfaz y ISO 8601 en datos.
- **Dinero:** usar tipos decimales exactos, nunca números de punto flotante.
- **Cambios:** ramas cortas por tarea, pull request pequeño con descripción de qué cambia y cómo se probó. Otra persona revisa antes de fusionar.
- **Contratos entre capas:** no cambiar un contrato (herramientas del agente, rutas de API, esquema SQL) sin avisar a quienes lo consumen y actualizar `docs/contratos.md`.
- **Datos sintéticos:** el generador debe ser reproducible (semilla fija) y producir suciedad realista: formatos distintos, precios viejos, partidas duplicadas, notas sueltas.

## Evaluación

- 50 casos escritos a mano por el equipo (10 por persona), cada uno con la cotización que un vendedor experto habría hecho.
- Nunca usar el mismo modelo para generar datos y para evaluarlo.
- Métricas mínimas: exactitud de totales (debe ser 100 % por cálculo en código), recuperación (una cotización realmente parecida entre los primeros 5 resultados), latencia en el hardware real, porcentaje de cotizaciones aprobadas sin edición, y al menos una fuente citada por respuesta.
- Toda comparación de modelos o configuraciones se guarda en `eval/resultados/` con fecha, modelo y hardware.

## Decisiones abiertas (no asumir; preguntar)

1. Qué significa «local»: servidor de la empresa o PC del vendedor. (E + D)
2. «Sin puntaje» de la estrategia de patentes frente al ML de riesgo prometido. Mientras no se resuelva, la interfaz muestra el margen como dato calculado y no predice aceptación. (E + C)
3. Frontera entre precios (sí) e inventario (no). (E + C)
4. Cómo se marca y actualiza un precio desactualizado. (A + C)
5. Qué se guarda en memoria, quién lo valida y cómo se evita contaminar con cotizaciones malas. (C + E)
6. Lenguaje y herramientas del equipo. (Gustavo)
7. Objetivo real de latencia: se fija después de medir en la semana 1.

La lista completa con responsables y semanas está en el plan del MVP.

## Fuera del MVP

ML de predicción de aceptación, lectura de chats de WhatsApp (solo si sobra tiempo), conectores a SharePoint o Drive, multiempresa, ajuste fino como funcionalidad, versión móvil completa.

## Cómo trabajar aquí con Claude

- Antes de proponer una arquitectura nueva, revisar las reglas de arriba y las decisiones abiertas.
- Ante una duda de alcance, preguntar; no ampliar el MVP por iniciativa propia.
- Marcar la confianza cuando se hagan afirmaciones técnicas que no se verificaron ([Certeza], [Probable], [Suposición]), sobre todo en documentación para el equipo.
- No dar por terminado un cambio sin una prueba o una corrida del script de evaluación que lo respalde, o decir claramente que no se probó.
