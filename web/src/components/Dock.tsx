import { CifraAnimada } from './CifraAnimada';
import { Icono } from './Iconos';
import type { EstadoCotizacion } from '../data/tipos';

/**
 * Dock de aprobación: el total y la acción principal siempre a la vista mientras se revisa.
 * «Aprobar» solo abre el diálogo de confirmación; nada se genera sin aprobación registrada.
 */
export function DockAprobacion({
  estado,
  escenario,
  total,
  onAprobar,
  onRechazar,
  onDescargar,
}: {
  estado: EstadoCotizacion;
  escenario: string;
  total: number;
  onAprobar: () => void;
  onRechazar: () => void;
  onDescargar: () => void;
}) {
  const revisable = estado === 'Borrador' || estado === 'En revisión';
  return (
    <div className="dock" role="region" aria-label="Total y aprobación">
      <div className="dock__total">
        <span className="dock__etiqueta">Total · {escenario}</span>
        <CifraAnimada centavos={total} className="dock__cifra" />
      </div>
      <div className="dock__acciones">
        {revisable && (
          <>
            <button className="boton boton--fantasma boton--peligro-suave" onClick={onRechazar}>
              Rechazar
            </button>
            <button className="boton boton--pildora boton--primario" onClick={onAprobar}>
              Aprobar y PDF
            </button>
          </>
        )}
        {estado === 'Aprobada' && (
          <button className="boton boton--pildora boton--primario" onClick={onDescargar}>
            <Icono nombre="descargar" tamano={16} /> Descargar PDF
          </button>
        )}
        {estado === 'Rechazada' && <span className="texto-suave">Rechazada: no se generó PDF</span>}
      </div>
    </div>
  );
}
