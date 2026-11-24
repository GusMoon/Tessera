import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAlmacen } from '../state/Almacen';

export type EstadoPantalla = 'cargando' | 'error' | 'vacio' | 'listo';

/**
 * Estado real de una pantalla que depende de la API: cargando mientras llega la información y error si falló
 * (con el mensaje del servidor). Se puede previsualizar con `?estado=cargando|error|vacio` para revisar el diseño (doc UI §7).
 */
export function useEstadoPantalla() {
  const { cargando, errorCarga, recargar } = useAlmacen();
  const [params, setParams] = useSearchParams();
  const forzado = params.get('estado');

  const reintentar = useCallback(() => {
    if (params.has('estado')) {
      const nuevo = new URLSearchParams(params);
      nuevo.delete('estado');
      setParams(nuevo, { replace: true });
    }
    recargar();
  }, [params, setParams, recargar]);

  let estado: EstadoPantalla = 'listo';
  if (forzado === 'cargando' || cargando) estado = 'cargando';
  else if (forzado === 'error' || errorCarga) estado = 'error';
  else if (forzado === 'vacio') estado = 'vacio';

  return { estado, reintentar, error: errorCarga };
}
