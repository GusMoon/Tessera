# Tessera: estructura visual de la app web (v2)

> **Versión 2 (11/11/2026).** Rediseño visual y de experiencia. La estructura, las rutas y las reglas de producto no cambian; cambian el sistema visual (§8), la pantalla de Revisión (§5.2), Memoria y Bitácora como líneas de tiempo (§5.5 y §5.6) y el selector de tema (§9). El documento original se conserva en `UI-ESTRUCTURA-VISUAL.md`. La referencia visual fue solo un punto de partida de patrones; no se copió su identidad.

Documento de arranque para el desarrollo de la interfaz. Complementa el [Plan del MVP](https://claude.ai/artifact/WLCD5meRsXG7K5R38Kicoi) y el [Mapa del prototipo](https://claude.ai/artifact/Ho7w2J9UEa4Khub1wDsF55).

Etiquetas: **[Decidido]** ya acordado, **[Propuesta]** recomendación a confirmar, **[Pendiente]** depende de una decisión abierta.

---

## 1. Principios de la interfaz

1. **El chat es la puerta de entrada, pero el resultado es una cotización, no un mensaje.** Al terminar, el usuario ve una pantalla de revisión, no solo texto. [Decidido]
2. **Todo número tiene origen.** Cada cifra muestra de dónde salió (documento, fila SQL o cálculo). Nada se presenta como hecho sin fuente. [Decidido]
3. **Nada sale sin aprobación humana.** El botón de generar el PDF final solo se activa después de aprobar. [Decidido]
4. **La memoria es visible y editable.** El usuario puede ver, corregir y borrar lo que el sistema recuerda. [Decidido]
5. **Funciona con datos incompletos.** Debe mostrar estados vacíos, precios desactualizados y fuentes faltantes sin romperse. [Propuesta]
6. **Español de México, pesos MXN, fechas dd/mm/aaaa.** [Propuesta]

## 2. Usuarios y tareas

| Usuario | Tarea principal | Pantalla donde vive |
|---|---|---|
| Vendedor | Pedir y revisar cotizaciones | Chat y Revisión |
| Responsable comercial | Aprobar, editar márgenes, ver historial | Revisión y Cotizaciones |
| Administrador | Cargar fuentes, ver estado de ingesta, permisos | Fuentes y Ajustes |

[Pendiente] Los roles finales los define la Persona E en la matriz de permisos (semana 2). Hasta entonces la interfaz asume estos tres.

## 3. Mapa de navegación

```
Tessera
├─ Chat                     /               (pantalla inicial)
├─ Cotizaciones             /cotizaciones
│   └─ Detalle y revisión   /cotizaciones/:id
├─ Fuentes                  /fuentes
├─ Memoria                  /memoria
├─ Bitácora                 /bitacora
└─ Ajustes                  /ajustes        (usuarios, roles, modelo, datos)
```

Navegación principal: barra lateral izquierda fija en escritorio, menú inferior en móvil.

## 4. Estructura de página (escritorio)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Barra superior: nombre de empresa · búsqueda global · usuario        │
├────────────┬───────────────────────────────────────┬─────────────────┤
│ Barra      │                                       │ Panel lateral   │
│ lateral    │          Área principal               │ derecho         │
│            │                                       │ (fuentes,       │
│ Chat       │                                       │  detalle,       │
│ Cotizac.   │                                       │  memoria        │
│ Fuentes    │                                       │  relacionada)   │
│ Memoria    │                                       │                 │
│ Bitácora   │                                       │ Se abre y       │
│ Ajustes    │                                       │ cierra          │
├────────────┴───────────────────────────────────────┴─────────────────┤
│ Barra de estado: modelo activo · estado de ingesta · latencia última │
└──────────────────────────────────────────────────────────────────────┘
```

- Ancho de la barra lateral: 220 px, colapsable a 64 px (solo iconos).
- Panel derecho: 360 px, se abre al seleccionar una fuente o una cotización.
- Ancho máximo de lectura del chat: 760 px, centrado en el área principal.
- Mínimo soportado: 1024 px de ancho. Tablet horizontal y móvil son de segunda prioridad. [Propuesta]

## 5. Pantallas

### 5.1 Chat (inicio)

```
┌─────────────────────────────────────────────────┬──────────────────┐
│  Nueva conversación                [Historial ▾]│ Fuentes usadas   │
│                                                 │                  │
│  Tú:                                            │ ▸ Cot. 0412      │
│  Cotiza 20 gabinetes metálicos con instalación  │   12/03/2026     │
│  y transporte a Mérida                          │ ▸ Ficha GM-200   │
│                                                 │ ▸ Cot. 0388      │
│  Tessera:                                       │                  │
│  Encontré 4 cotizaciones parecidas. Preparé     │ Memoria aplicada │
│  tres escenarios.                               │ • Cliente X pide │
│  ┌─────────────────────────────────────────┐    │   flete aparte   │
│  │ Resumen: Económico · Recomendado · Premium│  │                  │
│  │ [Abrir revisión]                         │    │                  │
│  └─────────────────────────────────────────┘    │                  │
│                                                 │                  │
│  ┌───────────────────────────────────────────┐  │                  │
│  │ Escribe tu solicitud…              [Enviar]│ │                  │
│  └───────────────────────────────────────────┘  │                  │
└─────────────────────────────────────────────────┴──────────────────┘
```

Componentes:
- **Mensajes** con avatar, texto y, cuando aplica, una **tarjeta de cotización** embebida con botón «Abrir revisión».
- **Citas numeradas** en el texto (por ejemplo `[1]`) que abren la fuente en el panel derecho.
- **Indicador de herramientas**: línea discreta «Buscando cotizaciones… Calculando totales…» mientras el agente trabaja.
- **Campo de entrada** con envío por Enter y salto de línea con Mayús+Enter. Adjuntar archivo queda fuera del MVP.
- **Sugerencias iniciales** en la conversación vacía: 3 ejemplos de solicitudes reales.

### 5.2 Revisión de cotización (la pantalla más importante)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Cotización #0123 · Borrador               [Rechazar] [Aprobar y PDF] │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────┐ ┌─────────────────┐ ┌────────────┐                   │
│  │ Económico  │ │ ★ Recomendado   │ │ Premium    │   ← pestañas      │
│  └────────────┘ └─────────────────┘ └────────────┘                   │
│                                                                      │
│  Partidas                                                            │
│  ┌─────────────────────┬──────┬───────────┬──────────┬────────────┐  │
│  │ Concepto            │ Cant │ P. unit.  │ Importe  │ Fuente     │  │
│  ├─────────────────────┼──────┼───────────┼──────────┼────────────┤  │
│  │ Gabinete metálico   │  20  │ $4,850.00 │ $97,000  │ Cot. 0412  │  │
│  │ Instalación         │  20  │   $620.00 │ $12,400  │ Cot. 0388  │  │
│  │ Transporte a Mérida │   1  │ $3,900.00 │  $3,900  │ ⚠ 14 meses │  │
│  └─────────────────────┴──────┴───────────┴──────────┴────────────┘  │
│                                                                      │
│  Subtotal · IVA · Total                       Margen estimado: 18 %  │
│                                                                      │
│  Notas del agente (editable)                                         │
│  Alternativas y riesgos detectados                                   │
│                                                                      │
│  Historial de cambios de esta cotización                             │
└──────────────────────────────────────────────────────────────────────┘
```

**Cambios de la v2:**
- **Pasos del ciclo** arriba a la derecha: Borrador → En revisión → Aprobada (o Rechazada). Es una secuencia real, por eso van numerados.
- **Traza de antigüedad** junto a cada fuente: una barra de 0 a 18 meses con una marca en el umbral de 6. El tramo pasa a ocre al superarlo y el texto con los meses siempre se muestra (el estado no depende solo del color).
- **Dock de aprobación** flotante y fijo abajo: total y acción principal siempre visibles. «Aprobar y PDF» solo abre el diálogo de confirmación.
- **Total** en serif grande; rueda hacia su nuevo valor al recalcularse (con movimiento reducido, cambia sin animar).
- **Historial** como línea de tiempo vertical.
- **Móvil (< 760 px):** cada partida pasa de fila a tarjeta; nada se corta.

Reglas:
- Las **tres pestañas** (Económico, Recomendado, Premium) muestran la misma estructura de tabla para comparar fácil. «Recomendado» abre seleccionada.
- Las celdas de cantidad, precio y notas **son editables**. Al editar, el total se recalcula con código y se marca la celda como «editada por [usuario]».
- Cada partida muestra su **fuente**. Si el precio tiene más de 6 meses, aparece el aviso ⚠ con la antigüedad. [Propuesta] El umbral de 6 meses se confirma con la Persona A (precios históricos).
- El **margen** se muestra como dato calculado, nunca como predicción de aceptación. [Pendiente] Depende de resolver «puntaje vs ML» (pendiente #2 del plan).
- «Aprobar y PDF» abre un diálogo de confirmación con el resumen y registra quién aprobó. Después descarga el PDF y marca la cotización como Aprobada.
- Al aprobar o editar, el sistema pregunta una vez: «¿Guardar este ajuste como aprendizaje?» (alimenta retroalimentación y memoria).

### 5.3 Lista de cotizaciones

Tabla con filtros arriba.

| Columna | Detalle |
|---|---|
| Folio | #0123, enlace al detalle |
| Cliente | texto |
| Fecha | dd/mm/aaaa |
| Total | MXN, alineado a la derecha, cifras tabulares |
| Estado | Borrador, En revisión, Aprobada, Rechazada |
| Creada por | usuario |

Filtros: estado, fecha, cliente, texto libre. Orden por defecto: más reciente primero. Estado vacío: «Aún no hay cotizaciones. Pide la primera en el chat».

### 5.4 Fuentes

Administración de lo que el sistema conoce.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Fuentes                                        [Conectar carpeta]    │
├──────────────────────────────────────────────────────────────────────┤
│ Resumen:  312 documentos · 298 listos · 9 procesando · 5 con error   │
│                                                                      │
│ ┌────────────────────┬────────┬────────────┬──────────┬────────────┐ │
│ │ Archivo            │ Tipo   │ Actualizado│ Estado   │ Acciones   │ │
│ ├────────────────────┼────────┼────────────┼──────────┼────────────┤ │
│ │ cotizaciones_q1.xlsx│ Excel │ 03/11/2026 │ ● Listo  │ Reprocesar │ │
│ │ ficha_gm200.pdf    │ PDF    │ 28/10/2026 │ ◐ Procesa│            │ │
│ │ chat_cliente.txt   │ Chat   │ 01/11/2026 │ ✕ Error  │ Ver motivo │ │
│ └────────────────────┴────────┴────────────┴──────────┴────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

- Estados con icono y texto, nunca solo color: Listo, Procesando, Error, Omitido.
- «Ver motivo» muestra el error legible (por ejemplo «PDF escaneado sin texto, falta OCR»).
- Los permisos de cada fuente se muestran como etiqueta (Todos, Comercial, Administración). [Pendiente] Matriz de permisos de la Persona E.

### 5.5 Memoria

Línea de tiempo (v2) de los hechos que el sistema recuerda, del más reciente al más antiguo, con fecha relativa («hace 6 días») junto a la fecha exacta.

| Campo | Ejemplo |
|---|---|
| Hecho | «El cliente X siempre pide el flete aparte» |
| Origen | Conversación del 05/11/2026 · Cot. 0398 |
| Fecha | 05/11/2026 |
| Estado | Activa, Pausada |
| Acciones | Editar, Pausar, Borrar |

Los hechos nuevos aparecen con la etiqueta «Por confirmar» hasta que un usuario autorizado los acepta. [Propuesta] Esto evita que una cotización mal hecha contamine las siguientes (pendiente #7 del plan).

### 5.6 Bitácora

Registro de solo lectura (v2: línea de tiempo agrupada por día), filtrable por fecha, usuario y cotización. Cada entrada muestra: qué se preguntó, qué documentos se recuperaron, qué herramientas se usaron, cuánto tardó y quién aprobó. Exportable a CSV.

### 5.7 Ajustes

Secciones: Usuarios y roles, Modelo activo (solo lectura en el MVP), Datos y privacidad (qué se guarda, borrar todo), Preferencias de formato.

## 6. Componentes reutilizables

| Componente | Uso | Notas |
|---|---|---|
| Tarjeta de cotización | Chat y listas | Folio, cliente, total, estado |
| Tabla editable | Revisión | Celdas con estado «editada», recalcula total |
| Chip de fuente | Citas | Abre el panel derecho |
| Aviso de antigüedad | Precios | Icono + «14 meses», nunca solo color |
| Insignia de estado | Cotizaciones, fuentes | Texto + icono |
| Panel lateral deslizante | Detalle de fuente, memoria | 360 px |
| Diálogo de confirmación | Aprobar, borrar memoria | Siempre dice qué pasará |
| Estado vacío | Toda lista | Dice qué falta y cómo empezar |
| Traza de antigüedad | Fuentes de partidas, tarjeta de cotización, tabla de Fuentes | Barra 0–18 meses, marca en 6; texto con los meses |
| Pasos de estado | Revisión | Secuencia numerada del ciclo de la cotización |
| Dock de aprobación | Revisión | Total y acción principal siempre visibles |
| Cifra animada | Totales | Rueda al recalcular; valor final exacto para lectores de pantalla |
| Chip de fecha | Listas y líneas de tiempo | dd/mm/aaaa más lectura relativa |
| Selector de tema | Barra superior y Ajustes | Claro, Sistema, Oscuro |
| Notificación breve (toast) | Éxito y error leves | Desaparece en 5 s, no tapa acciones |

## 7. Estados que toda pantalla debe cubrir

1. **Cargando**: esqueletos que imitan el contenido, no ruedas girando solas.
2. **Vacío**: mensaje útil y acción siguiente.
3. **Error**: qué falló, qué hacer, botón para reintentar.
4. **Parcial**: datos incompletos (por ejemplo fuente sin permiso); se muestra lo disponible y se avisa lo que falta.
5. **Largo**: el agente puede tardar. Mostrar progreso por herramienta y permitir cancelar. [Pendiente] La latencia real se mide en la semana 1; hasta entonces se diseña para esperas de hasta 60 s.

## 8. Sistema visual (v2)

[Propuesta] Herramienta de trabajo con carácter propio. Concepto: **el tiempo deja trazas en los precios**; lo único memorable es la traza de antigüedad y todo lo demás se mantiene en silencio. Paneles flotantes redondeados sobre un fondo de cal.

### Color

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--bg` | `#EDF0F1` (cal) | `#0E1520` | Fondo de página |
| `--surface` | `#FBFCFC` (papel) | `#151E2B` | Tarjetas, tablas, paneles |
| `--surface-2` | `#E3E8EA` | `#0A1019` | Campos y fondos hundidos |
| `--fg` | `#1B2A41` (tinta índigo) | `#E6EBF1` | Texto |
| `--muted` | `#4F5E70` | `#9AA8B8` | Texto secundario |
| `--line` / `--line-strong` | `#D3DADD` / `#B4BFC5` | `#263446` / `#3A4C62` | Bordes |
| `--accent` | `#1A6F81` (azul maya) | `#5CC0D4` | Acción principal, enlaces, traza al día |
| `--ok` | `#1E7B4B` | `#5FD08F` | Listo, aprobada |
| `--warn` | `#9A5B00` (ocre) | `#F0B04A` | Precio antiguo, por confirmar |
| `--error` | `#B3261E` | `#F28B82` | Errores, rechazada |

Contrastes calculados (WCAG): los 36 pares texto/fondo usados (texto, secundario, acento, estados y botón primario, en claro y oscuro) superan 4.5:1. [Certeza]
Nota: el acento claro pasó de `#1F7A8C` (propuesto, 4.35:1 sobre cal) a `#1A6F81` para cumplir el mínimo.

### Tipografía

- Titulares, total y frases destacadas: **Newsreader** (serif, licencia OFL-1.1).
- Interfaz, tablas y cuerpo: **Hanken Grotesk** (sans, OFL-1.1).
- Ambas verificadas con cifras tabulares en el navegador (mismo ancho en «1111» y «0000»). [Certeza]
- Escala: 12 / 14 / 16 / 20 / 32 / 44 px. El de 44 es solo para el total. Cuerpo de tabla 14 px, chat 16 px.
- Sin etiquetas en mayúsculas ni monoespaciada para etiquetas; el código de herramientas usa monoespaciada del sistema.

### Espaciado y forma

- Base de 4 px; usar 8, 12, 16, 24, 32, 48.
- Radios jerárquicos: 6 px controles, 16 px superficies (tarjetas, tablas), 24 px elementos flotantes (barra lateral, panel derecho, dock, diálogos), píldora para chips y el botón principal del dock.
- Bordes de 1 px en reposo; sombra solo en lo flotante (dock, panel, diálogos, avisos), con tinte índigo.

### Movimiento

- Responde a acciones: el total rueda al recalcular, las sugerencias del chat se desplazan al pasar el cursor, el panel y los diálogos entran con una transición corta.
- Un solo momento orquestado: las trazas se dibujan una vez al abrir una cotización.
- Todo se desactiva con `prefers-reduced-motion`.

## 9. Accesibilidad y formato

- Contraste mínimo 4.5:1 en texto. El estado nunca depende solo del color.
- Todo es operable con teclado; foco visible; el chat se envía con Enter.
- **Tema:** selector de tres opciones (Claro, Sistema, Oscuro) en la barra superior y en Ajustes; se maneja con flechas, la elección se recuerda y el cambio de colores se suaviza unos 300 ms (sin animación con movimiento reducido).
- Moneda: `$12,400.00 MXN`. Fechas: `dd/mm/aaaa`. Separador de miles: coma, decimal: punto.
- Textos de la interfaz en español claro, orientados al usuario («Aprobar», «Pedir cotización»), sin términos internos («embedding», «pgvector»).

## 10. Conexión con la API

| Pantalla | Endpoint (borrador) |
|---|---|
| Chat | `POST /chat` (respuesta en flujo) |
| Lista de cotizaciones | `GET /cotizaciones` |
| Revisión | `GET /cotizaciones/{id}`, `PATCH /cotizaciones/{id}/partidas/{n}` |
| Aprobar | `POST /cotizaciones/{id}/aprobar` |
| Fuentes | `GET /fuentes`, `POST /fuentes/{id}/reprocesar` |
| Memoria | `GET /memoria`, `PATCH /memoria/{id}`, `DELETE /memoria/{id}` |
| Bitácora | `GET /bitacora` |

[Propuesta] Los contratos exactos se escriben en la semana 1 (Persona D con las demás). Este cuadro es el punto de partida.

## 11. Stack de interfaz sugerido

[Suposición] React con TypeScript y Vite; componentes propios o una librería sin licencia restrictiva; tablas con una librería MIT. Se confirma cuando el equipo diga qué lenguajes maneja (pendiente #12 del plan).

## 12. Orden de construcción

1. Estructura base: barra lateral, barra superior y rutas con pantallas vacías.
2. Chat con respuestas simuladas (datos de ejemplo) para validar el diseño antes del backend.
3. Revisión de cotización con tabla editable y recálculo.
4. Lista de cotizaciones y detalle.
5. Fuentes y estado de ingesta.
6. Memoria y bitácora.
7. Ajustes, modo oscuro y pulido.

## 13. Fuera del MVP

- Subida de archivos desde el chat.
- Gráficas y paneles de métricas.
- Colaboración en tiempo real.
- Versión móvil completa (solo se garantiza que no se rompa).
- Personalización de marca por empresa.
