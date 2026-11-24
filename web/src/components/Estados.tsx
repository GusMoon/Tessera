import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Icono } from './Iconos';
import type { EstadoPantalla } from '../lib/useEstadoPantalla';

export function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: string;
  descripcion?: string;
  acciones?: ReactNode;
}) {
  return (
    <header className="encabezado-pagina">
      <div>
        <h1>{titulo}</h1>
        {descripcion && <p className="texto-suave">{descripcion}</p>}
      </div>
      {acciones && <div className="acciones">{acciones}</div>}
    </header>
  );
}

export function EstadoVacio({
  titulo,
  texto,
  accion,
}: {
  titulo: string;
  texto: string;
  accion?: { etiqueta: string; a?: string; onClick?: () => void };
}) {
  return (
    <div className="estado estado--vacio" role="status">
      <Icono nombre="archivo" tamano={28} />
      <h2>{titulo}</h2>
      <p>{texto}</p>
      {accion?.a && (
        <Link className="boton boton--primario" to={accion.a}>
          {accion.etiqueta}
        </Link>
      )}
      {accion?.onClick && (
        <button className="boton boton--primario" onClick={accion.onClick}>
          {accion.etiqueta}
        </button>
      )}
    </div>
  );
}

export function EstadoError({ texto, onReintentar }: { texto: string; onReintentar: () => void }) {
  return (
    <div className="estado estado--error" role="alert">
      <Icono nombre="error" tamano={28} />
      <h2>No se pudo cargar</h2>
      <p>{texto}</p>
      <button className="boton" onClick={onReintentar}>
        <Icono nombre="reintentar" tamano={16} />
        Reintentar
      </button>
    </div>
  );
}

/** Esqueleto que imita una tabla, en lugar de una rueda girando sola (doc UI §7). */
export function EsqueletoTabla({ filas = 6 }: { filas?: number }) {
  return (
    <div className="esqueleto" aria-busy="true" aria-label="Cargando contenido">
      <div className="esqueleto__fila esqueleto__fila--encabezado" />
      {Array.from({ length: filas }, (_, i) => (
        <div key={i} className="esqueleto__fila" />
      ))}
    </div>
  );
}

/** Envuelve el contenido de una pantalla con los estados cargando, error y vacío. */
export function ContenidoConEstados({
  estado,
  reintentar,
  mensajeError,
  vacio,
  children,
}: {
  estado: EstadoPantalla;
  reintentar: () => void;
  /** Mensaje del servidor cuando la carga falló. */
  mensajeError?: string | null;
  vacio: { titulo: string; texto: string; accion?: { etiqueta: string; a?: string } };
  children: ReactNode;
}) {
  if (estado === 'cargando') return <EsqueletoTabla />;
  if (estado === 'error')
    return <EstadoError texto={mensajeError || 'Falló la conexión con el servidor. Intenta de nuevo.'} onReintentar={reintentar} />;
  if (estado === 'vacio') return <EstadoVacio {...vacio} />;
  return <>{children}</>;
}
