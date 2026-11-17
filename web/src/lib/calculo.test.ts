import { describe, expect, it } from 'vitest';
import { calcularCotizacion, divRedondeada, formatoMargen } from './calculo';
import {
  diasDeAntiguedad,
  textoRelativo,
  formatoFecha,
  formatoMXN,
  formatoPesos,
  mesesDeAntiguedad,
  parsePesos,
} from './dinero';

describe('calcularCotizacion', () => {
  it('reproduce el ejemplo del documento de UI', () => {
    const r = calcularCotizacion([
      { cantidad: 20, precioUnitario: 485000, costoUnitario: 395000 },
      { cantidad: 20, precioUnitario: 62000, costoUnitario: 48000 },
      { cantidad: 1, precioUnitario: 390000, costoUnitario: 310000 },
    ]);
    expect(r.importes).toEqual([9700000, 1240000, 390000]);
    expect(r.subtotal).toBe(11330000);
    expect(r.iva).toBe(1812800);
    expect(r.total).toBe(13142800);
    expect(r.margenPuntosBase).toBe(1906);
  });

  it('redondea el IVA a centavos sin flotantes (medio hacia arriba)', () => {
    // 0.03 * 16 % = 0.0048 -> $0.00 ; $0.34 * 16 % = 0.0544 -> $0.05 ; $0.03 -> 0.5 se redondea a 1
    expect(calcularCotizacion([{ cantidad: 1, precioUnitario: 3, costoUnitario: 0 }]).iva).toBe(0);
    expect(calcularCotizacion([{ cantidad: 1, precioUnitario: 34, costoUnitario: 0 }]).iva).toBe(5);
    expect(calcularCotizacion([{ cantidad: 1, precioUnitario: 1125, costoUnitario: 0 }], 10).iva).toBe(113);
  });

  it('maneja subtotal cero y margen negativo', () => {
    expect(calcularCotizacion([]).margenPuntosBase).toBeNull();
    const r = calcularCotizacion([{ cantidad: 1, precioUnitario: 1000, costoUnitario: 1500 }]);
    expect(r.margenPuntosBase).toBe(-5000);
    expect(formatoMargen(r.margenPuntosBase)).toBe('-50.0 %');
  });

  it('divRedondeada respeta el signo', () => {
    expect(divRedondeada(5, 2)).toBe(3);
    expect(divRedondeada(-5, 2)).toBe(-3);
  });
});

describe('dinero', () => {
  it('formatea moneda y fechas con el estilo del proyecto', () => {
    expect(formatoMXN(1240000)).toBe('$12,400.00 MXN');
    expect(formatoPesos(5)).toBe('$0.05');
    expect(formatoPesos(123456789)).toBe('$1,234,567.89');
    expect(formatoFecha('2026-03-12')).toBe('12/03/2026');
  });

  it('interpreta texto de precios y rechaza lo inválido', () => {
    expect(parsePesos('4,850.5')).toBe(485050);
    expect(parsePesos('$620 MXN')).toBe(62000);
    expect(parsePesos('abc')).toBeNull();
    expect(parsePesos('1.234')).toBeNull();
    expect(parsePesos('-5')).toBeNull();
  });

  it('expresa fechas de forma relativa', () => {
    expect(textoRelativo('2026-11-11', '2026-11-11')).toBe('hoy');
    expect(textoRelativo('2026-11-10', '2026-11-11')).toBe('ayer');
    expect(textoRelativo('2026-11-06', '2026-11-11')).toBe('hace 5 días');
    expect(textoRelativo('2026-08-11', '2026-11-11')).toBe('hace 3 meses');
    expect(textoRelativo('2025-09-10', '2026-11-11')).toBe('hace 1 año');
    expect(diasDeAntiguedad('2026-03-01', '2026-03-31')).toBe(30);
  });

  it('calcula antigüedad en meses completos', () => {
    expect(mesesDeAntiguedad('2025-09-10', '2026-11-11')).toBe(14);
    expect(mesesDeAntiguedad('2026-03-12', '2026-11-11')).toBe(7);
    expect(mesesDeAntiguedad('2026-11-12', '2026-11-11')).toBe(0);
  });
});
