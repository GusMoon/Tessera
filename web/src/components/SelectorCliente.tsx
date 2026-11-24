import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Icono } from './Iconos';

interface SelectorClienteProps {
  id?: string;
  cliente: string;
  alCambiar: (cliente: string) => void;
  clientes: string[];
  deshabilitado?: boolean;
  haciaArriba?: boolean;
}

export function SelectorCliente({
  id,
  cliente,
  alCambiar,
  clientes,
  deshabilitado = false,
  haciaArriba = false,
}: SelectorClienteProps) {
  const [abierto, setAbierto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const idMenu = useId();

  useEffect(() => {
    if (!abierto) return;
    const alPulsarFuera = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) {
        setAbierto(false);
      }
    };
    document.addEventListener('mousedown', alPulsarFuera);
    return () => document.removeEventListener('mousedown', alPulsarFuera);
  }, [abierto]);

  const cerrar = () => {
    setAbierto(false);
    boton.current?.focus();
  };

  const alTeclear = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' && abierto) {
      e.preventDefault();
      cerrar();
      return;
    }
    if (!abierto) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter') {
        e.preventDefault();
        setAbierto(true);
      }
      return;
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const opciones = Array.from(raiz.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []);
      const i = opciones.indexOf(document.activeElement as HTMLButtonElement);
      const siguiente = e.key === 'ArrowDown' ? (i + 1) % opciones.length : (i - 1 + opciones.length) % opciones.length;
      opciones[siguiente]?.focus();
    }
  };

  const elegir = (val: string) => {
    alCambiar(val);
    cerrar();
  };

  const etiquetaActual = cliente || 'Cliente general (tarifas base)';

  return (
    <div
      ref={raiz}
      className={`selector-cliente ${abierto ? 'selector-cliente--abierto' : ''} ${deshabilitado ? 'selector-cliente--deshabilitado' : ''}`}
      onKeyDown={alTeclear}
    >
      <button
        ref={boton}
        id={id}
        type="button"
        className="selector-cliente__boton"
        aria-haspopup="listbox"
        aria-expanded={abierto}
        aria-controls={abierto ? idMenu : undefined}
        aria-label="Seleccionar cliente para pre-cargar tarifas"
        disabled={deshabilitado}
        onClick={() => setAbierto((a) => !a)}
      >
        <span className="selector-cliente__icono-tipo" aria-hidden="true">
          <Icono nombre="cotizaciones" tamano={14} />
        </span>
        <span className="selector-cliente__etiqueta" title={etiquetaActual}>
          {etiquetaActual}
        </span>
        <span className={`selector-cliente__flecha ${abierto ? 'selector-cliente__flecha--abierta' : ''}`} aria-hidden="true">
          <Icono nombre="abajo" tamano={12} />
        </span>
      </button>

      {abierto && (
        <div
          id={idMenu}
          className={`selector-cliente__menu ${haciaArriba ? 'selector-cliente__menu--arriba' : 'selector-cliente__menu--abajo'}`}
          role="listbox"
          aria-label="Lista de clientes"
        >
          <div className="selector-cliente__cabecera">
            <span>Tarifas por cliente</span>
          </div>
          <div className="selector-cliente__lista">
            <button
              type="button"
              role="option"
              aria-selected={!cliente}
              className={`selector-cliente__opcion ${!cliente ? 'selector-cliente__opcion--activa' : ''}`}
              onClick={() => elegir('')}
            >
              <div className="selector-cliente__opcion-texto">
                <span className="selector-cliente__opcion-nombre">Cliente general</span>
                <span className="selector-cliente__opcion-desc">Tarifas base sin descuento</span>
              </div>
              {!cliente && (
                <span className="selector-cliente__marca" aria-hidden="true">
                  <Icono nombre="check" tamano={15} />
                </span>
              )}
            </button>

            {clientes.map((c) => {
              const activo = c === cliente;
              return (
                <button
                  key={c}
                  type="button"
                  role="option"
                  aria-selected={activo}
                  className={`selector-cliente__opcion ${activo ? 'selector-cliente__opcion--activa' : ''}`}
                  onClick={() => elegir(c)}
                >
                  <div className="selector-cliente__opcion-texto">
                    <span className="selector-cliente__opcion-nombre">{c}</span>
                  </div>
                  {activo && (
                    <span className="selector-cliente__marca" aria-hidden="true">
                      <Icono nombre="check" tamano={15} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
