// Paridad con el backend: el mismo fixture lo prueba pytest sobre `agent/tools/calcular_cotizacion.py`
// (tests/unit/test_calcular_cotizacion.py). Si una de las dos calculadoras cambia, este archivo avisa.
import { describe, expect, it } from 'vitest';
import { calcularCotizacion } from './calculo';
import fixture from './calculo_casos.fixture.json';

describe('paridad con el fixture compartido del backend', () => {
  for (const caso of fixture.casos) {
    it(caso.nombre, () => {
      const r = calcularCotizacion(caso.lineas, caso.tasaIvaPorciento);
      expect(r.importes).toEqual(caso.esperado.importes);
      expect(r.subtotal).toBe(caso.esperado.subtotal);
      expect(r.iva).toBe(caso.esperado.iva);
      expect(r.total).toBe(caso.esperado.total);
      expect(r.costo).toBe(caso.esperado.costo);
      expect(r.margen).toBe(caso.esperado.margen);
      expect(r.margenPuntosBase).toBe(caso.esperado.margenPuntosBase);
    });
  }
});
