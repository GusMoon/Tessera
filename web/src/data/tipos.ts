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

/** Fragmento citable de un documento (fila del catálogo, tarifa de servicio, cotización histórica, ficha…). */
export interface Cita {
  id: string; // la referencia de la fuente, p. ej. «catalogo:GAB-403020»
  documentoId: string; // id de la fuente cargada («Fuentes»); vacío si ya no existe
  documentoNombre: string;
  etiqueta: string; // «GAB-403020»
  fecha: string; // ISO; fecha del dato citado; vacío si el dato no la trae
  ubicacion: string;
  extracto: string;
  permiso?: Permiso;
  /** El servidor no entrega el extracto si el usuario no puede abrir la fuente (regla 6). */
  restringido: boolean;
}

export interface Partida {
  id: string;
  codigo: string;
  tipo: 'material' | 'servicio';
  unidad: string;
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

/** Cotización histórica parecida que se consultó al armar la cotización (fuente citable). */
export interface Parecida {
  ref: string;
  folio: string;
  cliente: string | null;
  fecha: string;
}

export interface Cotizacion {
  id: string;
  folio: string;
  cliente: string;
  solicitud: string;
  avisos: string[];
  parecidas: Parecida[];
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

export type TipoDocumento = 'CSV' | 'Excel' | 'PDF' | 'Chat';
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
