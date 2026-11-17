# Tessera web (prototipo visual)

Base visual de la interfaz según `docs/UI-ESTRUCTURA-VISUAL.md`. **No hay backend**: todo funciona con datos sintéticos en memoria (`src/data/ejemplo.ts`) y al recargar se reinicia.

```
npm install
npm run dev      # http://localhost:5173
npm run build    # revisa tipos y empaqueta
npm test         # pruebas de cálculo y formato de dinero
```

## Qué incluye
Chat con respuesta simulada y citas, Revisión de cotización con tabla editable y recálculo, Cotizaciones, Fuentes, Memoria, Bitácora (con CSV) y Ajustes; modo claro/oscuro; estados cargando, vacío, error y parcial.

Para revisar estados de pantalla agrega `?estado=cargando`, `?estado=error` o `?estado=vacio` a Cotizaciones, Fuentes, Memoria o Bitácora.

## Estructura
- `src/lib/calculo.ts`: simula `calcular_cotizacion` (enteros de centavos, sin flotantes). Los totales nunca salen de un modelo.
- `src/lib/dinero.ts`: formato `$12,400.00 MXN`, fechas `dd/mm/aaaa`, antigüedad de precios.
- `src/state/Almacen.tsx`: estado global; se reemplaza por llamadas a la API (`/cotizaciones`, `/fuentes`, `/memoria`, `/bitacora`).
- `src/components/`, `src/pages/`, `src/styles/` (tokens claro/oscuro en `tokens.css`).

## Lo que es simulado
Respuestas del chat, PDF (solo un aviso), reprocesar fuentes, latencias de la bitácora y el usuario activo (Marcos Díaz, Responsable comercial). Ninguna cifra de latencia o exactitud de este prototipo es una medición.
