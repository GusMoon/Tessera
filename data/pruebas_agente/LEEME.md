# Documentos ficticios para probar el agente

Todo es sintético: los clientes, el proveedor y las cifras son inventados. Los archivos los genera `python data/synthetic/generar_documentos_prueba.py` (determinista: no usa azar). Los artículos de las solicitudes salen del catálogo sintético, así que **primero carga el dataset** (Fuentes → «Cargar dataset sintético», como Laura Canché).

## Cómo usarlos

- **Las solicitudes de clientes (`solicitud_*`) se adjuntan en el chat**, no en Fuentes. En Fuentes solo van el catálogo, el tarifario, el historial y las fichas: ahí un Excel se toma como historial y un PDF como ficha técnica, así que una solicitud subida ahí se rechaza o no sirve para cotizar.
- **Adjunta el archivo con el clip (o arrástralo al chat) y pulsa Enviar**, con o sin mensaje. Si trae materiales con cantidades, el sistema lo lee (sin modelo), busca los precios en las fuentes cargadas y arma los tres escenarios; el cliente sale del propio archivo. Si no trae renglones con cantidad (una imagen, una nota), se lo deja al modelo de conversación.
- **Primero carga el dataset** (Fuentes → «Cargar dataset sintético», como Laura Canché) o no habrá precios que citar.
- Puedes adjuntar varios a la vez (hasta 5): se juntan en una sola cotización.
- También sirve pegar el texto de la columna «Para pegar» de abajo, que es el mismo contenido.

## Solicitudes de clientes (para adjuntar en el chat)

| Archivo | Formato | Qué prueba |
|---|---|---|
| `solicitud_01_hotel_costa_dorada.pdf` | PDF con tabla | Lectura de un PDF formal; instalación y flete a Progreso |
| `solicitud_02_constructora_peninsular.xlsx` | Excel | Lectura de una hoja de cálculo; hay precios de catálogo con más de 6 meses |
| `solicitud_03_taller_los_pinos.txt` | Texto estilo WhatsApp | Lenguaje informal, flete a Umán |
| `solicitud_04_obra_progreso.csv` | CSV | Otro orden de columnas; instalación de canalización y 2 viajes de flete |

### Para pegar en el chat, con el resultado esperado

Totales con IVA, en pesos. Los calculó la app y los cotejé contra `eval/referencia.py` (implementación independiente): coinciden los tres escenarios de las cuatro cotizaciones, tanto con el texto pegado como adjuntando el archivo correspondiente (hay una prueba automática de esto: `tests/unit/test_solicitud_archivos.py`).

| Para pegar | Económico | Recomendado | Premium |
|---|---|---|---|
| `Para Hotel Costa Dorada: 12 gabinetes NEMA 4X intemperie 40x30x20, 30 rollos de cable THW calibre 12 negro, 60 tramos de tubo conduit pared delgada 3/4 y 120 coples conduit pared delgada 3/4. Con instalación. Flete a Progreso.` | $107,100.85 | $114,938.34 | $132,318.37 |
| `Para Constructora Peninsular: 24 interruptores termomagnéticos 1P 20A, 6 interruptores termomagnéticos 1P 30A, 3 centros de carga 4 polos bifásico, 40 contactos dúplex aterrizados, 30 apagadores sencillos y 35 placas con chasis 3 módulos. Flete a Mérida.` | $15,686.44 | $16,834.08 | $25,055.59 |
| `Para Taller Los Pinos: 3 reflectores LED 50W intemperie y 10 luminarias LED gabinete 2x18W 1.20m. Flete a Umán.` | $6,709.52 | $7,200.44 | $14,523.17 |
| `Para Obra Progreso: 8 varillas de tierra Copperweld 5/8 con conector, 10 rollos de cable THW calibre 8 verde y 40 tramos de tubo conduit pared gruesa 1 pulg. Instalación de canalización. Flete a Progreso, 2 viajes.` | $75,162.39 | $80,662.11 | $94,841.89 |

El escenario premium incluye siempre los opcionales «Supervisión en obra» y «Garantía extendida». La de Constructora Peninsular debe mostrar el aviso de precios con más de 6 meses.

## Mensajes cortos para probar que el agente no inventa

| Para pegar | Qué debe pasar |
|---|---|
| `10 cables calibre 12` | Pregunta cuál: hay un cable rojo (`CAB-THW-12R`) y uno negro (`CAB-THW-12N`). No cotiza. |
| `50 metros de cable THW calibre 12 negro` | Pregunta cuántos **rollos**: el catálogo lo vende por rollo, no por metro. |
| `20 turbinas de helicóptero` | Dice que no lo encontró en el catálogo y sugiere artículos parecidos. No cotiza. |
| `20 interruptores termomagnéticos 1P 20A` | Cotiza ($4,613.55 / $4,951.11 / $12,063.92) y avisa que `INT-TM-120` tiene más de 6 meses; en la revisión sale ámbar con ⚠. |

Estos resultados salieron de una corrida con el embedder de respaldo (`TESSERA_EMBEDDER=hash`) y una base temporal. **No los corrí con el modelo e5 que usa tu app**; si algún renglón se interpreta distinto con e5, dímelo.

## Fuentes de prueba (para subir en Fuentes como Administrador)

| Archivo | Qué prueba | Resultado esperado al subirlo |
|---|---|---|
| `fuente_proveedor_ferreteria_maya.csv` | Un segundo catálogo, de otro proveedor | Leídas 8, guardadas 6, rechazadas 2 (una sin SKU, otra con precio negativo), con su motivo en «Rechazos» |
| `fuente_politica_comercial_interna.pdf` | Permisos (regla 6) | Ver abajo: debe subirse con permiso «Administración» |

Tras subir el catálogo del proveedor se puede cotizar, por ejemplo: `4 registros eléctricos de concreto 40x40x40 y 2 rollos de cable THHW calibre 14 rojo`. Debe salir completa y los totales de las cotizaciones de arriba no cambian (lo comprobé con las dos fuentes cargadas).

### Subir la política con permiso «Administración»

La pantalla de Fuentes no tiene selector de permiso, así que esta se sube por la API (con el backend en el puerto 8000; `u3` es Laura Canché, Administrador):

```
curl.exe -X POST http://127.0.0.1:8000/api/fuentes/subir -H "X-Usuario-Id: u3" -F "file=@data/pruebas_agente/fuente_politica_comercial_interna.pdf" --form-string "permiso=Administración"
```

Comprobé la carga con ese permiso y la búsqueda directamente sobre el código: la política solo aparece entre los resultados del Administrador (`u3`), no en los del Vendedor (`u1`). **No ejecuté este comando `curl` contra el servidor**; si la ruta o el acento dan problema en tu terminal, dímelo.

Si subes la política sin el permiso (desde la pantalla), quedará como «Todos» y cualquiera podrá usarla: es un buen contraste.
