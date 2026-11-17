// Simula la herramienta `calcular_cotizacion` (regla 1 de CLAUDE.md): el cálculo es código
// determinista con enteros; ninguna cifra la produce un modelo.

import type { Centavos } from './dinero';

export const TASA_IVA_PORCIENTO = 16;

export interface LineaCalculo {
  cantidad: number; // entero >= 0
  precioUnitario: Centavos;
  costoUnitario: Centavos;
}

export interface ResultadoCalculo {
  importes: Centavos[];
  subtotal: Centavos;
  iva: Centavos;
  total: Centavos;
  costo: Centavos;
  margen: Centavos;
  /** Margen sobre el subtotal en puntos base (1 825 = 18.25 %). null si el subtotal es 0. */
  margenPuntosBase: number | null;
}

/** División entera con redondeo de medio hacia afuera del cero. */
export function divRedondeada(numerador: number, denominador: number): number {
  const signo = Math.sign(numerador);
  const n = Math.abs(numerador);
  return signo * Math.floor((2 * n + denominador) / (2 * denominador));
}

export function calcularCotizacion(
  lineas: LineaCalculo[],
  tasaIvaPorciento: number = TASA_IVA_PORCIENTO,
): ResultadoCalculo {
  const importes = lineas.map((l) => l.cantidad * l.precioUnitario);
  const subtotal = importes.reduce((a, b) => a + b, 0);
  const iva = divRedondeada(subtotal * tasaIvaPorciento, 100);
  const costo = lineas.reduce((a, l) => a + l.cantidad * l.costoUnitario, 0);
  const margen = subtotal - costo;
  return {
    importes,
    subtotal,
    iva,
    total: subtotal + iva,
    costo,
    margen,
    margenPuntosBase: subtotal === 0 ? null : divRedondeada(margen * 10000, subtotal),
  };
}

export function formatoMargen(puntosBase: number | null): string {
  if (puntosBase === null) return '—';
  return `${(puntosBase / 100).toFixed(1)} %`;
}
