/** Clientes de la API (`api/*.py`). Contratos en `docs/contratos.md`; permisos por rol en `docs/permisos.md`. */

export interface AdjuntoInfo {
  nombre: string;
  tipo: 'texto' | 'imagen' | string;
  detalle: string;
  truncado: boolean;
}

export interface RespuestaChat {
  texto: string;
  modelo: string;
  proveedor: string;
  latencia_s: number;
  tokens_entrada: number;
  tokens_salida: number;
  adjuntos: AdjuntoInfo[];
  avisos: string[];
}

export interface ConfigChat {
  proveedor: string;
  modelo: string;
  modelo_vision: string | null;
}

export interface TurnoHistorial {
  rol: 'usuario' | 'tessera';
  texto: string;
}

/** Error con un mensaje apto para mostrarse al usuario. */
export class ErrorApi extends Error {
  constructor(mensaje: string, readonly estado?: number) {
    super(mensaje);
  }
}

export const SIN_CONEXION = 'No se pudo conectar con la API. ¿Está corriendo el backend? (uvicorn api.main:app --port 8000)';

// Prototipo: la identidad es el id del usuario elegido en la interfaz, enviada en X-Usuario-Id. No es autenticación real.
let usuarioActivoId: string | null = null;
export function fijarUsuarioActivo(id: string | null): void {
  usuarioActivoId = id;
}

async function detalleDeError(res: Response): Promise<string> {
  try {
    const cuerpo = await res.json();
    const d = cuerpo?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  } catch {
    /* el cuerpo no es JSON: pasa a los mensajes genéricos */
  }
  // El proxy de Vite responde 5xx sin cuerpo útil cuando el backend está apagado.
  return res.status >= 500 ? SIN_CONEXION : `Error ${res.status} de la API.`;
}

/** `fetch` con la identidad del usuario activo. Convierte los fallos de red en un `ErrorApi` legible. */
export async function fetchApi(url: string, init: RequestInit = {}): Promise<Response> {
  const cabeceras = new Headers(init.headers);
  if (usuarioActivoId) cabeceras.set('X-Usuario-Id', usuarioActivoId);
  try {
    return await fetch(url, { ...init, headers: cabeceras });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e; // la cancelación la maneja quien llama
    throw new ErrorApi(SIN_CONEXION);
  }
}

async function pedirJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const res = await fetchApi(url, init);
  if (!res.ok) throw new ErrorApi(await detalleDeError(res), res.status);
  return res.status === 204 ? (undefined as T) : res.json();
}

const enJson = (metodo: string, cuerpo?: unknown): RequestInit => ({
  method: metodo,
  headers: { 'Content-Type': 'application/json' },
  body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
});

// --------------------------------------------------------------------------- chat
export const obtenerConfigChat = () => pedirJson<ConfigChat>('/api/chat/config');

export async function enviarChat(params: {
  mensaje: string;
  historial: TurnoHistorial[];
  archivos: File[];
  signal?: AbortSignal;
}): Promise<RespuestaChat> {
  const datos = new FormData();
  datos.append('mensaje', params.mensaje);
  datos.append('historial', JSON.stringify(params.historial));
  params.archivos.forEach((a) => datos.append('archivos', a, a.name));
  return pedirJson<RespuestaChat>('/api/chat', { method: 'POST', body: datos, signal: params.signal });
}

export interface UsoChat {
  proveedor: string;
  modelo: string;
  /** «peticiones» (OpenRouter :free no limita por tokens), «peticiones y tokens» (Groq) o «ninguno» (modelo local). */
  tipo_limite: 'peticiones' | 'peticiones y tokens' | 'ninguno' | string;
  plan_gratuito: boolean | null;
  dia: { usadas: number | null; limite: number | null; restantes: number | null } | null;
  reinicio_dia_utc: string | null;
  /** «dia_utc»: se reinicia a las 00:00 UTC (OpenRouter). «recarga»: se recarga de forma continua y la fecha es cuándo vuelve a estar completa (Groq). */
  reinicio_modo: 'dia_utc' | 'recarga' | null;
  minuto: { usadas_aqui: number; limite: number; segundos_para_liberar: number | null } | null;
  /** Solo Groq: lo que informó en la última respuesta. */
  tokens_minuto: { restantes: number | null; limite: number | null; segundos_para_reiniciar: number | null } | null;
  sesion: { llamadas: number; tokens_entrada: number; tokens_salida: number; tokens_total: number };
  aviso: string | null;
}

export const obtenerUsoChat = () => pedirJson<UsoChat>('/api/chat/uso');

// --------------------------------------------------------------------------- usuarios, fuentes
export interface UsuarioApi {
  id: string;
  nombre: string;
  rol: 'Vendedor' | 'Responsable comercial' | 'Administrador';
}
export const listarUsuarios = () => pedirJson<UsuarioApi[]>('/api/usuarios');

export interface FuenteApi {
  id: number;
  nombre: string;
  tipo: string;
  estado: 'Listo' | 'Procesando' | 'Error' | 'Omitido';
  leidas: number;
  guardadas: number;
  rechazadas: number;
  omitidas: number;
  motivo?: string | null;
  fecha_carga: string;
  permiso: 'Todos' | 'Comercial' | 'Administración';
}
export const listarFuentes = () => pedirJson<FuenteApi[]>('/api/fuentes');

// --------------------------------------------------------------------------- cotizaciones
export interface PartidaApi {
  id: string;
  tipo: 'material' | 'servicio';
  codigo: string;
  concepto: string;
  unidad: string;
  cantidad: number;
  costo_unitario_centavos: number;
  precio_unitario_centavos: number;
  importe_centavos: number;
  fuente_ref: string;
  fuente_fecha: string | null;
  antiguedad_meses: number;
  precio_antiguo: boolean;
  editada_por: string | null;
}

export interface TotalesApi {
  subtotal_centavos: number;
  iva_centavos: number;
  total_centavos: number;
  costo_centavos: number;
  margen_centavos: number;
  margen_puntos_base: number | null;
}

export interface FuenteCitadaApi {
  ref: string;
  etiqueta: string;
  fecha: string | null;
  ubicacion: string;
  extracto: string | null;
  fuente_id: number | null;
  documento: string | null;
  permiso: 'Todos' | 'Comercial' | 'Administración' | null;
  restringido: boolean;
  disponible: boolean;
}

export type IdEscenarioApi = 'economico' | 'recomendado' | 'premium';

export interface CotizacionApi {
  id: string;
  folio: string;
  cliente: string;
  solicitud: string;
  fecha: string;
  estado: 'Borrador' | 'En revisión' | 'Aprobada' | 'Rechazada';
  creada_por: string;
  escenario_aprobado: IdEscenarioApi | null;
  motivo_rechazo: string | null;
  aprobada_por: string | null;
  fecha_aprobacion: string | null;
  escenarios: Record<IdEscenarioApi, { notas: string; riesgos: string[]; margen_objetivo_puntos_base: number; partidas: PartidaApi[]; totales: TotalesApi }>;
  historial: { fecha: string; usuario: string; texto: string }[];
  avisos: string[];
  parecidas: { ref: string; folio: string; cliente: string | null; fecha: string }[];
  fuentes: Record<string, FuenteCitadaApi>;
}

export type ResultadoSolicitud =
  | { tipo: 'cotizacion'; cotizacion: CotizacionApi; avisos: string[]; tiempos_ms: { total: number }; redaccion: { origen: string; modelo: string | null; aviso: string | null } }
  | { tipo: 'aclaracion'; preguntas: string[]; avisos: string[]; tiempos_ms: { total: number } }
  | { tipo: 'conversacion'; avisos?: string[] };

export const listarCotizaciones = () => pedirJson<CotizacionApi[]>('/api/cotizaciones');
export const crearCotizacionApi = (solicitud: string) => pedirJson<ResultadoSolicitud>('/api/cotizaciones', enJson('POST', { solicitud }));
/** Cotiza lo que piden los archivos (PDF, Excel, CSV o texto de chat), solos o con un mensaje. Los lee el servidor, sin modelo. */
export function crearCotizacionDesdeArchivosApi(mensaje: string, archivos: File[]): Promise<ResultadoSolicitud> {
  const datos = new FormData();
  datos.append('mensaje', mensaje);
  archivos.forEach((a) => datos.append('archivos', a, a.name));
  return pedirJson<ResultadoSolicitud>('/api/cotizaciones/desde-archivos', { method: 'POST', body: datos });
}
export const editarPartidaApi = (cotId: string, partidaId: string, cambios: { cantidad?: number; precio_unitario_centavos?: number }) =>
  pedirJson<CotizacionApi>(`/api/cotizaciones/${cotId}/partidas/${partidaId}`, enJson('PATCH', cambios));
export const editarNotasApi = (cotId: string, escenario: IdEscenarioApi, notas: string) =>
  pedirJson<CotizacionApi>(`/api/cotizaciones/${cotId}/escenarios/${escenario}`, enJson('PATCH', { notas }));
export const enviarARevisionApi = (cotId: string) => pedirJson<CotizacionApi>(`/api/cotizaciones/${cotId}/enviar`, enJson('POST'));
export const aprobarApi = (cotId: string, escenario: IdEscenarioApi) =>
  pedirJson<CotizacionApi>(`/api/cotizaciones/${cotId}/aprobar`, enJson('POST', { escenario }));
export const rechazarApi = (cotId: string, motivo: string) => pedirJson<CotizacionApi>(`/api/cotizaciones/${cotId}/rechazar`, enJson('POST', { motivo }));

/** Descarga el PDF de una cotización aprobada. El servidor responde 409 si no hay aprobación registrada. */
export async function descargarPdfApi(cotId: string): Promise<{ blob: Blob; nombre: string }> {
  const res = await fetchApi(`/api/cotizaciones/${cotId}/pdf`);
  if (!res.ok) throw new ErrorApi(await detalleDeError(res), res.status);
  const nombre = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? `Cotizacion-${cotId}.pdf`;
  return { blob: await res.blob(), nombre };
}

// --------------------------------------------------------------------------- memoria, bitácora, ajustes
export interface HechoApi {
  id: string;
  texto: string;
  origen: string;
  fecha: string;
  estado: 'Activa' | 'Pausada';
  por_confirmar: boolean;
}
export const listarMemoriaApi = () => pedirJson<HechoApi[]>('/api/memoria');
export const proponerHechoApi = (texto: string, origen?: string) => pedirJson<HechoApi>('/api/memoria', enJson('POST', { texto, origen }));
export const editarHechoApi = (id: string, cambios: { texto?: string; estado?: 'Activa' | 'Pausada' }) =>
  pedirJson<HechoApi>(`/api/memoria/${id}`, enJson('PATCH', cambios));
export const confirmarHechoApi = (id: string) => pedirJson<HechoApi>(`/api/memoria/${id}/confirmar`, enJson('POST'));
export const borrarHechoApi = (id: string) => pedirJson<void>(`/api/memoria/${id}`, { method: 'DELETE' });

export interface EntradaBitacoraApi {
  id: string;
  fecha: string;
  usuario: string;
  pregunta: string;
  documentos: string[];
  herramientas: string[];
  duracion_ms: number;
  cotizacion: string | null;
  aprobado_por: string | null;
}
export const listarBitacoraApi = () => pedirJson<EntradaBitacoraApi[]>('/api/bitacora');

export interface AjustesApi {
  proveedor: string;
  modelo: string;
  modo_demo: boolean;
  embedder: string;
  fragmentos_indexados: number;
  ultima_cotizacion_ms: { interpretar: number; historial: number; calculo: number; total: number } | null;
  evaluacion: { archivo: string; fecha: string; embedder: string; mediana_ms: number; p95_ms: number; exactitud: number; casos: number; aprobado: boolean } | null;
  cotizaciones: number;
  hechos_memoria: number;
}
export const obtenerAjustesApi = () => pedirJson<AjustesApi>('/api/ajustes');
export const borrarDatosApi = () =>
  pedirJson<{ ok: boolean; borrado: { cotizaciones: number; hechos_memoria: number; entradas_bitacora: number } }>('/api/datos', { method: 'DELETE' });
