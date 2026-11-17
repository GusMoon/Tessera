// Datos 100 % sintéticos para el prototipo (CLAUDE.md, regla 7). Nombres de empresas y personas ficticios.
// Cuando exista la API, este archivo se reemplaza por llamadas a /cotizaciones, /fuentes, etc.

import { divRedondeada } from '../lib/calculo';
import type {
  Cita,
  Cotizacion,
  Documento,
  EntradaBitacora,
  Escenario,
  HechoMemoria,
  Partida,
  Usuario,
} from './tipos';

export const USUARIOS: Usuario[] = [
  { id: 'u1', nombre: 'Ana Pérez', rol: 'Vendedor' },
  { id: 'u2', nombre: 'Marcos Díaz', rol: 'Responsable comercial' },
  { id: 'u3', nombre: 'Laura Canché', rol: 'Administrador' },
];

/** Persona que usa el prototipo. */
export const USUARIO_ACTUAL: Usuario = USUARIOS[1];

export const EMPRESA = 'Materiales del Sureste (ficticia)';

export const DOCUMENTOS_INICIALES: Documento[] = [
  { id: 'f1', nombre: 'cotizaciones_2026.xlsx', tipo: 'Excel', actualizado: '2026-11-03', estado: 'Listo', permisos: 'Comercial' },
  { id: 'f2', nombre: 'ficha_gm200.pdf', tipo: 'PDF', actualizado: '2026-10-28', estado: 'Listo', permisos: 'Todos' },
  { id: 'f3', nombre: 'fletes_proveedores.xlsx', tipo: 'Excel', actualizado: '2025-09-10', estado: 'Listo', permisos: 'Comercial' },
  {
    id: 'f4', nombre: 'chat_cliente.txt', tipo: 'Chat', actualizado: '2026-11-01', estado: 'Error', permisos: 'Comercial',
    motivo: 'Formato de chat no reconocido: faltan marcas de fecha en las líneas 1 a 40.',
  },
  {
    id: 'f5', nombre: 'catalogo_escaneado.pdf', tipo: 'PDF', actualizado: '2026-10-20', estado: 'Error', permisos: 'Todos',
    motivo: 'PDF escaneado sin texto, falta OCR.',
  },
  { id: 'f6', nombre: 'lista_precios_2025.xlsx', tipo: 'Excel', actualizado: '2025-06-30', estado: 'Listo', permisos: 'Comercial' },
  { id: 'f7', nombre: 'costos_internos.xlsx', tipo: 'Excel', actualizado: '2026-10-02', estado: 'Listo', permisos: 'Administración' },
  { id: 'f8', nombre: 'ficha_gm150.pdf', tipo: 'PDF', actualizado: '2026-10-28', estado: 'Procesando', permisos: 'Todos' },
  { id: 'f9', nombre: 'ficha_gm300_inox.pdf', tipo: 'PDF', actualizado: '2026-10-28', estado: 'Listo', permisos: 'Todos' },
  {
    id: 'f10', nombre: 'notas_vendedores.txt', tipo: 'Chat', actualizado: '2026-09-10', estado: 'Omitido', permisos: 'Comercial',
    motivo: 'Omitido por el administrador: contiene datos personales.',
  },
  { id: 'f11', nombre: 'cotizaciones_2025.xlsx', tipo: 'Excel', actualizado: '2025-12-20', estado: 'Listo', permisos: 'Comercial' },
];

export const CITAS: Cita[] = [
  { id: 'c1', documentoId: 'f1', etiqueta: 'Cot. 0412', fecha: '2026-03-12', ubicacion: 'Hoja Q1 · fila 38', extracto: '20 gabinetes metálicos GM-200 · $4,850.00 c/u · entrega en Mérida.' },
  { id: 'c2', documentoId: 'f1', etiqueta: 'Cot. 0388', fecha: '2026-02-20', ubicacion: 'Hoja Q1 · fila 21', extracto: 'Instalación de gabinetes · $620.00 por pieza.' },
  { id: 'c3', documentoId: 'f2', etiqueta: 'Ficha GM-200', fecha: '2026-10-28', ubicacion: 'Página 1', extracto: 'Gabinete metálico GM-200, 1.8 m, acero calibre 14, IP54. Garantía estándar de 12 meses.' },
  { id: 'c4', documentoId: 'f3', etiqueta: 'Flete Mérida', fecha: '2025-09-10', ubicacion: 'Hoja Rutas · fila 6', extracto: 'Transporte local a Mérida, viaje redondo · $3,900.00.' },
  { id: 'c5', documentoId: 'f11', etiqueta: 'Cot. 0301', fecha: '2025-11-14', ubicacion: 'Hoja Q4 · fila 12', extracto: 'Gabinete GM-150 · $4,200.00 c/u.' },
  { id: 'c6', documentoId: 'f6', etiqueta: 'Lista 2025', fecha: '2025-06-30', ubicacion: 'Hoja Gabinetes · fila 9', extracto: 'GM-300 acero inoxidable · $6,300.00 c/u.' },
];

const P = (
  id: string, concepto: string, cantidad: number, precio: number, costo: number, citaId: string,
): Partida => ({ id, concepto, cantidad, precioUnitario: precio, costoUnitario: costo, citaId });

/** Variante de un escenario base: factor en porcentaje (92 = 8 % menos). */
const variante = (base: Partida[], factor: number, sufijo: string): Partida[] =>
  base.map((p) => ({
    ...p,
    id: `${p.id}-${sufijo}`,
    precioUnitario: divRedondeada(p.precioUnitario * factor, 100),
  }));

function tresEscenarios(base: Partida[], notas: string): Cotizacion['escenarios'] {
  const mk = (partidas: Partida[], n: string): Escenario => ({ partidas, notas: n, riesgos: [] });
  return {
    economico: mk(variante(base, 92, 'e'), 'Precios con 8 % menos que el recomendado; revisar disponibilidad.'),
    recomendado: mk(base, notas),
    premium: mk(variante(base, 118, 'p'), 'Incluye acabado superior y plazo prioritario.'),
  };
}

const cotizacion0123: Cotizacion['escenarios'] = {
  economico: {
    partidas: [
      P('a1', 'Gabinete metálico GM-150', 20, 420000, 345000, 'c5'),
      P('a2', 'Instalación', 20, 62000, 48000, 'c2'),
      P('a3', 'Transporte a Mérida', 1, 390000, 310000, 'c4'),
    ],
    notas: 'Opción de menor precio con el modelo GM-150. El precio base del gabinete tiene 12 meses; confirmar con proveedor.',
    riesgos: ['El precio del GM-150 viene de una cotización de hace 12 meses.'],
  },
  recomendado: {
    partidas: [
      P('b1', 'Gabinete metálico GM-200', 20, 485000, 395000, 'c1'),
      P('b2', 'Instalación', 20, 62000, 48000, 'c2'),
      P('b3', 'Transporte a Mérida', 1, 390000, 310000, 'c4'),
    ],
    notas: 'Basado en las cotizaciones 0412 y 0388, que son las más parecidas. El cliente suele pedir el flete aparte (memoria aplicada), por eso se separa como partida.',
    riesgos: [
      'El transporte usa un precio de hace 14 meses: confirmar tarifa vigente.',
      'La cotización 0412 es de marzo; el precio del gabinete pudo cambiar.',
    ],
  },
  premium: {
    partidas: [
      P('c1', 'Gabinete metálico GM-300 inoxidable', 20, 630000, 520000, 'c6'),
      P('c2', 'Instalación', 20, 74000, 56000, 'c2'),
      P('c3', 'Garantía extendida 24 meses', 20, 45000, 30000, 'c3'),
      P('c4', 'Transporte a Mérida', 1, 390000, 310000, 'c4'),
    ],
    notas: 'Acero inoxidable con garantía extendida. El precio del GM-300 viene de la lista de 2025 (16 meses).',
    riesgos: ['El precio del GM-300 es de la lista de 2025; solicitar lista actualizada.'],
  },
};

const baseGabinete = (n: number): Partida[] => [
  P('x1', 'Gabinete metálico GM-200', n, 485000, 395000, 'c1'),
  P('x2', 'Instalación', n, 62000, 48000, 'c2'),
];

export const COTIZACIONES_INICIALES: Cotizacion[] = [
  {
    id: '0123', folio: '#0123', cliente: 'Constructora Peninsular del Sureste', fecha: '2026-11-09',
    estado: 'Borrador', creadaPor: 'Ana Pérez', escenarios: cotizacion0123,
    historial: [{ fecha: '2026-11-09T10:12', usuario: 'Tessera (agente)', texto: 'Borrador creado con 3 escenarios a partir de 4 fuentes.' }],
  },
  {
    id: '0122', folio: '#0122', cliente: 'Hospedaje Costa Dorada', fecha: '2026-11-06',
    estado: 'En revisión', creadaPor: 'Ana Pérez', escenarios: tresEscenarios(baseGabinete(8), 'Pedido pequeño; mismas fuentes que la 0412.'),
    historial: [{ fecha: '2026-11-06T16:40', usuario: 'Ana Pérez', texto: 'Enviada a revisión.' }],
  },
  {
    id: '0119', folio: '#0119', cliente: 'Desarrollos Itzamná', fecha: '2026-11-02',
    estado: 'Aprobada', creadaPor: 'Ana Pérez',
    escenarios: tresEscenarios([...baseGabinete(12), P('x3', 'Transporte a Mérida', 1, 390000, 310000, 'c4')], 'Cliente con pago a 30 días.'),
    historial: [{ fecha: '2026-11-03T09:05', usuario: 'Marcos Díaz', texto: 'Aprobó el escenario Recomendado.' }],
    aprobadaPor: 'Marcos Díaz', fechaAprobacion: '2026-11-03T09:05', escenarioAprobado: 'recomendado',
  },
  {
    id: '0115', folio: '#0115', cliente: 'Taller Mecánico Chuburná', fecha: '2026-10-27',
    estado: 'Rechazada', creadaPor: 'Ana Pérez',
    escenarios: tresEscenarios([P('y1', 'Gabinete metálico GM-150', 5, 420000, 345000, 'c5')], 'Precio basado en una cotización de hace 12 meses.'),
    historial: [{ fecha: '2026-10-28T11:20', usuario: 'Marcos Díaz', texto: 'Rechazó la cotización: precio base desactualizado.' }],
    motivoRechazo: 'Precio base desactualizado.',
  },
  {
    id: '0111', folio: '#0111', cliente: 'Parque Industrial Kanasín', fecha: '2026-10-20',
    estado: 'Aprobada', creadaPor: 'Ana Pérez', escenarios: tresEscenarios(baseGabinete(30), 'Volumen alto.'),
    historial: [{ fecha: '2026-10-21T08:30', usuario: 'Marcos Díaz', texto: 'Aprobó el escenario Económico.' }],
    aprobadaPor: 'Marcos Díaz', fechaAprobacion: '2026-10-21T08:30', escenarioAprobado: 'economico',
  },
  {
    id: '0108', folio: '#0108', cliente: 'Clínica San Ángel', fecha: '2026-10-14',
    estado: 'Aprobada', creadaPor: 'Ana Pérez', escenarios: tresEscenarios(baseGabinete(6), 'Entrega en dos fechas.'),
    historial: [{ fecha: '2026-10-15T13:10', usuario: 'Marcos Díaz', texto: 'Aprobó el escenario Premium.' }],
    aprobadaPor: 'Marcos Díaz', fechaAprobacion: '2026-10-15T13:10', escenarioAprobado: 'premium',
  },
  {
    id: '0104', folio: '#0104', cliente: 'Escuela Técnica Uxmal', fecha: '2026-10-09',
    estado: 'En revisión', creadaPor: 'Ana Pérez', escenarios: tresEscenarios(baseGabinete(15), 'Cliente institucional.'),
    historial: [{ fecha: '2026-10-09T17:00', usuario: 'Ana Pérez', texto: 'Enviada a revisión.' }],
  },
  {
    id: '0098', folio: '#0098', cliente: 'Agroindustria Maxcanú', fecha: '2026-09-30',
    estado: 'Aprobada', creadaPor: 'Ana Pérez', escenarios: tresEscenarios(baseGabinete(10), 'Sin observaciones.'),
    historial: [{ fecha: '2026-10-01T10:45', usuario: 'Marcos Díaz', texto: 'Aprobó el escenario Recomendado.' }],
    aprobadaPor: 'Marcos Díaz', fechaAprobacion: '2026-10-01T10:45', escenarioAprobado: 'recomendado',
  },
];

export const MEMORIA_INICIAL: HechoMemoria[] = [
  { id: 'm1', texto: 'El cliente Constructora Peninsular del Sureste pide el flete aparte.', origen: 'Conversación del 05/11/2026 · Cot. 0398', fecha: '2026-11-05', estado: 'Activa', porConfirmar: false },
  { id: 'm2', texto: 'Las instalaciones fuera de Mérida llevan viáticos por separado.', origen: 'Cot. 0377 editada por Marcos Díaz', fecha: '2026-10-18', estado: 'Activa', porConfirmar: false },
  { id: 'm3', texto: 'Los precios de la lista de 2025 no se usan sin revisar su antigüedad.', origen: 'Retroalimentación al rechazar la Cot. 0115', fecha: '2026-10-28', estado: 'Activa', porConfirmar: true },
  { id: 'm4', texto: 'El cliente Desarrollos Itzamná paga a 30 días.', origen: 'Conversación del 12/10/2026', fecha: '2026-10-12', estado: 'Pausada', porConfirmar: false },
];

export const BITACORA_INICIAL: EntradaBitacora[] = [
  { id: 'b1', fecha: '2026-11-09T10:12', usuario: 'Ana Pérez', pregunta: 'Cotiza 20 gabinetes metálicos con instalación y transporte a Mérida', documentos: ['Cot. 0412', 'Cot. 0388', 'Ficha GM-200', 'Flete Mérida'], herramientas: ['buscar_historial', 'calcular_cotizacion'], duracionMs: 18400, cotizacion: '#0123' },
  { id: 'b2', fecha: '2026-11-06T16:35', usuario: 'Ana Pérez', pregunta: '8 gabinetes GM-200 instalados para Hospedaje Costa Dorada', documentos: ['Cot. 0412', 'Cot. 0388'], herramientas: ['buscar_historial', 'calcular_cotizacion'], duracionMs: 12100, cotizacion: '#0122' },
  { id: 'b3', fecha: '2026-11-03T09:05', usuario: 'Marcos Díaz', pregunta: 'Aprobación de la cotización #0119', documentos: ['Cot. 0412', 'Cot. 0388', 'Flete Mérida'], herramientas: ['generar_pdf'], duracionMs: 2300, cotizacion: '#0119', aprobadoPor: 'Marcos Díaz' },
  { id: 'b4', fecha: '2026-10-27T15:50', usuario: 'Ana Pérez', pregunta: '5 gabinetes GM-150 para un taller mecánico', documentos: ['Cot. 0301'], herramientas: ['buscar_historial', 'calcular_cotizacion'], duracionMs: 9800, cotizacion: '#0115' },
  { id: 'b5', fecha: '2026-10-20T11:15', usuario: 'Ana Pérez', pregunta: '30 gabinetes con instalación para parque industrial', documentos: ['Cot. 0412', 'Cot. 0388'], herramientas: ['buscar_historial', 'calcular_cotizacion'], duracionMs: 15600, cotizacion: '#0111' },
  { id: 'b6', fecha: '2026-10-14T12:30', usuario: 'Ana Pérez', pregunta: '¿Cuánto cobramos de flete a Progreso?', documentos: [], herramientas: ['buscar_historial'], duracionMs: 4200 },
];
