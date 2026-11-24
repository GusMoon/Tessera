/** Divide un texto en tramos normales y en **negrita** (el único formato Markdown que se interpreta). */
export interface Tramo {
  texto: string;
  negrita: boolean;
}

export function tramosConNegrita(texto: string): Tramo[] {
  // Con un grupo de captura, `split` deja las coincidencias en las posiciones impares.
  return texto
    .split(/\*\*([^*\n]+)\*\*/g)
    .map((t, i) => ({ texto: t, negrita: i % 2 === 1 }))
    .filter((t) => t.texto !== '');
}

/** Resume el tamaño de un archivo para mostrarlo en la lista de adjuntos. */
export function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** «45 s», «12 min», «5 h 12 min». */
export function duracionCorta(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  if (s < 90) return `${s} s`;
  const minutos = Math.round(s / 60);
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  return resto ? `${horas} h ${resto} min` : `${horas} h`;
}

/** «a las 18:00 (en 5 h 12 min)»; si cae en otro día local, «mañana a las 18:00 …». Hora local del navegador. */
export function textoReinicio(isoUtc: string, ahora: Date = new Date()): string {
  const destino = new Date(isoUtc);
  const hora = destino.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
  const otroDia = destino.toDateString() !== ahora.toDateString();
  const faltan = (destino.getTime() - ahora.getTime()) / 1000;
  const cuando = `${otroDia ? 'mañana ' : ''}a las ${hora}`;
  return faltan > 0 ? `${cuando} (en ${duracionCorta(faltan)})` : cuando;
}

/** Detecta el modificador de atajo según la plataforma: '⌘K' en macOS y 'Ctrl K' en Windows/Linux. */
export function atajoModificador(letra: string = 'K'): string {
  if (typeof navigator !== 'undefined') {
    const esMac = /(Mac|iPhone|iPod|iPad)/i.test(navigator.platform || navigator.userAgent || '');
    return esMac ? `⌘${letra}` : `Ctrl ${letra}`;
  }
  return `Ctrl ${letra}`;
}

/** Trunca el nombre de archivo dejando visible la extensión y el prefijo: "catalogo_p...csv" */
export function truncarNombreArchivo(nombre: string, maxLen: number = 20): string {
  if (!nombre || nombre.length <= maxLen) return nombre;
  const p = nombre.lastIndexOf('.');
  if (p > 0 && p > nombre.length - 7) {
    const ext = nombre.slice(p);
    const base = nombre.slice(0, p);
    const charsParaBase = maxLen - ext.length - 3;
    if (charsParaBase >= 3) {
      return `${base.slice(0, charsParaBase)}...${ext}`;
    }
  }
  return `${nombre.slice(0, maxLen - 3)}...`;
}

/** Corrige notación tipográfica de unidades industriales estándar: kg/cm², m³ y m². */
export function normalizarUnidadesTipograficas(texto: string): string {
  if (!texto) return '';
  return texto
    .replace(/\bkg\/cm2\b/gi, 'kg/cm²')
    .replace(/\bm3\b/gi, 'm³')
    .replace(/\bm2\b/gi, 'm²');
}
