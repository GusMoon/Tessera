import { describe, expect, it } from 'vitest';
import {
  MAX_CONVERSACIONES,
  MAX_MENSAJES,
  cargarConversaciones,
  fechaCorta,
  guardarConversaciones,
  recortar,
  siguienteIdMensaje,
  tituloDe,
  type Conversacion,
} from './conversaciones';

const almacenFalso = () => {
  const datos = new Map<string, string>();
  return { getItem: (k: string) => datos.get(k) ?? null, setItem: (k: string, v: string) => void datos.set(k, v) };
};

const conv = (id: string, actualizada: string, mensajes = 1): Conversacion => ({
  id,
  titulo: `Conversación ${id}`,
  creada: actualizada,
  actualizada,
  mensajes: Array.from({ length: mensajes }, (_, i) => ({ id: i + 1, rol: i % 2 ? 'tessera' : 'usuario', texto: `m${i}` })),
});

describe('tituloDe', () => {
  it('usa lo primero que pidió el usuario y lo recorta', () => {
    expect(tituloDe('  Cotiza   20 gabinetes\nNEMA 4X ')).toBe('Cotiza 20 gabinetes NEMA 4X');
    expect(tituloDe('x'.repeat(100))).toHaveLength(58);
    expect(tituloDe('x'.repeat(100)).endsWith('…')).toBe(true);
  });
  it('sin texto usa el nombre de los archivos', () => {
    expect(tituloDe('', ['pedido.xlsx', 'nota.txt'])).toBe('Archivos: pedido.xlsx, nota.txt');
    expect(tituloDe('')).toBe('Conversación');
  });
});

describe('guardar y cargar', () => {
  it('cada usuario tiene su propio historial', () => {
    const a = almacenFalso();
    guardarConversaciones(a, 'u1', [conv('a', '2026-11-24T10:00:00Z')], 'a');
    guardarConversaciones(a, 'u3', [conv('b', '2026-11-24T11:00:00Z')], 'b');
    expect(cargarConversaciones(a, 'u1').conversaciones.map((c) => c.id)).toEqual(['a']);
    expect(cargarConversaciones(a, 'u3')).toMatchObject({ activaId: 'b' });
    expect(cargarConversaciones(a, 'u2')).toEqual({ conversaciones: [], activaId: null });
  });

  it('recuerda cuál estaba abierta y la ignora si ya no existe', () => {
    const a = almacenFalso();
    guardarConversaciones(a, 'u1', [conv('a', '2026-11-24T10:00:00Z'), conv('b', '2026-11-24T09:00:00Z')], 'b');
    expect(cargarConversaciones(a, 'u1').activaId).toBe('b');
    a.setItem('tessera.chat.v1.u1.activa', 'borrada');
    expect(cargarConversaciones(a, 'u1').activaId).toBeNull();
  });

  it('un dato dañado no rompe: se ignora', () => {
    const a = almacenFalso();
    a.setItem('tessera.chat.v1.u1', '{no es json');
    expect(cargarConversaciones(a, 'u1')).toEqual({ conversaciones: [], activaId: null });
    const mala = { id: 'x', titulo: 't', actualizada: 'z', mensajes: [{ rol: 'otro' }] };
    a.setItem('tessera.chat.v1.u1', JSON.stringify([{ id: 1 }, conv('ok', '2026-11-24T10:00:00Z'), mala]));
    expect(cargarConversaciones(a, 'u1').conversaciones.map((c) => c.id)).toEqual(['ok']);
  });

  it('si el navegador no deja guardar, devuelve false y no lanza', () => {
    const lleno = {
      getItem: () => null,
      setItem: () => {
        throw new Error('cuota llena');
      },
    };
    expect(guardarConversaciones(lleno, 'u1', [conv('a', '2026-11-24T10:00:00Z')], 'a')).toBe(false);
  });
});

describe('recortar', () => {
  it('deja las más recientes primero y limita cuántas y qué tan largas', () => {
    const muchas = Array.from({ length: MAX_CONVERSACIONES + 5 }, (_, i) => conv(`c${i}`, new Date(2026, 10, 1, 0, i).toISOString()));
    const r = recortar(muchas);
    expect(r).toHaveLength(MAX_CONVERSACIONES);
    expect(r[0].id).toBe(`c${MAX_CONVERSACIONES + 4}`);
    expect(recortar([conv('larga', '2026-11-24T10:00:00Z', MAX_MENSAJES + 30)])[0].mensajes).toHaveLength(MAX_MENSAJES);
  });
});

describe('utilidades', () => {
  it('siguienteIdMensaje', () => {
    expect(siguienteIdMensaje([])).toBe(1);
    expect(siguienteIdMensaje(conv('a', '2026-11-24T10:00:00Z', 3).mensajes)).toBe(4);
  });
  it('fechaCorta usa dd/mm/aaaa y tolera fechas inválidas', () => {
    expect(fechaCorta(new Date(2026, 10, 24, 9, 5).toISOString())).toBe('24/11/2026 09:05');
    expect(fechaCorta('no es fecha')).toBe('');
  });
});
