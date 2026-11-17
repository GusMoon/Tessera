import { useAlmacen } from '../state/Almacen';
import { Icono } from './Iconos';

export function Toasts() {
  const { toasts, cerrarToast } = useAlmacen();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast--${t.tipo}`}>
          <Icono nombre={t.tipo === 'error' ? 'error' : t.tipo === 'ok' ? 'check' : 'alerta'} tamano={16} />
          <span>{t.texto}</span>
          <button className="boton-icono" aria-label="Cerrar aviso" onClick={() => cerrarToast(t.id)}>
            <Icono nombre="cerrar" tamano={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
