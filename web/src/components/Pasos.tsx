import { Icono } from './Iconos';
import type { EstadoCotizacion } from '../data/tipos';

const SECUENCIA = ['Borrador', 'En revisión', 'Aprobada'] as const;

/**
 * Pasos del ciclo de una cotización. Es una secuencia real, por eso lleva números.
 * Si fue rechazada, el último paso se convierte en «Rechazada».
 */
export function PasosEstado({ estado }: { estado: EstadoCotizacion }) {
  const rechazada = estado === 'Rechazada';
  const indice = rechazada ? 1 : SECUENCIA.indexOf(estado as (typeof SECUENCIA)[number]);
  const pasos = rechazada ? ['Borrador', 'En revisión', 'Rechazada'] : [...SECUENCIA];

  return (
    <ol className="pasos" aria-label="Progreso de la cotización">
      {pasos.map((p, i) => {
        const hecho = rechazada ? i < 2 : i < indice;
        const actual = rechazada ? i === 2 : i === indice;
        const fin = rechazada && i === 2;
        return (
          <li
            key={p}
            className={`paso ${hecho ? 'paso--hecho' : ''} ${actual ? 'paso--actual' : ''} ${fin ? 'paso--rechazo' : ''}`}
            aria-current={actual ? 'step' : undefined}
          >
            <span className="paso__marca" aria-hidden="true">
              {hecho ? <Icono nombre="check" tamano={13} /> : fin ? <Icono nombre="cerrar" tamano={13} /> : i + 1}
            </span>
            <span className="paso__texto">{p}</span>
          </li>
        );
      })}
    </ol>
  );
}
