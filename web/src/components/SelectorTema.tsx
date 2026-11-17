import { useRef, type KeyboardEvent } from 'react';
import { Icono, type NombreIcono } from './Iconos';
import { useTema, type Tema } from '../lib/tema';

const OPCIONES: { id: Tema; etiqueta: string; icono: NombreIcono }[] = [
  { id: 'claro', etiqueta: 'Claro', icono: 'sol' },
  { id: 'sistema', etiqueta: 'Sistema', icono: 'monitor' },
  { id: 'oscuro', etiqueta: 'Oscuro', icono: 'luna' },
];

/** Selector de tema de tres posiciones. Se maneja con flechas, como cualquier grupo de opciones. */
export function SelectorTema() {
  const [tema, fijarTema] = useTema();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const alTeclear = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const sig = (i + d + OPCIONES.length) % OPCIONES.length;
    fijarTema(OPCIONES[sig].id);
    refs.current[sig]?.focus();
  };

  return (
    <div className="selector-tema" role="radiogroup" aria-label="Tema de color">
      {OPCIONES.map((o, i) => (
        <button
          key={o.id}
          ref={(el) => { refs.current[i] = el; }}
          role="radio"
          aria-checked={tema === o.id}
          aria-label={`Tema ${o.etiqueta.toLowerCase()}`}
          title={`Tema ${o.etiqueta.toLowerCase()}`}
          tabIndex={tema === o.id ? 0 : -1}
          className={`selector-tema__op ${tema === o.id ? 'activa' : ''}`}
          onClick={() => fijarTema(o.id)}
          onKeyDown={(e) => alTeclear(e, i)}
        >
          <Icono nombre={o.icono} tamano={16} />
        </button>
      ))}
    </div>
  );
}
