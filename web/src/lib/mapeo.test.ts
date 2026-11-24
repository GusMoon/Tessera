import { describe, expect, it } from 'vitest';
import type { CotizacionApi, PartidaApi } from './api';
import { calcularCotizacion } from './calculo';
import { aCita, aCotizacion, aDocumento, aEntradaBitacora, aHecho, citasDe } from './mapeo';

const partida = (id: string, cantidad: number, precio: number, extra: Partial<PartidaApi> = {}): PartidaApi => ({
  id, tipo: 'material', codigo: `COD-${id}`, concepto: `Concepto ${id}`, unidad: 'PZA', cantidad,
  costo_unitario_centavos: Math.round(precio * 0.82), precio_unitario_centavos: precio, importe_centavos: cantidad * precio,
  fuente_ref: `catalogo:COD-${id}`, fuente_fecha: '2026-10-01', antiguedad_meses: 1, precio_antiguo: false, editada_por: null, ...extra,
});

const totales = { subtotal_centavos: 0, iva_centavos: 0, total_centavos: 0, costo_centavos: 0, margen_centavos: 0, margen_puntos_base: null };
const escenario = (partidas: PartidaApi[]) => ({ notas: 'Nota', riesgos: ['Riesgo'], margen_objetivo_puntos_base: 1800, partidas, totales });

const api: CotizacionApi = {
  id: '7', folio: '#0007', cliente: 'Hotel Prueba', solicitud: '20 gabinetes', fecha: '2026-11-23', estado: 'En revisión', creada_por: 'Ana Pérez',
  escenario_aprobado: null, motivo_rechazo: null, aprobada_por: null, fecha_aprobacion: null,
  escenarios: {
    economico: escenario([partida('1', 20, 100000)]),
    recomendado: escenario([partida('1', 20, 121951, { editada_por: 'Ana Pérez' }), partida('2', 1, 58537, { tipo: 'servicio' })]),
    premium: escenario([partida('1', 20, 133333)]),
  },
  historial: [{ fecha: '2026-11-23T10:00:00', usuario: 'Tessera (agente)', texto: 'Borrador creado.' }],
  avisos: ['Un aviso'], parecidas: [{ ref: 'historial:COT-MID-0101', folio: 'COT-MID-0101', cliente: 'Altabrisa', fecha: '2026-08-01' }],
  fuentes: {
    'catalogo:COD-1': { ref: 'catalogo:COD-1', etiqueta: 'COD-1', fecha: '2026-10-01', ubicacion: 'Catálogo · catalogo_materiales.csv', extracto: 'Gabinete…', fuente_id: 3, documento: 'catalogo_materiales.csv', permiso: 'Todos', restringido: false, disponible: true },
    'catalogo:COD-2': { ref: 'catalogo:COD-2', etiqueta: 'COD-2', fecha: null, ubicacion: 'Catálogo', extracto: null, fuente_id: null, documento: null, permiso: null, restringido: false, disponible: false },
  },
};

describe('aCotizacion', () => {
  const c = aCotizacion(api);

  it('copia las cifras en centavos sin tocarlas', () => {
    const p = c.escenarios.recomendado.partidas[0];
    expect([p.cantidad, p.precioUnitario, p.costoUnitario, p.citaId]).toEqual([20, 121951, Math.round(121951 * 0.82), 'catalogo:COD-1']);
    expect(c.escenarios.recomendado.partidas[1]).toMatchObject({ tipo: 'servicio', unidad: 'PZA' });
  });

  it('conserva quién editó, el estado y los datos de seguimiento', () => {
    expect(c.escenarios.recomendado.partidas[0].editadaPor).toBe('Ana Pérez');
    expect(c.escenarios.recomendado.partidas[1].editadaPor).toBeUndefined();
    expect(c).toMatchObject({ id: '7', folio: '#0007', estado: 'En revisión', creadaPor: 'Ana Pérez', avisos: ['Un aviso'], aprobadaPor: undefined });
    expect(c.parecidas[0].folio).toBe('COT-MID-0101');
  });

  it('los totales que se derivan en el navegador coinciden con importes enteros', () => {
    const r = calcularCotizacion(c.escenarios.recomendado.partidas);
    expect(r.subtotal).toBe(20 * 121951 + 58537);
    expect(r.iva).toBe(Math.round((r.subtotal * 16) / 100));
  });

  it('traduce la aprobación y el rechazo', () => {
    const aprobada = aCotizacion({ ...api, estado: 'Aprobada', escenario_aprobado: 'premium', aprobada_por: 'Marcos Díaz', fecha_aprobacion: '2026-11-23T11:00:00' });
    expect(aprobada).toMatchObject({ escenarioAprobado: 'premium', aprobadaPor: 'Marcos Díaz', fechaAprobacion: '2026-11-23T11:00:00' });
    expect(aCotizacion({ ...api, estado: 'Rechazada', motivo_rechazo: 'Caro' }).motivoRechazo).toBe('Caro');
  });
});

describe('citas', () => {
  it('una fuente sin fecha ni documento no inventa datos', () => {
    const cita = aCita(api.fuentes['catalogo:COD-2']);
    expect(cita).toMatchObject({ fecha: '', documentoId: '', extracto: '', restringido: false });
    expect(cita.documentoNombre).toMatch(/ya no está cargada/);
  });

  it('el id de documento es el de la fuente cargada, para enlazar con Fuentes', () => {
    expect(aCita(api.fuentes['catalogo:COD-1'])).toMatchObject({ id: 'catalogo:COD-1', documentoId: '3', documentoNombre: 'catalogo_materiales.csv' });
  });

  it('si dos cotizaciones citan lo mismo, gana la más reciente (la primera de la lista)', () => {
    const vieja = { ...api, id: '6', fuentes: { 'catalogo:COD-1': { ...api.fuentes['catalogo:COD-1'], extracto: 'Texto viejo' } } };
    expect(citasDe([api, vieja]).get('catalogo:COD-1')?.extracto).toBe('Gabinete…');
  });

  it('una fuente restringida llega sin extracto', () => {
    const r = aCita({ ...api.fuentes['catalogo:COD-1'], extracto: null, restringido: true, permiso: 'Administración' });
    expect(r).toMatchObject({ restringido: true, extracto: '', permiso: 'Administración' });
  });
});

describe('otros mapeos', () => {
  it('documento: tipo y fecha de carga', () => {
    expect(aDocumento({ id: 5, nombre: 'x.csv', tipo: 'CSV', estado: 'Listo', leidas: 1, guardadas: 1, rechazadas: 0, omitidas: 0, fecha_carga: '2026-11-23 10:00:00', permiso: 'Comercial' }))
      .toMatchObject({ id: '5', tipo: 'CSV', actualizado: '2026-11-23', permisos: 'Comercial' });
  });

  it('hecho de memoria y entrada de bitácora', () => {
    expect(aHecho({ id: '1', texto: 't', origen: 'o', fecha: '2026-11-23', estado: 'Pausada', por_confirmar: true })).toMatchObject({ porConfirmar: true, estado: 'Pausada' });
    expect(aEntradaBitacora({ id: '2', fecha: 'f', usuario: 'u', pregunta: 'p', documentos: ['a'], herramientas: ['h'], duracion_ms: 120, cotizacion: null, aprobado_por: null }))
      .toMatchObject({ duracionMs: 120, cotizacion: undefined, aprobadoPor: undefined });
  });
});
