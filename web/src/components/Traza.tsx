import { Icono } from './Iconos';
import {
  formatoFecha,
  mesesDeAntiguedad,
  textoMeses,
  textoRelativo,
  UMBRAL_ANTIGUEDAD_MESES,
} from '../lib/dinero';

/** Escala de la traza: 18 meses de punta a punta; la marca vertical cae en el umbral de 6. */
const ESCALA_MESES = 18;

/**
 * Traza de antigüedad: de qué fecha viene el dato. El tramo se pinta en ocre al pasar el umbral,
 * pero el texto con los meses siempre está, así el estado nunca depende solo del color.
 */
export function TrazaAntiguedad({
  fecha,
  compacta,
  retraso = 0,
  anima,
}: {
  fecha: string;
  compacta?: boolean;
  retraso?: number;
  anima?: boolean;
}) {
  const meses = mesesDeAntiguedad(fecha);
  const antigua = meses > UMBRAL_ANTIGUEDAD_MESES;
  const ancho = Math.max(4, Math.min(100, (meses / ESCALA_MESES) * 100));
  const umbral = (UMBRAL_ANTIGUEDAD_MESES / ESCALA_MESES) * 100;
  const descripcion = `Dato de hace ${textoMeses(meses)}${antigua ? `, supera el umbral de ${UMBRAL_ANTIGUEDAD_MESES} meses` : ''}`;

  return (
    <span className={`traza ${antigua ? 'traza--antigua' : ''} ${compacta ? 'traza--compacta' : ''}`} title={descripcion}>
      <span className="traza__pista" role="img" aria-label={descripcion}>
        <span
          className={`traza__relleno ${anima ? 'traza__relleno--anima' : ''}`}
          style={{ width: `${ancho}%`, animationDelay: `${retraso}ms` }}
        />
        <span className="traza__umbral" style={{ left: `${umbral}%` }} />
      </span>
      <span className="traza__texto" aria-hidden="true">
        {antigua && <Icono nombre="alerta" tamano={13} />}
        {compacta ? `${meses} m` : textoMeses(meses)}
      </span>
    </span>
  );
}

/** Fecha dd/mm/aaaa con su lectura relativa («hace 2 días»). */
export function ChipFecha({ fecha, soloRelativa }: { fecha: string; soloRelativa?: boolean }) {
  return (
    <span className="chip-fecha">
      {!soloRelativa && <span className="cifra">{formatoFecha(fecha)}</span>}
      <span className="chip-fecha__rel">{textoRelativo(fecha)}</span>
    </span>
  );
}

/** Meses del dato más viejo entre las partidas de un escenario (para miniaturas). */
export function fechaMasAntigua(fechas: string[]): string | undefined {
  return fechas.length ? [...fechas].sort()[0] : undefined;
}
