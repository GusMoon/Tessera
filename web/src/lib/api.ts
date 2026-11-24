/** Cliente de la ruta de chat (`api/chat.py`). Contrato en `docs/contratos.md`. */

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
export class ErrorApi extends Error {}

const SIN_CONEXION = 'No se pudo conectar con la API. ¿Está corriendo el backend? (uvicorn api.main:app --port 8000)';

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

export async function obtenerConfigChat(): Promise<ConfigChat> {
  let res: Response;
  try {
    res = await fetch('/api/chat/config');
  } catch {
    throw new ErrorApi(SIN_CONEXION);
  }
  if (!res.ok) throw new ErrorApi(await detalleDeError(res));
  return res.json();
}

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
  let res: Response;
  try {
    res = await fetch('/api/chat', { method: 'POST', body: datos, signal: params.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e; // la cancelación la maneja quien llama
    throw new ErrorApi(SIN_CONEXION);
  }
  if (!res.ok) throw new ErrorApi(await detalleDeError(res));
  return res.json();
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

export async function obtenerUsoChat(): Promise<UsoChat> {
  let res: Response;
  try {
    res = await fetch('/api/chat/uso');
  } catch {
    throw new ErrorApi(SIN_CONEXION);
  }
  if (!res.ok) throw new ErrorApi(await detalleDeError(res));
  return res.json();
}
