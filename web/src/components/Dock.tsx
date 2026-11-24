import { CifraAnimada } from './CifraAnimada';
import { Icono } from './Iconos';
import type { EstadoCotizacion } from '../data/tipos';

/**
 * Dock de aprobación: el total y la acción principal siempre a la vista mientras se revisa.
 * «Aprobar» solo abre el diálogo de confirmación; el servidor exige la aprobación registrada antes de dar el PDF
 * (regla 3) y solo un Responsable comercial o un Administrador puede aprobar.
 */
export function DockAprobacion({
  estado,
  escenario,
  total,
  puedeAprobar,
  onEnviar,
  onAprobar,
  onRechazar,
  onDescargar,
}: {
  estado: EstadoCotizacion;
  escenario: string;
  total: number;
  puedeAprobar: boolean;
  onEnviar: () => void;
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
        {revisable && !puedeAprobar && (
          <span className="texto-suave dock__aviso">Solo un Responsable comercial o un Administrador puede aprobar.</span>
        )}
        {revisable && estado === 'Borrador' && (
          <button className="boton" onClick={onEnviar}>
            Enviar a revisión
          </button>
        )}
        {revisable && puedeAprobar && (
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
