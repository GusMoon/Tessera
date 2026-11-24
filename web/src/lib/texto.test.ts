import { describe, expect, it } from 'vitest';
import { duracionCorta, tamanoLegible, textoReinicio, tramosConNegrita } from './texto';

describe('tramosConNegrita', () => {
  it('separa la negrita del texto normal', () => {
    expect(tramosConNegrita('Código: **CAB-THW-12AWG** (ficha)')).toEqual([
      { texto: 'Código: ', negrita: false },
      { texto: 'CAB-THW-12AWG', negrita: true },
      { texto: ' (ficha)', negrita: false },
    ]);
  });
  it('deja intacto un texto sin formato o con asteriscos sueltos', () => {
    expect(tramosConNegrita('2 * 3 = 6')).toEqual([{ texto: '2 * 3 = 6', negrita: false }]);
    expect(tramosConNegrita('****')).toEqual([{ texto: '****', negrita: false }]);
  });
  it('no cruza saltos de línea', () => {
    expect(tramosConNegrita('**uno\ndos**').every((t) => !t.negrita)).toBe(true);
  });
});

describe('tamanoLegible', () => {
  it('usa B, KB y MB', () => {
    expect(tamanoLegible(900)).toBe('900 B');
    expect(tamanoLegible(2048)).toBe('2 KB');
    expect(tamanoLegible(3 * 1024 * 1024)).toBe('3.0 MB');
  });
});

describe('duracionCorta', () => {
  it('elige la unidad según la magnitud', () => {
    expect(duracionCorta(45)).toBe('45 s');
    expect(duracionCorta(600)).toBe('10 min');
    expect(duracionCorta(3600)).toBe('1 h');
    expect(duracionCorta(18_720)).toBe('5 h 12 min');
    expect(duracionCorta(-5)).toBe('0 s');
  });
});

describe('textoReinicio', () => {
  it('indica cuánto falta', () => {
    const ahora = new Date('2026-11-24T23:00:00Z');
    expect(textoReinicio('2026-11-25T00:00:00Z', ahora)).toContain('(en 1 h)');
  });
  it('dice «mañana» solo si cae en otro día local', () => {
    const hoy20 = new Date(2026, 10, 24, 20, 0); // hora local, sin depender de la zona del equipo
    const manana18 = new Date(2026, 10, 25, 18, 0).toISOString();
    const hoy23 = new Date(2026, 10, 24, 23, 0).toISOString();
    expect(textoReinicio(manana18, hoy20)).toMatch(/^mañana a las /);
    expect(textoReinicio(hoy23, hoy20)).toMatch(/^a las .* \(en 3 h\)$/);
  });
  it('si ya pasó, no inventa una cuenta regresiva', () => {
    expect(textoReinicio('2026-11-24T00:00:00Z', new Date('2026-11-25T00:00:00Z'))).not.toContain('(en');
  });
});
