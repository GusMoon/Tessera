# Licencias de dependencias

Regla 8 de `CLAUDE.md`: solo licencias permisivas; nada AGPL. Cada librería o modelo nuevo se anota aquí antes de agregarlo.

Etiquetas de confianza: [Certeza] verificado, [Probable] por conocimiento general, [Suposición] sin verificar.

## Interfaz web (`web/`)

| Paquete | Uso | Licencia | Confianza |
|---|---|---|---|
| react, react-dom | Interfaz | MIT | [Certeza] |
| react-router-dom | Rutas | MIT | [Certeza] |
| vite, @vitejs/plugin-react | Servidor de desarrollo y empaquetado | MIT | [Certeza] |
| typescript | Tipos | Apache-2.0 | [Certeza] |
| vitest | Pruebas unitarias | MIT | [Certeza] |
| @fontsource/newsreader (Newsreader) | Tipografía de titulares y total, servida localmente | OFL-1.1 | [Certeza] |
| @fontsource/hanken-grotesk (Hanken Grotesk) | Tipografía de interfaz, servida localmente | OFL-1.1 | [Certeza] |

Verificado el 11/11/2026 leyendo el campo `license` del `package.json` de cada paquete instalado en `web/node_modules`. Los paquetes @fontsource declaran OFL-1.1 (la licencia de las fuentes); se usan sin modificarlas.

## Backend Python (configuración de la API de IA)

| Paquete | Uso | Licencia | Confianza |
|---|---|---|---|
| openai | SDK compatible con OpenAI para Ollama y OpenRouter | Apache-2.0 | [Certeza] |
| pydantic-settings (y pydantic) | Carga de variables de entorno y `.env` | MIT | [Certeza] |
| python-dotenv (dependencia de pydantic-settings) | Lectura de `.env` | BSD-3-Clause | [Certeza] |
| httpx (dependencia de openai) | Cliente HTTP | BSD-3-Clause | [Certeza] |
| pytest | Pruebas (solo desarrollo) | MIT | [Certeza] |

Verificado el 21/11/2026 leyendo los metadatos de licencia de cada paquete instalado en `.venv`.

## Búsqueda híbrida (Hito 2)

| Paquete / modelo | Uso | Licencia | Confianza |
|---|---|---|---|
| faiss-cpu 1.16.0 | Índice de vectores | MIT | [Certeza] metadatos del paquete |
| sentence-transformers 6.3.0 | Carga del modelo de embeddings | Apache-2.0 | [Certeza] metadatos del paquete |
| torch 2.15.0 (dependencia de la anterior) | Cálculo de tensores en CPU | BSD-3-Clause y otras permisivas (Apache-2.0, MIT, Zlib…) | [Certeza] metadatos del paquete |
| transformers 5.24.0, huggingface_hub 2.4.0 (dependencias) | Carga de modelos | Apache-2.0 | [Certeza] metadatos del paquete |
| numpy 2.5.5 | Vectores y cálculo | BSD-3-Clause (y 0BSD, MIT, Zlib, CC0) | [Certeza] metadatos del paquete |
| `intfloat/multilingual-e5-small` | Embeddings multilingües de la búsqueda semántica | MIT | [Certeza] campo `license: mit` de su tarjeta en Hugging Face (leída el 23/11/2026) |
| FTS5 (SQLite 3.49.1) | Búsqueda por palabras (BM25) | Dominio público | [Probable] |

Verificado el 23/11/2026. No se revisó la licencia de cada dependencia transitiva de torch más allá del metadato del paquete.

### Modelos y servicios

| Elemento | Uso | Licencia / condiciones | Confianza |
|---|---|---|---|
| Qwen2.5-3B-Instruct (Q4_K_M, vía Ollama) | LLM local predeterminado del prototipo | **No adoptar todavía.** Una búsqueda del 23/11/2026 confirmó que la etiqueta de licencia del modelo en Hugging Face es `qwen-research` (no Apache-2.0). No se leyó el texto de esa licencia: [Probable] que limite el uso comercial, lo que contradice la regla 8. Antes de usarlo en una demostración pública, leer `LICENSE` en la tarjeta del modelo o elegir uno con licencia permisiva (de Qwen2.5 suelen ser Apache-2.0 los de otros tamaños: [Suposición], verificar). | [Probable] |
| Groq (plan gratuito) + `openai/gpt-oss-20b` | Solo pruebas durante el desarrollo; no son dependencia del prototipo | El modelo es de pesos abiertos de OpenAI [Probable: Apache-2.0; revisar la tarjeta del modelo antes de adoptarlo]. El servicio tiene sus propios términos de uso y límites por organización; usar solo datos sintéticos (regla 7) y sin registrar tarjeta. | [Probable] |
| Modelos `:free` de OpenRouter | Solo pruebas durante el desarrollo; no son dependencia del prototipo | Cada modelo trae su propia licencia y condiciones de uso; revisarlas al elegir los IDs. | [Probable] |

Historial: la v1 del prototipo usaba Inter y Space Grotesk (OFL-1.1). Se retiraron al adoptar el sistema visual v2 (`docs/UI-ESTRUCTURA-VISUAL-v2.md`).
