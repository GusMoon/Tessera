// Estado global de la interfaz. Los datos viven en la API (SQLite): aquí solo se guarda una copia para pintar la pantalla.
// Las cifras de una cotización se derivan en el navegador con lib/calculo.ts para recalcular al instante al editar, pero el
// servidor valida cada edición y es la fuente de verdad: lo que responde reemplaza a lo que se pintó de forma optimista.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { Cita, Cotizacion, Documento, EntradaBitacora, HechoMemoria, IdEscenario, Partida, Usuario } from '../data/tipos';
import { ESCENARIOS } from '../data/tipos';
import {
  aprobarApi,
  borrarDatosApi,
  borrarHechoApi,
  confirmarHechoApi,
  crearCotizacionApi,
  crearCotizacionDesdeArchivosApi,
  descargarPdfApi,
  editarHechoApi,
  editarNotasApi,
  editarPartidaApi,
  enviarARevisionApi,
  fijarUsuarioActivo,
  listarBitacoraApi,
  listarCotizaciones,
  listarFuentes,
  listarMemoriaApi,
  listarUsuarios,
  obtenerAjustesApi,
  proponerHechoApi,
  rechazarApi,
  type AjustesApi,
  type CotizacionApi,
  type ResultadoSolicitud,
} from '../lib/api';
import { ahoraISO, formatoMXN } from '../lib/dinero';
import { aCita, aCotizacion, aDocumento, aEntradaBitacora, aHecho, citasDe } from '../lib/mapeo';

export type TipoToast = 'ok' | 'error' | 'info';
interface Toast {
  id: number;
  texto: string;
  tipo: TipoToast;
}

const CLAVE_USUARIO = 'tessera.usuario';
const SIN_USUARIO: Usuario = { id: '', nombre: '…', rol: 'Vendedor' };

interface Almacen {
  usuario: Usuario;
  usuarios: Usuario[];
  cambiarUsuario: (id: string) => void;
  /** Quien puede aprobar, rechazar y gestionar la memoria (Responsable comercial y Administrador). */
  puedeAprobar: boolean;
  esAdministrador: boolean;
  cotizaciones: Cotizacion[];
  documentos: Documento[];
  memoria: HechoMemoria[];
  bitacora: EntradaBitacora[];
  ajustes: AjustesApi | null;
  citas: Cita[];
  cargando: boolean;
  errorCarga: string | null;
  recargar: () => void;
  toasts: Toast[];
  avisar: (texto: string, tipo?: TipoToast) => void;
  cerrarToast: (id: number) => void;
  citaPorId: (id: string) => Cita | undefined;
  documentoPorId: (id: string) => Documento | undefined;
  /** Interpreta la solicitud (y los archivos adjuntos, si hay). Lanza `ErrorApi` con un mensaje legible si falla. */
  crearCotizacion: (solicitud: string, archivos?: File[]) => Promise<ResultadoSolicitud>;
  actualizarPartida: (
    cotizacionId: string,
    escenario: IdEscenario,
    partidaId: string,
    cambios: Partial<Pick<Partida, 'cantidad' | 'precioUnitario'>>,
  ) => void;
  actualizarNotas: (cotizacionId: string, escenario: IdEscenario, notas: string) => void;
  enviarARevision: (cotizacionId: string) => Promise<boolean>;
  aprobar: (cotizacionId: string, escenario: IdEscenario) => Promise<boolean>;
  rechazar: (cotizacionId: string, motivo: string) => Promise<boolean>;
  descargarPdf: (cotizacionId: string) => Promise<void>;
  guardarAprendizaje: (cotizacionId: string, texto: string) => Promise<void>;
  editarHecho: (id: string, texto: string) => Promise<void>;
  alternarPausa: (id: string) => Promise<void>;
  confirmarHecho: (id: string) => Promise<void>;
  borrarHecho: (id: string) => Promise<void>;
  borrarDatos: () => Promise<void>;
}

const Contexto = createContext<Almacen | null>(null);

const etiquetaEscenario = (id: IdEscenario) => ESCENARIOS.find((e) => e.id === id)?.etiqueta ?? id;
const mensajeDe = (e: unknown) => (e instanceof Error ? e.message : 'Ocurrió un error inesperado.');

export function ProveedorAlmacen({ children }: { children: ReactNode }) {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [usuarioId, setUsuarioId] = useState<string>(() => window.localStorage.getItem(CLAVE_USUARIO) ?? 'u2');
  const [cotizaciones, setCotizaciones] = useState<Cotizacion[]>([]);
  const [citas, setCitas] = useState<Map<string, Cita>>(new Map());
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [memoria, setMemoria] = useState<HechoMemoria[]>([]);
  const [bitacora, setBitacora] = useState<EntradaBitacora[]>([]);
  const [ajustes, setAjustes] = useState<AjustesApi | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const siguienteToast = useRef(1);
  const cotRef = useRef<Cotizacion[]>([]);
  cotRef.current = cotizaciones;
  const cargaVigente = useRef(0);

  const usuario = usuarios.find((u) => u.id === usuarioId) ?? SIN_USUARIO;

  const cerrarToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const avisar = useCallback(
    (texto: string, tipo: TipoToast = 'ok') => {
      const id = siguienteToast.current++;
      setToasts((t) => [...t, { id, texto, tipo }]);
      window.setTimeout(() => cerrarToast(id), 5000); // desaparece en 5 s (doc UI §6)
    },
    [cerrarToast],
  );

  // --------------------------------------------------------------------------- carga
  const cargarTodo = useCallback(async () => {
    const mia = ++cargaVigente.current;
    setCargando(true);
    try {
      const [cots, fuentes, hechos, entradas, aj] = await Promise.all([
        listarCotizaciones(),
        listarFuentes(),
        listarMemoriaApi(),
        listarBitacoraApi(),
        obtenerAjustesApi(),
      ]);
      if (mia !== cargaVigente.current) return; // llegó otra carga más nueva (cambio de usuario)
      setCotizaciones(cots.map(aCotizacion));
      setCitas(citasDe(cots));
      setDocumentos(fuentes.map(aDocumento));
      setMemoria(hechos.map(aHecho));
      setBitacora(entradas.map(aEntradaBitacora));
      setAjustes(aj);
      setErrorCarga(null);
    } catch (e) {
      if (mia === cargaVigente.current) setErrorCarga(mensajeDe(e));
    } finally {
      if (mia === cargaVigente.current) setCargando(false);
    }
  }, []);

  useEffect(() => {
    listarUsuarios()
      .then((lista) => {
        setUsuarios(lista);
        setUsuarioId((actual) => (lista.some((u) => u.id === actual) ? actual : (lista.find((u) => u.rol === 'Responsable comercial') ?? lista[0])?.id ?? ''));
      })
      .catch((e) => {
        setErrorCarga(mensajeDe(e));
        setCargando(false);
      });
  }, []);

  useEffect(() => {
    if (!usuarioId || usuarios.length === 0) return;
    fijarUsuarioActivo(usuarioId);
    window.localStorage.setItem(CLAVE_USUARIO, usuarioId);
    void cargarTodo();
  }, [usuarioId, usuarios, cargarTodo]);

  const refrescarBitacora = useCallback(() => {
    listarBitacoraApi().then((l) => setBitacora(l.map(aEntradaBitacora))).catch(() => undefined);
    obtenerAjustesApi().then(setAjustes).catch(() => undefined);
  }, []);

  // --------------------------------------------------------------------------- cotizaciones
  const reemplazar = useCallback((api: CotizacionApi) => {
    const nueva = aCotizacion(api);
    setCotizaciones((lista) => (lista.some((c) => c.id === nueva.id) ? lista.map((c) => (c.id === nueva.id ? nueva : c)) : [nueva, ...lista]));
    setCitas((m) => {
      const copia = new Map(m);
      Object.values(api.fuentes).forEach((f) => copia.set(f.ref, aCita(f)));
      return copia;
    });
  }, []);

  const modificar = useCallback(
    (id: string, fn: (c: Cotizacion) => Cotizacion) => setCotizaciones((lista) => lista.map((c) => (c.id === id ? fn(c) : c))),
    [],
  );

  const valor = useMemo<Almacen>(() => {
    const restaurar = (antes: Cotizacion | undefined) => antes && setCotizaciones((lista) => lista.map((c) => (c.id === antes.id ? antes : c)));

    return {
      usuario,
      usuarios,
      cambiarUsuario: setUsuarioId,
      puedeAprobar: usuario.rol !== 'Vendedor',
      esAdministrador: usuario.rol === 'Administrador',
      cotizaciones,
      documentos,
      memoria,
      bitacora,
      ajustes,
      citas: [...citas.values()],
      cargando,
      errorCarga,
      recargar: () => void cargarTodo(),
      toasts,
      avisar,
      cerrarToast,
      citaPorId: (id) => citas.get(id),
      documentoPorId: (id) => documentos.find((d) => d.id === id),

      crearCotizacion: async (solicitud, archivos = []) => {
        const r = archivos.length > 0 ? await crearCotizacionDesdeArchivosApi(solicitud, archivos) : await crearCotizacionApi(solicitud);
        if (r.tipo === 'cotizacion') reemplazar(r.cotizacion);
        if (r.tipo !== 'conversacion') refrescarBitacora();
        return r;
      },

      actualizarPartida: (cotizacionId, escenario, partidaId, cambios) => {
        const antes = cotRef.current.find((c) => c.id === cotizacionId);
        const actual = antes?.escenarios[escenario].partidas.find((p) => p.id === partidaId);
        if (!antes || !actual) return;
        const detalle: string[] = [];
        if (cambios.cantidad !== undefined && cambios.cantidad !== actual.cantidad) detalle.push(`cantidad ${actual.cantidad} → ${cambios.cantidad}`);
        if (cambios.precioUnitario !== undefined && cambios.precioUnitario !== actual.precioUnitario)
          detalle.push(`precio ${formatoMXN(actual.precioUnitario)} → ${formatoMXN(cambios.precioUnitario)}`);
        if (detalle.length === 0) return;
        // Se pinta de inmediato (el recálculo se siente instantáneo) y se confirma con el servidor.
        modificar(cotizacionId, (c) => ({
          ...c,
          escenarios: {
            ...c.escenarios,
            [escenario]: {
              ...c.escenarios[escenario],
              partidas: c.escenarios[escenario].partidas.map((p) => (p.id === partidaId ? { ...p, ...cambios, editadaPor: usuario.nombre } : p)),
            },
          },
          historial: [...c.historial, { fecha: ahoraISO(), usuario: usuario.nombre, texto: `Editó «${actual.concepto}» (${etiquetaEscenario(escenario)}): ${detalle.join(', ')}.` }],
        }));
        editarPartidaApi(cotizacionId, partidaId, {
          cantidad: cambios.cantidad,
          precio_unitario_centavos: cambios.precioUnitario,
        })
          .then(reemplazar)
          .catch((e) => {
            restaurar(antes);
            avisar(`No se guardó el cambio: ${mensajeDe(e)}`, 'error');
          });
      },

      actualizarNotas: (cotizacionId, escenario, notas) => {
        const antes = cotRef.current.find((c) => c.id === cotizacionId);
        if (!antes || antes.escenarios[escenario].notas === notas) return;
        modificar(cotizacionId, (c) => ({ ...c, escenarios: { ...c.escenarios, [escenario]: { ...c.escenarios[escenario], notas } } }));
        editarNotasApi(cotizacionId, escenario, notas)
          .then(reemplazar)
          .catch((e) => {
            restaurar(antes);
            avisar(`No se guardaron las notas: ${mensajeDe(e)}`, 'error');
          });
      },

      enviarARevision: async (cotizacionId) => {
        try {
          reemplazar(await enviarARevisionApi(cotizacionId));
          return true;
        } catch (e) {
          avisar(mensajeDe(e), 'error');
          return false;
        }
      },

      aprobar: async (cotizacionId, escenario) => {
        try {
          reemplazar(await aprobarApi(cotizacionId, escenario));
          refrescarBitacora();
          return true;
        } catch (e) {
          avisar(mensajeDe(e), 'error');
          return false;
        }
      },

      rechazar: async (cotizacionId, motivo) => {
        try {
          reemplazar(await rechazarApi(cotizacionId, motivo));
          return true;
        } catch (e) {
          avisar(mensajeDe(e), 'error');
          return false;
        }
      },

      descargarPdf: async (cotizacionId) => {
        try {
          const { blob, nombre } = await descargarPdfApi(cotizacionId);
          const url = URL.createObjectURL(blob);
          const enlace = Object.assign(document.createElement('a'), { href: url, download: nombre });
          document.body.appendChild(enlace);
          enlace.click();
          enlace.remove();
          URL.revokeObjectURL(url);
          refrescarBitacora();
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },

      // --------------------------------------------------------------------- memoria
      guardarAprendizaje: async (cotizacionId, texto) => {
        const folio = cotRef.current.find((c) => c.id === cotizacionId)?.folio ?? cotizacionId;
        try {
          const h = await proponerHechoApi(texto, `Cot. ${folio} aprobada por ${usuario.nombre}`);
          setMemoria((m) => [aHecho(h), ...m]);
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },
      editarHecho: async (id, texto) => {
        try {
          const h = aHecho(await editarHechoApi(id, { texto }));
          setMemoria((m) => m.map((x) => (x.id === id ? h : x)));
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },
      alternarPausa: async (id) => {
        const actual = memoria.find((h) => h.id === id);
        if (!actual) return;
        try {
          const h = aHecho(await editarHechoApi(id, { estado: actual.estado === 'Activa' ? 'Pausada' : 'Activa' }));
          setMemoria((m) => m.map((x) => (x.id === id ? h : x)));
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },
      confirmarHecho: async (id) => {
        try {
          const h = aHecho(await confirmarHechoApi(id));
          setMemoria((m) => m.map((x) => (x.id === id ? h : x)));
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },
      borrarHecho: async (id) => {
        try {
          await borrarHechoApi(id);
          setMemoria((m) => m.filter((x) => x.id !== id));
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },

      borrarDatos: async () => {
        try {
          const r = await borrarDatosApi();
          avisar(`Se borraron ${r.borrado.cotizaciones} cotizaciones, ${r.borrado.hechos_memoria} hechos de memoria y ${r.borrado.entradas_bitacora} entradas de bitácora.`, 'info');
          await cargarTodo();
        } catch (e) {
          avisar(mensajeDe(e), 'error');
        }
      },
    };
  }, [usuario, usuarios, cotizaciones, documentos, memoria, bitacora, ajustes, citas, cargando, errorCarga, toasts, avisar, cerrarToast, modificar, reemplazar, cargarTodo, refrescarBitacora]);

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
