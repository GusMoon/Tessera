import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { Icono } from './Iconos';

interface EstadoPanel {
  titulo: string;
  contenido: ReactNode;
  ruta: string;
}

interface ApiPanel {
  panel: EstadoPanel | null;
  abrir: (titulo: string, contenido: ReactNode) => void;
  cerrar: () => void;
}

const Contexto = createContext<ApiPanel | null>(null);

/** Panel lateral derecho de 360 px: lo abre cada pantalla y se descarta al cambiar de ruta. */
export function ProveedorPanel({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const rutaActual = useRef(pathname);
  rutaActual.current = pathname;
  const [panel, setPanel] = useState<EstadoPanel | null>(null);

  useEffect(() => {
    setPanel((p) => (p && p.ruta !== pathname ? null : p));
  }, [pathname]);

  const abrir = useCallback(
    (titulo: string, contenido: ReactNode) => setPanel({ titulo, contenido, ruta: rutaActual.current }),
    [],
  );
  const cerrar = useCallback(() => setPanel(null), []);
  const valor = useMemo(() => ({ panel, abrir, cerrar }), [panel, abrir, cerrar]);

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function usePanel(): ApiPanel {
  const v = useContext(Contexto);
  if (!v) throw new Error('usePanel debe usarse dentro de ProveedorPanel');
  return v;
}

export function PanelDerecho() {
  const { panel, cerrar } = usePanel();
  const { pathname } = useLocation();

  useEffect(() => {
    if (!panel) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector('dialog[open]')) cerrar();
    };
    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, [panel, cerrar]);

  if (!panel || panel.ruta !== pathname) return null;
  return (
    <aside className="panel" aria-label={panel.titulo}>
      <div className="panel__cabecera">
        <h2>{panel.titulo}</h2>
        <button className="boton-icono" onClick={cerrar} aria-label="Cerrar panel">
          <Icono nombre="cerrar" />
        </button>
      </div>
      <div className="panel__cuerpo">{panel.contenido}</div>
    </aside>
  );
}
