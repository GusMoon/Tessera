// Convierte lo que responde la API (snake_case, centavos) en el modelo de la interfaz (data/tipos.ts).
// Las cifras no se recalculan aquí: se copian tal cual; los totales se derivan con lib/calculo.ts.

import type {
  Cita,
  Cotizacion,
  Documento,
  EntradaBitacora,
  HechoMemoria,
  IdEscenario,
  Partida,
  TipoDocumento,
} from '../data/tipos';
import { ESCENARIOS } from '../data/tipos';
import type { CotizacionApi, EntradaBitacoraApi, FuenteApi, FuenteCitadaApi, HechoApi, PartidaApi } from './api';

export const aPartida = (p: PartidaApi): Partida => ({
  id: p.id,
  codigo: p.codigo,
  tipo: p.tipo,
  unidad: p.unidad,
  concepto: p.concepto,
  cantidad: p.cantidad,
  precioUnitario: p.precio_unitario_centavos,
  costoUnitario: p.costo_unitario_centavos,
  citaId: p.fuente_ref,
  editadaPor: p.editada_por ?? undefined,
});

export function aCotizacion(c: CotizacionApi): Cotizacion {
  const escenarios = Object.fromEntries(
    ESCENARIOS.map(({ id }) => [
      id,
      { partidas: c.escenarios[id].partidas.map(aPartida), notas: c.escenarios[id].notas, riesgos: c.escenarios[id].riesgos },
    ]),
  ) as Cotizacion['escenarios'];
  return {
    id: c.id,
    folio: c.folio,
    cliente: c.cliente,
    solicitud: c.solicitud,
    avisos: c.avisos,
    parecidas: c.parecidas,
    fecha: c.fecha,
    estado: c.estado,
    creadaPor: c.creada_por,
    escenarios,
    historial: c.historial,
    aprobadaPor: c.aprobada_por ?? undefined,
    fechaAprobacion: c.fecha_aprobacion ?? undefined,
    escenarioAprobado: (c.escenario_aprobado as IdEscenario | null) ?? undefined,
    motivoRechazo: c.motivo_rechazo ?? undefined,
  };
}

export const aCita = (f: FuenteCitadaApi): Cita => ({
  id: f.ref,
  documentoId: f.fuente_id === null ? '' : String(f.fuente_id),
  documentoNombre: f.documento ?? 'Fuente que ya no está cargada',
  etiqueta: f.etiqueta,
  fecha: f.fecha ?? '',
  ubicacion: f.ubicacion,
  extracto: f.extracto ?? '',
  permiso: f.permiso ?? undefined,
  restringido: f.restringido,
});

/** Todas las citas de las cotizaciones, por referencia. Si dos cotizaciones citan lo mismo, gana la más reciente. */
export function citasDe(cotizaciones: CotizacionApi[]): Map<string, Cita> {
  const mapa = new Map<string, Cita>();
  for (const c of [...cotizaciones].reverse()) for (const f of Object.values(c.fuentes)) mapa.set(f.ref, aCita(f));
  return mapa;
}

const TIPOS: Record<string, TipoDocumento> = { CSV: 'CSV', Excel: 'Excel', PDF: 'PDF' };

export const aDocumento = (f: FuenteApi): Documento => ({
  id: String(f.id),
  nombre: f.nombre,
  tipo: TIPOS[f.tipo] ?? 'Excel',
  actualizado: f.fecha_carga.slice(0, 10),
  estado: f.estado,
  permisos: f.permiso,
  motivo: f.motivo ?? undefined,
});

export const aHecho = (h: HechoApi): HechoMemoria => ({
  id: h.id,
  texto: h.texto,
  origen: h.origen,
  fecha: h.fecha,
  estado: h.estado,
  porConfirmar: h.por_confirmar,
});

export const aEntradaBitacora = (b: EntradaBitacoraApi): EntradaBitacora => ({
  id: b.id,
  fecha: b.fecha,
  usuario: b.usuario,
  pregunta: b.pregunta,
  documentos: b.documentos,
  herramientas: b.herramientas,
  duracionMs: b.duracion_ms,
  cotizacion: b.cotizacion ?? undefined,
  aprobadoPor: b.aprobado_por ?? undefined,
});
