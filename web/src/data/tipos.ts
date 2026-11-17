import type { Centavos } from '../lib/dinero';

export type EstadoCotizacion = 'Borrador' | 'En revisión' | 'Aprobada' | 'Rechazada';
export type IdEscenario = 'economico' | 'recomendado' | 'premium';

export const ESCENARIOS: { id: IdEscenario; etiqueta: string }[] = [
  { id: 'economico', etiqueta: 'Económico' },
  { id: 'recomendado', etiqueta: 'Recomendado' },
  { id: 'premium', etiqueta: 'Premium' },
];

export type Rol = 'Vendedor' | 'Responsable comercial' | 'Administrador';
export type Permiso = 'Todos' | 'Comercial' | 'Administración';

export interface Usuario {
  id: string;
  nombre: string;
  rol: Rol;
}

/** Fragmento citable de un documento (fila de Excel, página de PDF…). */
export interface Cita {
  id: string;
  documentoId: string;
  etiqueta: string; // «Cot. 0412»
  fecha: string; // ISO; fecha del dato citado
  ubicacion: string;
  extracto: string;
}

export interface Partida {
  id: string;
  concepto: string;
  cantidad: number;
  precioUnitario: Centavos;
  costoUnitario: Centavos;
  citaId: string;
  editadaPor?: string;
}

export interface Escenario {
  partidas: Partida[];
  notas: string;
  riesgos: string[];
}

export interface EntradaHistorial {
  fecha: string; // ISO con hora
  usuario: string;
  texto: string;
}

export interface Cotizacion {
  id: string;
  folio: string;
  cliente: string;
  fecha: string;
  estado: EstadoCotizacion;
  creadaPor: string;
  escenarios: Record<IdEscenario, Escenario>;
  historial: EntradaHistorial[];
  aprobadaPor?: string;
  fechaAprobacion?: string;
  escenarioAprobado?: IdEscenario;
  motivoRechazo?: string;
}

export type TipoDocumento = 'Excel' | 'PDF' | 'Chat';
export type EstadoDocumento = 'Listo' | 'Procesando' | 'Error' | 'Omitido';

export interface Documento {
  id: string;
  nombre: string;
  tipo: TipoDocumento;
  actualizado: string;
  estado: EstadoDocumento;
  permisos: Permiso;
  motivo?: string;
}

export interface HechoMemoria {
  id: string;
  texto: string;
  origen: string;
  fecha: string;
  estado: 'Activa' | 'Pausada';
  porConfirmar: boolean;
}

export interface EntradaBitacora {
  id: string;
  fecha: string;
  usuario: string;
  pregunta: string;
  documentos: string[];
  herramientas: string[];
  duracionMs: number;
  cotizacion?: string;
  aprobadoPor?: string;
}
