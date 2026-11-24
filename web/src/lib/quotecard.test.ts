import { describe, expect, it } from 'vitest';
import { COTIZACION_MOCK_EJEMPLO } from '../mocks/cotizacionMock';
import { calcularCotizacion } from './calculo';
import { formatoMXN } from './dinero';

describe('Cotización estructurada y QuoteCard mock', () => {
  it('contiene partidas estructuradas con trazabilidad y niveles de confianza válidos', () => {
    const mock = COTIZACION_MOCK_EJEMPLO;
    expect(mock.partidas.length).toBeGreaterThan(0);
    for (const p of mock.partidas) {
      expect(p.concepto).toBeTruthy();
      expect(p.cantidad).toBeGreaterThan(0);
      expect(p.precioUnitario).toBeGreaterThan(0);
      expect(p.etiquetaTrazabilidad).toBeTruthy();
      expect(['alta', 'desactualizada_12m', 'sin_antecedente', 'desactualizada_6m']).toContain(p.nivelConfianza);
    }
  });

  it('verifica que el desglose financiero coincide con la suma determinista de partidas', () => {
    const mock = COTIZACION_MOCK_EJEMPLO;
    const subtotalCalculado = mock.partidas.reduce((acc, p) => acc + p.cantidad * p.precioUnitario, 0);
    expect(mock.desglose.subtotalGeneral).toBeCloseTo(subtotalCalculado, 2);

    const ivaCalculado = Math.round(subtotalCalculado * 0.16 * 100) / 100;
    expect(mock.desglose.iva).toBeCloseTo(ivaCalculado, 2);
    expect(mock.desglose.total).toBeCloseTo(subtotalCalculado + ivaCalculado, 2);
  });

  it('valida el cálculo determinista con la función central calcularCotizacion', () => {
    const lineas = [
      { cantidad: 20, precioUnitario: 345000, costoUnitario: 265000 },
      { cantidad: 15, precioUnitario: 14250, costoUnitario: 10500 },
    ];
    const res = calcularCotizacion(lineas);
    expect(res.subtotal).toBe(20 * 345000 + 15 * 14250);
    expect(res.total).toBe(res.subtotal + res.iva);
    expect(formatoMXN(res.total)).toContain('$');
  });
});
