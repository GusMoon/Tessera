# Lista de verificación de hitos

Cada hito del «Plan de Prototipado a Escala» es binario y lo respalda un script que imprime números. Solo se reporta lo medido (regla 9 de `CLAUDE.md`). Etiquetas: [Certeza] medido en esta máquina, [Probable] inferido, [Suposición] sin verificar.

Hardware de las mediciones: Intel Core i5-13420H (8 núcleos, 12 hilos), 23.7 GB de RAM, Windows 11, Python 3.13.3, solo CPU.

## Hito 1 · Entrada (datos) — APROBADO

Script: `python verificar_ingesta.py` (corrida del 23/11/2026) [Certeza].

| Criterio | Meta | Medido |
|---|---|---|
| Filas válidas guardadas | 100 % | catálogo 47, historial 115, fichas 10 y tarifario 15, todos iguales al manifiesto |
| Filas defectuosas rechazadas con motivo | 8 de 8 | 8 de 8 detectadas con su motivo |
| Tiempo de ingesta | menos de 60 s | 0.35 s |

Además: 11 precios con más de 6 meses y 2 partidas duplicadas detectados. El generador produce 13 archivos (con el tarifario de servicios, que no está en el documento del plan).

## Hito 2 · Proceso (búsqueda híbrida y cálculo de escenarios) — APROBADO con reservas

Script: `python eval/evaluar.py` sobre los 50 casos de `data/eval/casos.json`. Resultado guardado en `eval/resultados/2026-11-23_multilingual-e5-small.json` [Certeza].

| Criterio | Meta | Medido con e5 (corrida guardada) |
|---|---|---|
| Recuperación híbrida + cálculo de 3 escenarios, mediana | menos de 500 ms | 199.7 ms (p95 304.7 ms, máximo 370.0 ms) |
| Exactitud de totales | 50 de 50 | 50 de 50 |
| Cotización parecida entre los primeros 5 resultados | al menos 80 % | 100 % (50 de 50); en primer lugar, 66 % |
| Respuestas con al menos una fuente | 100 % | 100 % |

**Variación de la latencia:** en cuatro corridas completas la mediana fue 149 a 263 ms (tres de ellas entre 250 y 263 ms; la guardada, 200 ms), así que cita el rango y no un solo valor [Certeza]. La carga del modelo e5 tarda 29 a 38 s al arrancar y no entra en esa mediana; indexar los 109 fragmentos tarda 4 a 7 s [Certeza]. Con el embedder de respaldo (`--embedder hash`) la misma evaluación da 50 de 50, 100 % en el top-5, 80 % en primer lugar y 25.6 ms de mediana.

**Reservas que debes leer antes de presumir este número:**

1. **Los 50 casos los redactó Claude, no el equipo.** El documento pide 10 por persona. Están marcados «pendiente de revisión» y se usaron mientras se desarrollaba el intérprete, así que no son un conjunto reservado: con ellos encontré y corregí varios errores del intérprete (por ejemplo, no entendía «Instalación incluida»).
2. **El top-5 es optimista.** El historial tiene 28 folios y varios casi idénticos (por ejemplo 0101, 0113 y 0125 tienen los mismos artículos), y el catálogo y el historial usan las mismas descripciones. El embedder de respaldo, sin entender sinónimos, también llega a 100 %: esta evaluación no demuestra que el modelo e5 aporte mejora.
3. **Las reglas de negocio son sintéticas:** el precio del catálogo es el costo, la instalación se cotiza por categoría, y los opcionales premium entran siempre al escenario premium. El equipo debe validarlas (decisión abierta 3).
4. **No hay medición del LLM como parte del veredicto.** Con Groq (`openai/gpt-oss-20b`) se redactaron 3 casos sin descartes (0.8 a 2.1 s) y con `MODO_DEMO` 0.1 a 0.2 s; son pruebas de humo, no una evaluación de calidad de la redacción.
5. El tool calling nativo del modelo no se usa ni se midió: el código encadena las herramientas.

Pruebas: `python -m pytest` (219 pruebas, sin red) y `npm test` en `web/` (24 pruebas, incluida la paridad de la calculadora con el backend) [Certeza].

## Hito 3 · Salida (revisión, aprobación y PDF) — PENDIENTE

No iniciado. Falta: rutas de cotizaciones, memoria, bitácora y usuarios en la API; PDF con ReportLab bloqueado hasta que exista una aprobación registrada (regla 3); y conectar la interfaz a la API para que Revisión use datos reales (ámbar con ⚠ para precios de más de 6 meses, recálculo en menos de 1 s, «Aprobar y PDF» bloqueado).
