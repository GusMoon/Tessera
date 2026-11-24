# Contratos entre capas

Regla de `CLAUDE.md`: no cambiar un contrato sin avisar a quienes lo consumen y actualizar este archivo.
Etiquetas de confianza: [Certeza] verificado, [Probable] por conocimiento general, [Suposición] sin verificar.

## Proveedor de LLM (`agent/llm/`)

Quién lo ofrece: C (agente). Quién lo consume: agente, `eval/` (comparativa de modelos), `api/`.

```python
from agent.llm import crear_proveedor

proveedor = crear_proveedor()   # lee LLM_PROVIDER y el resto de .env
r = proveedor.completar([{"role": "user", "content": "..."}])
r.texto, r.modelo, r.proveedor, r.latencia_s   # `modelo` = el que realmente respondió
```

- Interfaz compatible con OpenAI (formato de chat). Proveedores: `ollama` (predeterminado, local), `openrouter` y `groq` (ambos solo desarrollo y pruebas; nunca dependencia obligatoria).
- Errores: todos heredan de `ErrorLLM` y su mensaje es apto para mostrarse al usuario (nunca contiene la clave).
- Variables de entorno: ver `.env.example`. La clave vive solo en `.env` local.
- Con `openrouter`, todos los IDs de `OPENROUTER_MODELS` deben terminar en `:free`; si no, falla al crear el proveedor.
- El modelo no calcula precios ni totales (regla 1): este contrato solo cubre redacción, decisión de herramienta y explicación.
- Gestión de tokens: `completar` aplica por defecto `max_tokens` (512), `temperature` (0.2) y recorte de historial (3000 tokens estimados), configurables con `LLM_MAX_TOKENS_SALIDA`, `LLM_TEMPERATURA` y `LLM_CONTEXTO_ENTRADA`. Cada respuesta trae `tokens_entrada` y `tokens_salida` reales (`usage`), y `proveedor.uso` acumula el total. La estimación de tokens es una heurística [Suposición]; el conteo real es el de `usage`.
- Contexto de dominio: `completar(..., sistema=PROMPT_SISTEMA_COTIZACIONES)` antepone el prompt de cotizaciones (~270 tokens, prefijo estable). Es opcional: quien llama decide cuándo pagarlo.
- Recortar historial descarta turnos viejos, no los resume; resumir y recordar corresponde a `agent/memory/`.
- Fuera de este contrato por ahora: streaming, tool calling y modo demo (`MODO_DEMO` solo se lee).

## Chat con el LLM (`api/chat.py`) — modo prueba

Quién lo ofrece: D (API) sobre `agent/llm/`. Quién lo consume: `web/` (pantalla Chat).

`POST /api/chat` — `multipart/form-data`:

| Campo | Tipo | Notas |
|---|---|---|
| `mensaje` | texto | obligatorio, no vacío |
| `historial` | texto JSON | `[{"rol": "usuario"\|"tessera", "texto": "..."}]`; solo se usan los últimos 20 |
| `archivos` | 0..5 archivos | txt, md, json, csv, xlsx, pdf, png, jpg, webp, gif; máx. 20 MB (imágenes 5 MB) |

Respuesta 200: `texto`, `modelo` (el que realmente respondió), `proveedor`, `latencia_s`, `tokens_entrada`, `tokens_salida`, `adjuntos[]` (`nombre`, `tipo`, `detalle`, `truncado`) y `avisos[]`.
Errores: cuerpo `{"detail": "<mensaje legible>"}`. 400 entrada inválida, 429 límite de uso del modelo, 502 modelo o clave rechazados, 503 configuración o red.

`GET /api/chat/config` — `proveedor`, `modelo`, `modelo_vision` (nunca la clave).

Contexto de fuentes: si la petición trae `X-Usuario-Id`, el prompt de sistema incluye cuántas filas hay cargadas por fuente (solo las que ese usuario puede abrir, regla 6) y cómo se pide una cotización (`agent/contexto.py`). Así el modelo no responde «no tengo acceso a ningún archivo» con un catálogo cargado. Son conteos, nunca precios.

- Sin estado: el cliente reenvía el historial (solo texto) y los archivos que quiera que el modelo vea en ese turno. Los archivos se leen en memoria y **no se guardan** (regla 7).
- Si algún archivo es imagen, se usa `OPENROUTER_MODEL_VISION` (u `OLLAMA_MODEL_VISION`) en lugar del modelo de texto. Debe terminar en `:free` con OpenRouter.
- Cada archivo de texto se recorta a 12,000 caracteres; se avisa en `avisos`.
- `max_tokens` de salida es al menos 2,048 [Probable]: los modelos de razonamiento gastan tokens pensando y con 512 la respuesta llega vacía.
- Alcance actual: el modelo responde solo con lo adjuntado. **Aún no consulta la base ni usa `calcular_cotizacion`**, así que sus cifras no son precios (reglas 1 y 2 pendientes de `retrieval/` y `agent/tools/`).


## Fuentes, permisos y usuarios de prueba (`ingest/`, `db/`, `api/main.py`)

Quién lo ofrece: A (datos e ingesta). Quién lo consume: `retrieval/`, `agent/tools/`, `web/` (pantalla Fuentes).

- `POST /api/fuentes/subir` — `multipart`: `file` y `permiso` opcional (`Todos` | `Comercial` | `Administración`; otro valor da 400). Sin `permiso` se asigna el predeterminado de su tipo: catálogo y fichas `Todos`; historial y tarifario `Comercial`.
- `GET /api/fuentes` y la respuesta de carga incluyen `permiso`.
- Tipos de archivo: CSV de catálogo, **CSV de servicios** (se reconoce por sus encabezados `Codigo, Servicio, Tipo, Precio_Unitario`; en `fuentes.tipo` sigue figurando como `CSV`), XLSX de historial y PDF de fichas.
- `POST /api/fuentes/limpiar` vacía solo lo cargado desde «Fuentes» y su índice. **Conserva** usuarios, cotizaciones, memoria y bitácora (las partidas de una cotización guardan su propia copia de la fuente).
- Tarifario de servicios: tabla `servicios` (`tipo` = Flete | Instalación | Opcional; `incluir_en` = todos | premium; `zona` para fletes).
- Usuarios de prueba (tabla `usuarios`, sin contraseñas): `u1` Ana Pérez (Vendedor), `u2` Marcos Díaz (Responsable comercial), `u3` Laura Canché (Administrador). **Prototipo:** la identidad llegará en la cabecera `X-Usuario-Id`; no es autenticación real [Certeza].
- Regla de acceso (propuesta, la confirma la Persona E): `Administración` solo la ve el Administrador; `Todos` y `Comercial` los ven los tres roles.
- Importes nuevos (cotizaciones, partidas, aprobaciones) se guardan en **centavos enteros**; las tablas de ingesta heredadas siguen en `REAL` y el cálculo las convierte con `Decimal`.
- Fecha de referencia del prototipo para medir antigüedad: `2026-11-21` (backend y frontend). «Más de 6 meses» significa 7 o más meses completos (`antiguedad_meses > 6`).

## Uso y cuota del modelo (`GET /api/chat/uso`)

Quién lo ofrece: D (API) sobre `agent/llm/uso.py`. Quién lo consume: `web/` (medidor en el Chat; luego Ajustes).

- Respuesta: `proveedor`, `modelo`, `tipo_limite` (`peticiones` con OpenRouter, `ninguno` con Ollama), `plan_gratuito`, `dia` (`usadas`, `limite`, `restantes`), `reinicio_dia_utc` (ISO 8601 UTC), `minuto` (`usadas_aqui`, `limite`, `segundos_para_liberar`), `sesion` (`llamadas`, `tokens_entrada`, `tokens_salida`, `tokens_total`) y `aviso`.
- **Los modelos `:free` de OpenRouter se limitan por peticiones, no por tokens** [Certeza: documentación de OpenRouter, 23/11/2026]: 20 por minuto y, por día UTC, 50 con menos de 10 créditos comprados o 1000 con 10 o más. Por eso «lo que queda» se expresa en solicitudes; los tokens de `sesion` son solo informativos (suma de `usage` desde que arrancó el backend).
- `dia` sale de `GET https://openrouter.ai/api/v1/key` (`free_model_daily_requests`), con caché de 15 s y sin exponer la clave ni su `label`. **OpenRouter refleja ese contador con ~30 s de retraso** [Certeza: medido]; la interfaz lo relee 35 s después de cada mensaje.
- `reinicio_dia_utc` es el siguiente 00:00 UTC (18:00 en Mérida, UTC-6) [Probable: la documentación dice «día UTC» pero no da la hora de corte].
- `minuto` es una **estimación**: cuenta solo las peticiones de esta app; otras apps con la misma clave no se ven. El límite por minuto no lo informa OpenRouter.
- Si no se puede consultar la cuota (sin red o clave inválida), `dia` es `null` y `aviso` lo explica; la estimación local sigue disponible.
- Un 429 de `POST /api/chat` trae la cabecera `Retry-After` (segundos) cuando OpenRouter informó `Retry-After` o `X-RateLimit-Reset`.
- El proxy de Vite apunta a `http://127.0.0.1:8000`; se cambia con la variable `TESSERA_API`.


## Proveedor Groq (`LLM_PROVIDER=groq`)

Quién lo ofrece: C (agente). Solo desarrollo y pruebas, igual que OpenRouter.

- Variables: `GROQ_API_KEY` (la clave vive solo en `.env`), `GROQ_MODEL` (predeterminado `openai/gpt-oss-20b`) y `GROQ_REASONING_EFFORT` (`low` | `medium` | `high`; predeterminado `low`; vacío = el del servicio).
- `openai/gpt-oss-20b` es un modelo de **razonamiento** de solo texto (131,072 tokens de contexto, herramientas y JSON). Con `low` piensa poco y gasta menos tokens; si se sube el esfuerzo, la respuesta tarda más y consume más del límite por minuto.
- **Límites del plan gratuito** [Probable: tabla de la documentación de Groq del 23/11/2026, que la propia documentación llama «resumen» y remite a la consola para los valores exactos]: `gpt-oss-20b` 30 peticiones por minuto, 1,000 por día, 8,000 tokens por minuto y 200,000 por día. Los límites son **por organización**, no por usuario ni por clave.
- Groq informa en las cabeceras de **cada respuesta** las peticiones restantes por día y los tokens restantes por minuto, con su tiempo de reinicio (`x-ratelimit-*`). El tope diario de tokens no viene en cabeceras. `GET /api/chat/uso` los expone en `dia` y `tokens_minuto`; antes del primer mensaje no hay datos (no se gasta una petición solo para leerlos).
- Sin modelo de visión gratuito en Groq: si un mensaje trae imágenes se envía por OpenRouter (`OPENROUTER_API_KEY` y `OPENROUTER_MODEL_VISION`); sin esa clave, la API responde 503 con la explicación.
- El tope de salida (`max_tokens`) en Groq es de al menos 1,024 (2,048 en OpenRouter): con 8,000 tokens por minuto, un tope alto agotaría el minuto con una sola petición. Un 413 de Groq significa que la petición excede el límite por minuto; se traduce a «adjunta un archivo más corto».
- **No registres método de pago** en Groq: sin tarjeta no se puede generar un cobro (el plan de pago se llama «Developer»).

## Búsqueda híbrida (`retrieval/`) — Hito 2

- **Fragmentos** (`fragmentos` + `fragmentos_fts`): se reconstruyen con `retrieval.fragmentos.construir_fragmentos(conn)`. Tipos y `ref` citable: `catalogo:SKU`, `servicio:CODIGO`, `historial:FOLIO`, `ficha:CODIGO#n`. Cada uno hereda el `permiso` de su fuente y lleva la `fecha` del dato.
- **Indexar:** `retrieval.servicio.reindexar(conn, embedder)` (o `python scripts/indexar.py`). La API reindexa sola, en segundo plano, tras `POST /api/fuentes/subir` y `POST /api/fuentes/cargar-dataset-sintetico`, y olvida el índice con `POST /api/fuentes/limpiar`. El índice vive en `data/index/` (no se versiona; `TESSERA_INDEX_DIR` lo cambia).
- **Buscar:** `Indice.buscar(conn, consulta, usuario_id, k=5, tipos=None, desde=None, vector=None) -> list[Resultado]`. Con `Resultado(fragmento, puntaje, rangos)`; `puntaje` es RRF (k = 60) y `rangos` dice la posición en `bm25` y/o `vector`.
- **Regla 6:** permisos del usuario, `tipos` y `desde` (fecha ISO mínima; los fragmentos sin fecha se conservan) se resuelven con SQL **antes** de buscar; FTS5 y FAISS solo ven los fragmentos permitidos. Matriz (propuesta, prototipo sin autenticación real): Vendedor y Responsable comercial → `Todos` y `Comercial`; Administrador → además `Administración`; un usuario inexistente → solo `Todos`.
- **Embedder:** `TESSERA_EMBEDDER=e5` (por defecto, `intfloat/multilingual-e5-small`) o `hash` (respaldo determinista, solo para pruebas). Todo reporte debe decir cuál se usó.

## Herramientas y cotización (`agent/`) — Hito 2

- **`calcular_cotizacion(lineas, margenes=None) -> {escenario: {...}}`** (`agent/tools/calcular_cotizacion.py`; sin LLM, solo enteros). Entrada: `Linea(tipo, codigo, concepto, unidad, cantidad:int≥1, costo_unitario_centavos:int, fuente_ref, fuente_fecha, antiguedad_meses, incluir_en)`. Márgenes por defecto en puntos base sobre el precio de venta: `economico` 1 200, `recomendado` 1 800, `premium` 2 500; `precio = costo / (1 − margen)` redondeado a centavo con medio hacia afuera del cero; IVA 16 %. Los servicios con `incluir_en = 'premium'` solo entran al escenario premium. Cada escenario trae `partidas` (con `precio_unitario_centavos`, `importe_centavos`, `fuente_ref`, `fuente_fecha`, `antiguedad_meses`, `precio_antiguo` si es mayor a 6 meses, `duplicada`) y `subtotal_centavos`, `iva_centavos`, `total_centavos`, `costo_centavos`, `margen_centavos`, `margen_puntos_base`. Reproduce `web/src/lib/calculo.ts`; la paridad se prueba con `tests/fixtures/calculo_casos.json` (copia en `web/src/lib/calculo_casos.fixture.json`).
- **`buscar_precios(...)`** y **`buscar_historial(...)`**: sobre `Indice.buscar`; devuelven `ref`, precio en centavos leído de SQLite (nunca del texto del fragmento), fecha y antigüedad.
- **`cotizar(solicitud, usuario_id, conn, indice) -> dict`** (`agent/cotizar.py`; camino determinista que mide el Hito 2). `estado` es `completa` o `requiere_aclaracion` (entonces `preguntas` trae lo que falta y `escenarios` es `None`: no se inventa). Trae también `avisos`, `fuentes` (cada `ref` usada, con fecha y antigüedad), `historial_parecido` (top-5 de folios), `renglones` (cómo se resolvió cada línea) y `tiempos_ms`.
- **`orquestar(...)`** (`agent/orquestador.py`): `cotizar` + redacción opcional. El LLM solo redacta `notas` y `riesgos` por escenario; si el texto trae una cifra que no está en el contexto entregado, se descarta y se avisa; si el modelo falla, queda el resultado determinista. `MODO_DEMO=true` lee `agent/demo/respuestas.json`. `resultado["redaccion"]` dice el `origen` (`llm`, `demo` o `determinista`).
- **Memoria** (`agent/memory/memoria.py`) y **bitácora** (`agent/bitacora.py`): módulos sin rutas HTTP (las rutas son del Hito 3). Solo los hechos activos y confirmados llegan al modelo; editar un hecho lo deja por confirmar otra vez.
- **Reglas de negocio sintéticas que valida el equipo:** el precio del catálogo es el costo; la instalación se cotiza por categoría (Gabinetes, Tableros, Canalización en metros por tramo, Iluminación, Protección); la zona mencionada incluye flete (con aviso); los opcionales premium entran siempre al escenario premium.

## Casos de evaluación (`data/eval/casos.json`)

`{"version", "nota", "casos": [{"id", "autor", "estado_revision", "solicitud", "renglones": [{"sku", "cantidad"}], "servicios": [{"codigo", "cantidad"}], "folio_parecido", "esperado": {escenario: {"subtotal_centavos", "iva_centavos", "total_centavos"}}}]}`. `esperado` lo calcula `eval/referencia.py --actualizar`, de forma independiente de `agent/tools`. Hoy son un borrador de Claude pendiente de revisión por el equipo.

## Cotizaciones, memoria y bitácora (`api/cotizaciones.py`, `api/panel.py`) — Hito 3

Todas las rutas (salvo `GET /api/usuarios`) exigen `X-Usuario-Id`; sin él, 401. Un rol sin permiso recibe 403 con el motivo (matriz en `docs/permisos.md`). Los importes son **centavos enteros**; los totales los calcula el servidor.

**Cotizaciones**

| Ruta | Qué hace | Rol |
|---|---|---|
| `POST /api/cotizaciones` `{solicitud, cliente?}` | Interpreta la solicitud con las fuentes cargadas. Responde `{"tipo": "cotizacion", cotizacion, avisos, tiempos_ms, redaccion}` (201, guardada como Borrador), `{"tipo": "aclaracion", preguntas, avisos}` (200, no se guarda) o `{"tipo": "conversacion"}` (200: no pide materiales con cantidad; que la atienda `/api/chat`). 409 si no hay fuentes cargadas. | todos |
| `POST /api/cotizaciones/desde-archivos` (multipart: `mensaje?`, `archivos` 1..5) | Cotiza lo que piden los archivos adjuntos (PDF, Excel, CSV o texto de chat), solos o junto con el mensaje. `agent/solicitud_archivos.py` los convierte, sin modelo, en renglones («12 piezas de …») y frases de servicio («flete a Progreso») para el mismo intérprete y la misma calculadora de `POST /api/cotizaciones`; el cliente sale del archivo («Cliente:», columna Obra, remitente del chat o título). Los archivos se leen en memoria y no se guardan. Misma respuesta que `POST /api/cotizaciones`, con un aviso «Se leyeron los archivos: …». Si no traen renglones con cantidad (una imagen, una nota) responde `{"tipo": "conversacion"}` y el chat los atiende. | todos |
| `GET /api/cotizaciones` · `GET /api/cotizaciones/{id}` | Lista (la más reciente primero) o detalle. | todos |
| `PATCH /api/cotizaciones/{id}/partidas/{partida_id}` `{cantidad?, precio_unitario_centavos?}` | Edita una partida (enteros; cantidad ≥ 1). La marca como «editada» y lo anota en el historial. 409 si ya no está en Borrador o En revisión; 422 si el valor no es válido. | todos |
| `PATCH /api/cotizaciones/{id}/escenarios/{economico\|recomendado\|premium}` `{notas}` | Edita las notas del agente. | todos |
| `POST /api/cotizaciones/{id}/enviar` | Borrador → En revisión. | todos |
| `POST /api/cotizaciones/{id}/aprobar` `{escenario}` | Registra la aprobación (quién, cuándo y el total) y deja la cotización Aprobada. | Responsable comercial, Administrador |
| `POST /api/cotizaciones/{id}/rechazar` `{motivo}` | Rechaza. | Responsable comercial, Administrador |
| `GET /api/cotizaciones/{id}/pdf` | PDF de la cotización aprobada (`application/pdf`). **409 si no hay aprobación registrada** (regla 3). | todos |

Detalle de cotización: `id`, `folio` («#0007»), `cliente`, `solicitud`, `fecha`, `estado`, `creada_por`, `escenario_aprobado`, `motivo_rechazo`, `aprobada_por`, `fecha_aprobacion`, `escenarios[e] = {notas, riesgos, margen_objetivo_puntos_base, partidas[], totales}`, `historial[]`, `avisos[]`, `parecidas[]` (cotizaciones históricas consultadas) y `fuentes{ref: {etiqueta, fecha, ubicacion, extracto, documento, permiso, restringido, disponible}}`. Cada partida lleva `fuente_ref`, `fuente_fecha`, `antiguedad_meses`, `precio_antiguo` y `editada_por`. El `extracto` de una fuente que el usuario no puede abrir llega `null` con `restringido: true`.

**Memoria:** `GET /api/memoria` (todos) · `POST /api/memoria {texto, origen?}` (todos; entra «por confirmar») · `PATCH /api/memoria/{id} {texto?, estado?}` · `POST /api/memoria/{id}/confirmar` · `DELETE /api/memoria/{id}` (estas tres, Responsable comercial y Administrador; editar el texto vuelve a dejar el hecho «por confirmar»).

**Bitácora:** `GET /api/bitacora` (un Vendedor ve solo sus entradas). **Usuarios:** `GET /api/usuarios` (sin identidad; alimenta el selector). **Ajustes:** `GET /api/ajustes` (modelo, `modo_demo`, embedder, fragmentos indexados, latencia de la última cotización y última evaluación guardada). **Datos de trabajo:** `DELETE /api/datos` (Administrador; borra cotizaciones, aprobaciones, memoria y bitácora, y conserva fuentes y usuarios).

**Fuentes:** `POST /api/fuentes/subir`, `POST /api/fuentes/cargar-dataset-sintetico` y `POST /api/fuentes/limpiar` ahora exigen Administrador.
