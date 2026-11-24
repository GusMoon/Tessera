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
