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

Historial: la v1 del prototipo usaba Inter y Space Grotesk (OFL-1.1). Se retiraron al adoptar el sistema visual v2 (`docs/UI-ESTRUCTURA-VISUAL-v2.md`).
