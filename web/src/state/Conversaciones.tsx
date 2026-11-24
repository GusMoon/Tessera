import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { enviarChat } from '../lib/api';
import {
  cargarConversaciones,
  guardarConversaciones,
  siguienteIdMensaje,
  tituloDe,
  type Conversacion,
  type Mensaje,
} from '../lib/conversaciones';
import { useAlmacen } from './Almacen';

export const MAX_ARCHIVOS = 5; // igual que api/chat.py

const TEXTO_SOLO_ARCHIVOS = 'Cotiza lo que piden los archivos adjuntos.';

interface ChatEstado {
  /** Historial del usuario activo, la más reciente primero. */
  conversaciones: Conversacion[];
  activa: Conversacion | null;
  mensajes: Mensaje[];
  /** Hay una consulta en curso (el modelo o el cálculo siguen trabajando aunque cambies de pantalla). */
  enviando: boolean;
  /** …y es de la conversación que está abierta. */
  enviandoAqui: boolean;
  /** Cuántas consultas han terminado: la pantalla lo usa para refrescar la cuota. */
  terminadas: number;
  /** Falso si el navegador no dejó guardar el historial (espacio lleno o modo privado). */
  guardado: boolean;
  texto: string;
  setTexto: (t: string) => void;
  archivos: File[];
  agregarArchivos: (nuevos: File[]) => void;
  quitarArchivo: (archivo: File) => void;
  enviar: (texto?: string) => Promise<void>;
  cancelar: () => void;
  nueva: () => void;
  abrir: (id: string) => void;
  borrar: (id: string) => void;
}

const Contexto = createContext<ChatEstado | null>(null);

export const useChat = () => {
  const c = useContext(Contexto);
  if (!c) throw new Error('useChat debe usarse dentro de ProveedorConversaciones');
  return c;
};

const idNuevo = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

/** Mensajes y archivos del chat. Viven aquí, no en la página, para que no se pierdan al cambiar de pestaña. */
export function ProveedorConversaciones({ children }: { children: ReactNode }) {
  const { usuario, crearCotizacion } = useAlmacen();
  const [conversaciones, setConversaciones] = useState<Conversacion[]>([]);
  const [activaId, setActivaId] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [archivos, setArchivos] = useState<File[]>([]);
  const [enviandoEn, setEnviandoEn] = useState<string | null>(null);
  const [terminadas, setTerminadas] = useState(0);
  const [guardado, setGuardado] = useState(true);
  const [cargadoPara, setCargadoPara] = useState('');

  // Espejos para el código asíncrono, que no debe leer valores de un render anterior.
  const convRef = useRef<Conversacion[]>([]);
  const activaRef = useRef<string | null>(null);
  const archivosRef = useRef<File[]>([]);
  const textoRef = useRef('');
  const enviandoRef = useRef(false);
  const control = useRef<AbortController | null>(null);
  activaRef.current = activaId;
  archivosRef.current = archivos;
  textoRef.current = texto;

  const aplicar = useCallback((fn: (previas: Conversacion[]) => Conversacion[]) => {
    const nuevas = fn(convRef.current);
    convRef.current = nuevas;
    setConversaciones(nuevas);
  }, []);

  // Al cambiar de usuario se carga su historial (cada uno tiene el suyo).
  useEffect(() => {
    if (!usuario.id) return;
    control.current?.abort();
    const { conversaciones: guardadas, activaId: abierta } = cargarConversaciones(window.localStorage, usuario.id);
    convRef.current = guardadas;
    setConversaciones(guardadas);
    setActivaId(abierta);
    setArchivos([]);
    setTexto('');
    setEnviandoEn(null);
    enviandoRef.current = false;
    setCargadoPara(usuario.id);
  }, [usuario.id]);

  // Cada cambio se guarda, pero solo después de haber cargado el del usuario actual (para no pisarlo con una lista vacía).
  useEffect(() => {
    if (!usuario.id || cargadoPara !== usuario.id) return;
    setGuardado(guardarConversaciones(window.localStorage, usuario.id, conversaciones, activaId));
  }, [conversaciones, activaId, usuario.id, cargadoPara]);

  const agregarMensaje = useCallback(
    (convId: string, m: Omit<Mensaje, 'id'>) =>
      aplicar((previas) =>
        previas.map((c) =>
          c.id === convId ? { ...c, mensajes: [...c.mensajes, { ...m, id: siguienteIdMensaje(c.mensajes) }], actualizada: new Date().toISOString() } : c,
        ),
      ),
    [aplicar],
  );

  const agregarArchivos = useCallback((nuevos: File[]) => {
    if (nuevos.length === 0) return;
    setArchivos((actuales) => {
      const unicos = nuevos.filter((n) => !actuales.some((a) => a.name === n.name && a.size === n.size));
      return [...actuales, ...unicos].slice(0, MAX_ARCHIVOS);
    });
  }, []);

  const quitarArchivo = useCallback((archivo: File) => setArchivos((as) => as.filter((x) => x !== archivo)), []);

  const enviar = useCallback(
    async (entrada?: string) => {
      const adjuntos = archivosRef.current;
      const escrito = (entrada ?? textoRef.current).trim();
      const limpio = escrito || (adjuntos.length > 0 ? TEXTO_SOLO_ARCHIVOS : '');
      if (!limpio || enviandoRef.current) return;

      // La conversación se crea con el primer mensaje: abrir «Nueva» sin escribir no deja entradas vacías en el historial.
      let id = activaRef.current;
      const ahora = new Date().toISOString();
      if (!id || !convRef.current.some((c) => c.id === id)) {
        id = idNuevo();
        const nueva: Conversacion = { id, titulo: tituloDe(escrito, adjuntos.map((a) => a.name)), creada: ahora, actualizada: ahora, mensajes: [] };
        aplicar((previas) => [nueva, ...previas]);
        activaRef.current = id;
        setActivaId(id);
      }
      const convId = id;
      const historial = (convRef.current.find((c) => c.id === convId)?.mensajes ?? []).filter((m) => !m.error).map((m) => ({ rol: m.rol, texto: m.texto }));

      agregarMensaje(convId, { rol: 'usuario', texto: limpio, archivos: adjuntos.map((a) => a.name) });
      setTexto('');
      enviandoRef.current = true;
      setEnviandoEn(convId);
      const controlador = new AbortController();
      control.current = controlador;
      try {
        // Una solicitud de materiales con cantidades (escrita o en un archivo) se cotiza con las fuentes cargadas, con código
        // determinista. Lo que no es una solicitud (una pregunta, una imagen) lo atiende el modelo de conversación.
        const c = await crearCotizacion(limpio, adjuntos);
        if (c.tipo === 'cotizacion') {
          const origen = c.redaccion.origen === 'llm' ? `notas redactadas por ${c.redaccion.modelo}` : c.redaccion.origen === 'demo' ? 'notas de demostración' : 'sin notas del modelo';
          const deArchivos = adjuntos.length > 0 ? `Leí ${adjuntos.length === 1 ? 'el archivo' : `los ${adjuntos.length} archivos`} y p` : 'P';
          agregarMensaje(convId, {
            rol: 'tessera',
            texto: `${deArchivos}reparé la cotización **${c.cotizacion.folio}** con tres escenarios a partir de ${Object.keys(c.cotizacion.fuentes).length} fuentes. Los importes los calculó código determinista, no el modelo: revisa las partidas y sus fuentes antes de aprobar.`,
            avisos: [...c.avisos, ...(c.redaccion.aviso ? [c.redaccion.aviso] : [])],
            meta: `${Math.round(c.tiempos_ms.total)} ms en recuperar y calcular · ${origen}`,
            cotizacionId: c.cotizacion.id,
          });
          setArchivos([]); // ya se usaron: no deben volver a cotizarse con el siguiente mensaje
          return;
        }
        if (c.tipo === 'aclaracion') {
          const conArchivos = adjuntos.length > 0;
          agregarMensaje(convId, {
            rol: 'tessera',
            texto: `Antes de calcular necesito aclarar esto:\n${c.preguntas.map((q) => `• ${q}`).join('\n')}\n\n${
              conArchivos
                ? 'Escribe en tu mensaje el dato que falta (con su cantidad, si es un material) y vuelve a enviar: los archivos siguen adjuntos.'
                : 'Edita tu solicitud con el dato que falta y vuelve a enviarla.'
            }`,
            avisos: c.avisos,
          });
          if (!conArchivos) setTexto(limpio);
          return;
        }
        const r = await enviarChat({ mensaje: limpio, historial, archivos: adjuntos, signal: controlador.signal });
        agregarMensaje(convId, { rol: 'tessera', texto: r.texto || '(sin respuesta)', meta: `${r.modelo} · ${r.latencia_s.toFixed(1)} s`, avisos: r.avisos, error: !r.texto });
      } catch (e) {
        const abortado = e instanceof DOMException && e.name === 'AbortError';
        agregarMensaje(convId, {
          rol: 'tessera',
          texto: abortado ? 'Cancelaste la consulta. No se generó ninguna respuesta.' : e instanceof Error ? e.message : 'Error inesperado.',
          error: true,
        });
      } finally {
        enviandoRef.current = false;
        setEnviandoEn(null);
        control.current = null;
        setTerminadas((n) => n + 1);
      }
    },
    [agregarMensaje, aplicar, crearCotizacion],
  );

  const cancelar = useCallback(() => control.current?.abort(), []);

  const nueva = useCallback(() => {
    control.current?.abort();
    activaRef.current = null;
    setActivaId(null);
    setArchivos([]);
    setTexto('');
  }, []);

  const abrir = useCallback((id: string) => {
    if (!convRef.current.some((c) => c.id === id)) return;
    activaRef.current = id;
    setActivaId(id);
  }, []);

  const borrar = useCallback(
    (id: string) => {
      if (enviandoRef.current && activaRef.current === id) control.current?.abort();
      aplicar((previas) => previas.filter((c) => c.id !== id));
      if (activaRef.current === id) {
        activaRef.current = null;
        setActivaId(null);
      }
    },
    [aplicar],
  );

  const ordenadas = useMemo(() => [...conversaciones].sort((a, b) => b.actualizada.localeCompare(a.actualizada)), [conversaciones]);
  const activa = ordenadas.find((c) => c.id === activaId) ?? null;

  const valor: ChatEstado = {
    conversaciones: ordenadas,
    activa,
    mensajes: activa?.mensajes ?? [],
    enviando: enviandoEn !== null,
    enviandoAqui: enviandoEn !== null && enviandoEn === activaId,
    terminadas,
    guardado,
    texto,
    setTexto,
    archivos,
    agregarArchivos,
    quitarArchivo,
    enviar,
    cancelar,
    nueva,
    abrir,
    borrar,
  };
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}
