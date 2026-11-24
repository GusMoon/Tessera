// Historial del chat: tipos y funciones puras para guardarlo en el navegador (localStorage), una lista por usuario.
// Solo se guardan textos y nombres de archivo; los archivos adjuntos no (pesan y pueden ser de la empresa).

export interface Mensaje {
  id: number;
  rol: 'usuario' | 'tessera';
  texto: string;
  archivos?: string[]; // nombres de los archivos que viajaron con este mensaje
  meta?: string; // modelo · latencia · tokens
  avisos?: string[];
  error?: boolean;
  cotizacionId?: string; // la cotización que se creó con este mensaje (se muestra como tarjeta)
}

export interface Conversacion {
  id: string;
  titulo: string;
  creada: string; // ISO 8601
  actualizada: string; // ISO 8601
  mensajes: Mensaje[];
}

export const MAX_CONVERSACIONES = 40;
export const MAX_MENSAJES = 200;
const VERSION = 1;

type Almacenamiento = Pick<Storage, 'getItem' | 'setItem'>;

const claveLista = (usuarioId: string) => `tessera.chat.v${VERSION}.${usuarioId}`;
const claveActiva = (usuarioId: string) => `tessera.chat.v${VERSION}.${usuarioId}.activa`;

/** Título de la conversación: lo primero que pidió el usuario (o el nombre del primer archivo). */
export function tituloDe(texto: string, archivos: string[] = []): string {
  const limpio = texto.replace(/\s+/g, ' ').trim();
  const base = limpio || (archivos.length > 0 ? `Archivos: ${archivos.join(', ')}` : 'Conversación');
  return base.length > 60 ? `${base.slice(0, 57).trimEnd()}…` : base;
}

export const siguienteIdMensaje = (mensajes: Mensaje[]) => mensajes.reduce((m, x) => Math.max(m, x.id), 0) + 1;

/** Deja las más recientes y recorta los mensajes de cada una, para no llenar el almacenamiento del navegador. */
export function recortar(conversaciones: Conversacion[]): Conversacion[] {
  return [...conversaciones]
    .sort((a, b) => b.actualizada.localeCompare(a.actualizada))
    .slice(0, MAX_CONVERSACIONES)
    .map((c) => (c.mensajes.length > MAX_MENSAJES ? { ...c, mensajes: c.mensajes.slice(-MAX_MENSAJES) } : c));
}

const esMensaje = (m: unknown): m is Mensaje => {
  const x = m as Partial<Mensaje> | null;
  return !!x && typeof x.id === 'number' && (x.rol === 'usuario' || x.rol === 'tessera') && typeof x.texto === 'string';
};

const esConversacion = (c: unknown): c is Conversacion => {
  const x = c as Partial<Conversacion> | null;
  return !!x && typeof x.id === 'string' && typeof x.titulo === 'string' && typeof x.actualizada === 'string' && Array.isArray(x.mensajes) && x.mensajes.every(esMensaje);
};

/** Lee el historial de un usuario. Un dato dañado o de otra versión se ignora: nunca debe romper la pantalla. */
export function cargarConversaciones(almacen: Almacenamiento, usuarioId: string): { conversaciones: Conversacion[]; activaId: string | null } {
  try {
    const crudo = JSON.parse(almacen.getItem(claveLista(usuarioId)) ?? '[]');
    const conversaciones = Array.isArray(crudo) ? recortar(crudo.filter(esConversacion)) : [];
    const activa = almacen.getItem(claveActiva(usuarioId));
    return { conversaciones, activaId: conversaciones.some((c) => c.id === activa) ? activa : null };
  } catch {
    return { conversaciones: [], activaId: null };
  }
}

/** Guarda el historial de un usuario. Si el navegador no deja (cuota llena, modo privado), el chat sigue funcionando sin guardarse. */
export function guardarConversaciones(almacen: Almacenamiento, usuarioId: string, conversaciones: Conversacion[], activaId: string | null): boolean {
  try {
    almacen.setItem(claveLista(usuarioId), JSON.stringify(recortar(conversaciones)));
    almacen.setItem(claveActiva(usuarioId), activaId ?? '');
    return true;
  } catch {
    return false;
  }
}

/** «dd/mm/aaaa hh:mm» (formato de la interfaz) a partir de una fecha ISO. */
export function fechaCorta(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const dos = (n: number) => String(n).padStart(2, '0');
  return `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}
