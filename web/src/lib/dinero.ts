// Dinero exacto: todo importe se maneja como entero de centavos (nunca flotantes).
// Formato del proyecto: $12,400.00 MXN y fechas dd/mm/aaaa (CLAUDE.md, Convenciones).

export type Centavos = number;

/** Fecha fija del prototipo para que la antigüedad de precios sea reproducible. */
export const FECHA_REFERENCIA = '2026-11-21';

/** Umbral de aviso de precio antiguo. [Propuesta] Se confirma con la Persona A. */
export const UMBRAL_ANTIGUEDAD_MESES = 6;

const formateadorMXN = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatoPesos(c: Centavos): string {
  // Asegura redondeo exacto de centavos antes de formatear
  const pesos = Math.round(c) / 100;
  return formateadorMXN.format(pesos);
}

export function formatoMXN(c: Centavos): string {
  return `${formatoPesos(c)} MXN`;
}

/** Convierte texto como "4,850.5" o "$4850.50 MXN" a centavos. Devuelve null si no es válido. */
export function parsePesos(texto: string): Centavos | null {
  const limpio = texto.replace(/MXN/gi, '').replace(/[\s$,]/g, '');
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(limpio);
  if (!m) return null;
  const fraccion = (m[2] ?? '').padEnd(2, '0');
  return Number(m[1]) * 100 + Number(fraccion);
}

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** Formato corto de fecha: "24 nov 2026" sin desbordamiento */
export function formatoFechaCorta(iso: string): string {
  if (!iso) return '';
  const [a, m, d] = iso.slice(0, 10).split('-');
  const mesNum = parseInt(m, 10);
  const mesNom = MESES_CORTOS[mesNum - 1] || m;
  return `${parseInt(d, 10)} ${mesNom} ${a}`;
}

/** ISO 8601 (aaaa-mm-dd...) a dd/mm/aaaa, sin pasar por zonas horarias. */
export function formatoFecha(iso: string): string {
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
}

export function formatoFechaHora(iso: string): string {
  return `${formatoFecha(iso)} ${iso.slice(11, 16)}`;
}

/** Meses completos transcurridos entre `iso` y la referencia. */
export function mesesDeAntiguedad(iso: string, referencia: string = FECHA_REFERENCIA): number {
  const [a1, m1, d1] = iso.slice(0, 10).split('-').map(Number);
  const [a2, m2, d2] = referencia.split('-').map(Number);
  let meses = (a2 - a1) * 12 + (m2 - m1);
  if (d2 < d1) meses -= 1;
  return Math.max(0, meses);
}

export function textoMeses(meses: number): string {
  return meses === 1 ? '1 mes' : `${meses} meses`;
}

/** Días completos entre `iso` y la referencia (sin zonas horarias). */
export function diasDeAntiguedad(iso: string, referencia: string = FECHA_REFERENCIA): number {
  const [a1, m1, d1] = iso.slice(0, 10).split('-').map(Number);
  const [a2, m2, d2] = referencia.split('-').map(Number);
  const ms = Date.UTC(a2, m2 - 1, d2) - Date.UTC(a1, m1 - 1, d1);
  return Math.max(0, Math.round(ms / 86_400_000));
}

/** «hoy», «ayer», «hace 5 días», «hace 3 meses», «hace 2 años». */
export function textoRelativo(iso: string, referencia: string = FECHA_REFERENCIA): string {
  const dias = diasDeAntiguedad(iso, referencia);
  if (dias === 0) return 'hoy';
  if (dias === 1) return 'ayer';
  if (dias < 30) return `hace ${dias} días`;
  const meses = mesesDeAntiguedad(iso, referencia);
  if (meses < 12) return `hace ${textoMeses(Math.max(1, meses))}`;
  const anios = Math.floor(meses / 12);
  return anios === 1 ? 'hace 1 año' : `hace ${anios} años`;
}

/** Fecha y hora local actual como ISO sin zona (aaaa-mm-ddThh:mm). */
export function ahoraISO(): string {
  const n = new Date();
  const p = (x: number) => String(x).padStart(2, '0');
  return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}T${p(n.getHours())}:${p(n.getMinutes())}`;
}
