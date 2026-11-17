// Estado global del prototipo (datos de ejemplo en memoria). Se reemplaza por llamadas a la API.
// Las cifras siempre se derivan con lib/calculo.ts; aquí solo se guardan cantidades y precios.

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  BITACORA_INICIAL,
  CITAS,
  COTIZACIONES_INICIALES,
  DOCUMENTOS_INICIALES,
  MEMORIA_INICIAL,
  USUARIO_ACTUAL,
} from '../data/ejemplo';
import type {
  Cita,
  Cotizacion,
  Documento,
  EntradaBitacora,
  HechoMemoria,
  IdEscenario,
  Partida,
  Usuario,
} from '../data/tipos';
import { ESCENARIOS } from '../data/tipos';
import { ahoraISO, formatoMXN } from '../lib/dinero';

export type TipoToast = 'ok' | 'error' | 'info';
interface Toast {
  id: number;
  texto: string;
  tipo: TipoToast;
}

interface Almacen {
  usuario: Usuario;
  cotizaciones: Cotizacion[];
  documentos: Documento[];
  memoria: HechoMemoria[];
  bitacora: EntradaBitacora[];
  citas: Cita[];
  toasts: Toast[];
  avisar: (texto: string, tipo?: TipoToast) => void;
  cerrarToast: (id: number) => void;
  citaPorId: (id: string) => Cita | undefined;
  documentoPorId: (id: string) => Documento | undefined;
  actualizarPartida: (
    cotizacionId: string,
    escenario: IdEscenario,
    partidaId: string,
    cambios: Partial<Pick<Partida, 'cantidad' | 'precioUnitario'>>,
  ) => void;
  actualizarNotas: (cotizacionId: string, escenario: IdEscenario, notas: string) => void;
  aprobar: (cotizacionId: string, escenario: IdEscenario) => void;
  rechazar: (cotizacionId: string, motivo: string) => void;
  guardarAprendizaje: (cotizacionId: string, texto: string) => void;
  editarHecho: (id: string, texto: string) => void;
  alternarPausa: (id: string) => void;
  confirmarHecho: (id: string) => void;
  borrarHecho: (id: string) => void;
  reprocesar: (id: string) => void;
}

const Contexto = createContext<Almacen | null>(null);

const etiquetaEscenario = (id: IdEscenario) => ESCENARIOS.find((e) => e.id === id)?.etiqueta ?? id;

export function ProveedorAlmacen({ children }: { children: ReactNode }) {
  const [cotizaciones, setCotizaciones] = useState<Cotizacion[]>(COTIZACIONES_INICIALES);
  const [documentos, setDocumentos] = useState<Documento[]>(DOCUMENTOS_INICIALES);
  const [memoria, setMemoria] = useState<HechoMemoria[]>(MEMORIA_INICIAL);
  const [bitacora, setBitacora] = useState<EntradaBitacora[]>(BITACORA_INICIAL);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const siguienteToast = useRef(1);
  const usuario = USUARIO_ACTUAL;

  const cerrarToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const avisar = useCallback(
    (texto: string, tipo: TipoToast = 'ok') => {
      const id = siguienteToast.current++;
      setToasts((t) => [...t, { id, texto, tipo }]);
      window.setTimeout(() => cerrarToast(id), 5000); // desaparece en 5 s (doc UI §6)
    },
    [cerrarToast],
  );

  const modificar = useCallback(
    (id: string, fn: (c: Cotizacion) => Cotizacion) =>
      setCotizaciones((lista) => lista.map((c) => (c.id === id ? fn(c) : c))),
    [],
  );

  const valor = useMemo<Almacen>(
    () => ({
      usuario,
      cotizaciones,
      documentos,
      memoria,
      bitacora,
      citas: CITAS,
      toasts,
      avisar,
      cerrarToast,
      citaPorId: (id) => CITAS.find((c) => c.id === id),
      documentoPorId: (id) => documentos.find((d) => d.id === id),

      actualizarPartida: (cotizacionId, escenario, partidaId, cambios) =>
        modificar(cotizacionId, (c) => {
          const actual = c.escenarios[escenario].partidas.find((p) => p.id === partidaId);
          if (!actual) return c;
          const detalle: string[] = [];
          if (cambios.cantidad !== undefined && cambios.cantidad !== actual.cantidad)
            detalle.push(`cantidad ${actual.cantidad} → ${cambios.cantidad}`);
          if (cambios.precioUnitario !== undefined && cambios.precioUnitario !== actual.precioUnitario)
            detalle.push(`precio ${formatoMXN(actual.precioUnitario)} → ${formatoMXN(cambios.precioUnitario)}`);
          if (detalle.length === 0) return c;
          return {
            ...c,
            escenarios: {
              ...c.escenarios,
              [escenario]: {
                ...c.escenarios[escenario],
                partidas: c.escenarios[escenario].partidas.map((p) =>
                  p.id === partidaId ? { ...p, ...cambios, editadaPor: usuario.nombre } : p,
                ),
              },
            },
            historial: [
              ...c.historial,
              {
                fecha: ahoraISO(),
                usuario: usuario.nombre,
                texto: `Editó «${actual.concepto}» (${etiquetaEscenario(escenario)}): ${detalle.join(', ')}.`,
              },
            ],
          };
        }),

      actualizarNotas: (cotizacionId, escenario, notas) =>
        modificar(cotizacionId, (c) =>
          c.escenarios[escenario].notas === notas
            ? c
            : {
                ...c,
                escenarios: { ...c.escenarios, [escenario]: { ...c.escenarios[escenario], notas } },
                historial: [
                  ...c.historial,
                  { fecha: ahoraISO(), usuario: usuario.nombre, texto: `Editó las notas del agente (${etiquetaEscenario(escenario)}).` },
                ],
              },
        ),

      aprobar: (cotizacionId, escenario) => {
        const ahora = ahoraISO();
        modificar(cotizacionId, (c) => ({
          ...c,
          estado: 'Aprobada',
          aprobadaPor: usuario.nombre,
          fechaAprobacion: ahora,
          escenarioAprobado: escenario,
          historial: [
            ...c.historial,
            { fecha: ahora, usuario: usuario.nombre, texto: `Aprobó el escenario ${etiquetaEscenario(escenario)}.` },
          ],
        }));
        setBitacora((b) => [
          {
            id: `b${Date.now()}`, fecha: ahora, usuario: usuario.nombre,
            pregunta: `Aprobación de la cotización #${cotizacionId}`, documentos: [], herramientas: ['generar_pdf'],
            duracionMs: 0, cotizacion: `#${cotizacionId}`, aprobadoPor: usuario.nombre,
          },
          ...b,
        ]);
      },

      rechazar: (cotizacionId, motivo) =>
        modificar(cotizacionId, (c) => ({
          ...c,
          estado: 'Rechazada',
          motivoRechazo: motivo || 'Sin motivo indicado.',
          historial: [
            ...c.historial,
            { fecha: ahoraISO(), usuario: usuario.nombre, texto: `Rechazó la cotización${motivo ? `: ${motivo}` : '.'}` },
          ],
        })),

      guardarAprendizaje: (cotizacionId, texto) =>
        setMemoria((m) => [
          {
            id: `m${Date.now()}`, texto, origen: `Cot. ${cotizacionId} aprobada por ${usuario.nombre}`,
            fecha: ahoraISO().slice(0, 10), estado: 'Activa', porConfirmar: true,
          },
          ...m,
        ]),

      editarHecho: (id, texto) => setMemoria((m) => m.map((h) => (h.id === id ? { ...h, texto } : h))),
      alternarPausa: (id) =>
        setMemoria((m) => m.map((h) => (h.id === id ? { ...h, estado: h.estado === 'Activa' ? 'Pausada' : 'Activa' } : h))),
      confirmarHecho: (id) => setMemoria((m) => m.map((h) => (h.id === id ? { ...h, porConfirmar: false } : h))),
      borrarHecho: (id) => setMemoria((m) => m.filter((h) => h.id !== id)),

      reprocesar: (id) => {
        setDocumentos((d) => d.map((x) => (x.id === id ? { ...x, estado: 'Procesando', motivo: undefined } : x)));
        window.setTimeout(
          () =>
            setDocumentos((d) =>
              d.map((x) => (x.id === id ? { ...x, estado: 'Listo', actualizado: ahoraISO().slice(0, 10) } : x)),
            ),
          1800,
        );
      },
    }),
    [usuario, cotizaciones, documentos, memoria, bitacora, toasts, avisar, cerrarToast, modificar],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAlmacen(): Almacen {
  const v = useContext(Contexto);
  if (!v) throw new Error('useAlmacen debe usarse dentro de ProveedorAlmacen');
  return v;
}

// Utilidad usada por listas y tarjetas: total del escenario aprobado o, si no hay, del recomendado.
export function escenarioVigente(c: Cotizacion): IdEscenario {
  return c.escenarioAprobado ?? 'recomendado';
}
