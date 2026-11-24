/**
 * Mocks aislados para desarrollo y pruebas del componente QuoteCard y vista previa de cotización.
 * No altera la lógica ni contratos de la API backend.
 */
import type { Cotizacion, IdEscenario } from '../data/tipos';

export interface PartidaEstructurada {
  id: string;
  codigo: string;
  concepto: string;
  cantidad: number;
  unidad: string;
  precioUnitario: number; // en pesos decimales
  subtotal: number;
  costoUnitario: number;
  citaId: string;
  etiquetaTrazabilidad: string;
  nivelConfianza: 'alta' | 'desactualizada_12m' | 'sin_antecedente' | 'desactualizada_6m';
  motivoConfianza?: string;
}

export interface DesgloseFinanciero {
  materialesSubtotal: number;
  instalacionSubtotal: number;
  fleteSubtotal: number;
  serviciosSubtotal: number;
  subtotalGeneral: number;
  costoTotal: number;
  margenImporte: number;
  margenPorcentaje: number | null;
  iva: number;
  total: number;
}

export interface CotizacionEstructurada {
  id: string;
  folio: string;
  cliente: string;
  fecha: string;
  estado: Cotizacion['estado'];
  escenarioActivo: IdEscenario;
  partidas: PartidaEstructurada[];
  desglose: DesgloseFinanciero;
  avisos: string[];
  notas: string;
}

export const COTIZACION_MOCK_EJEMPLO: CotizacionEstructurada = {
  id: 'cot-mock-001',
  folio: 'COT-2026-089',
  cliente: 'Grupo Inmobiliario Peninsular S.A. de C.V.',
  fecha: '2026-11-24',
  estado: 'Borrador',
  escenarioActivo: 'recomendado',
  partidas: [
    {
      id: 'p-1',
      codigo: 'GAB-403020',
      concepto: 'Gabinete NEMA 4X 400x300x200 mm acero inoxidable 304',
      cantidad: 20,
      unidad: 'PZA',
      precioUnitario: 3450.0,
      subtotal: 69000.0,
      costoUnitario: 2650.0,
      citaId: 'catalogo:GAB-403020',
      etiquetaTrazabilidad: 'Basado en Catálogo Maya · mar 2026',
      nivelConfianza: 'alta',
    },
    {
      id: 'p-2',
      codigo: 'TUB-CON-075',
      concepto: 'Tubo conduit pared delgada 3/4 pulg x 3 m',
      cantidad: 15,
      unidad: 'TRAMO',
      precioUnitario: 142.5,
      subtotal: 2137.5,
      costoUnitario: 105.0,
      citaId: 'historial:COT-0142',
      etiquetaTrazabilidad: 'Basado en COT-0142 · sep 2025',
      nivelConfianza: 'desactualizada_12m',
      motivoConfianza: 'Precio con más de 12 meses de antigüedad',
    },
    {
      id: 'p-3',
      codigo: 'COP-CON-075',
      concepto: 'Cople de presión para tubo conduit 3/4 pulg',
      cantidad: 30,
      unidad: 'PZA',
      precioUnitario: 18.0,
      subtotal: 540.0,
      costoUnitario: 12.0,
      citaId: 'estimado:COP-CON-075',
      etiquetaTrazabilidad: 'Sin antecedente exacto · Estimado',
      nivelConfianza: 'sin_antecedente',
      motivoConfianza: 'Sin antecedente en historial; costo paramétrico estimado',
    },
    {
      id: 'p-4',
      codigo: 'SRV-INST-GAB',
      concepto: 'Servicio de montaje y fijación de gabinetes NEMA en sitio',
      cantidad: 20,
      unidad: 'SRV',
      precioUnitario: 450.0,
      subtotal: 9000.0,
      costoUnitario: 300.0,
      citaId: 'servicios:SRV-INST',
      etiquetaTrazabilidad: 'Tarifario de servicios · nov 2026',
      nivelConfianza: 'alta',
    },
    {
      id: 'p-5',
      codigo: 'SRV-FLETE-MER',
      concepto: 'Flete y maniobra de entrega local Mérida y zona metropolitana',
      cantidad: 1,
      unidad: 'VIAJE',
      precioUnitario: 1800.0,
      subtotal: 1800.0,
      costoUnitario: 1200.0,
      citaId: 'servicios:SRV-FLETE-MER',
      etiquetaTrazabilidad: 'Tarifario fletes 2026',
      nivelConfianza: 'alta',
    },
  ],
  desglose: {
    materialesSubtotal: 71677.5,
    instalacionSubtotal: 9000.0,
    fleteSubtotal: 1800.0,
    serviciosSubtotal: 10800.0,
    subtotalGeneral: 82477.5,
    costoTotal: 60475.0,
    margenImporte: 22002.5,
    margenPorcentaje: 26.68,
    iva: 13196.4,
    total: 95673.9,
  },
  avisos: [
    'El tubo conduit usa un precio de septiembre 2025 (más de 12 meses): se sugiere validar con proveedor antes de firmar contrato.',
  ],
  notas: 'Instalación programable a 5 días hábiles tras confirmación de anticipo.',
};
