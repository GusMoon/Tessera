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

### Modelos y servicios

| Elemento | Uso | Licencia / condiciones | Confianza |
|---|---|---|---|
| Qwen2.5-3B-Instruct (Q4_K_M, vía Ollama) | LLM local predeterminado del prototipo | Pendiente de revisar. [Suposición] Los modelos de Qwen2.5 de 3B usan la «Qwen Research License», que podría no ser permisiva; los de otros tamaños usan Apache-2.0. Revisar la tarjeta del modelo antes de adoptarlo (regla 8). | [Suposición] |
| Modelos `:free` de OpenRouter | Solo pruebas durante el desarrollo; no son dependencia del prototipo | Cada modelo trae su propia licencia y condiciones de uso; revisarlas al elegir los IDs. | [Probable] |

Historial: la v1 del prototipo usaba Inter y Space Grotesk (OFL-1.1). Se retiraron al adoptar el sistema visual v2 (`docs/UI-ESTRUCTURA-VISUAL-v2.md`).
