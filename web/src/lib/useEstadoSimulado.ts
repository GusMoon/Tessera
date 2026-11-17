import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

export type EstadoPantalla = 'cargando' | 'error' | 'vacio' | 'listo';

/**
 * Simula la carga inicial de una pantalla y permite previsualizar estados con
 * `?estado=cargando|error|vacio` (útil para revisar el diseño; doc UI §7).
 */
export function useEstadoSimulado(ms = 450) {
  const [params, setParams] = useSearchParams();
  const forzado = params.get('estado');
  const [cargando, setCargando] = useState(true);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    setCargando(true);
    const t = window.setTimeout(() => setCargando(false), ms);
    return () => window.clearTimeout(t);
  }, [intento, ms]);

  const reintentar = useCallback(() => {
    if (params.has('estado')) {
      const nuevo = new URLSearchParams(params);
      nuevo.delete('estado');
      setParams(nuevo, { replace: true });
    }
    setIntento((n) => n + 1);
  }, [params, setParams]);

  let estado: EstadoPantalla = 'listo';
  if (forzado === 'cargando' || cargando) estado = 'cargando';
  else if (forzado === 'error') estado = 'error';
  else if (forzado === 'vacio') estado = 'vacio';

  return { estado, reintentar };
}
