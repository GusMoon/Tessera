import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Icono } from './Iconos';
import { SelectorTema } from './SelectorTema';
import { useAlmacen } from '../state/Almacen';

const iniciales = (nombre: string) => nombre.split(' ').map((p) => p[0]).join('').slice(0, 2);

// Elegir un usuario NO es iniciar sesión: solo prueba los permisos de cada rol (ver docs/permisos.md).
export function SelectorUsuario() {
  const { usuario, usuarios, cambiarUsuario } = useAlmacen();
  const [abierto, setAbierto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const idMenu = useId();

  useEffect(() => {
    if (!abierto) return;
    const alPulsarFuera = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener('mousedown', alPulsarFuera);
    // al abrir, el foco pasa a la opción activa para poder moverse con el teclado
    raiz.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
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
    if (!abierto || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
    e.preventDefault();
    const opciones = Array.from(raiz.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]') ?? []);
    const i = opciones.indexOf(document.activeElement as HTMLButtonElement);
    const siguiente = e.key === 'ArrowDown' ? (i + 1) % opciones.length : (i - 1 + opciones.length) % opciones.length;
    opciones[siguiente]?.focus();
  };

  const elegir = (id: string) => {
    if (id !== usuario.id) cambiarUsuario(id);
    cerrar();
  };

  return (
    <div className="selector-usuario" ref={raiz} onKeyDown={alTeclear}>
      <button
        ref={boton}
        type="button"
        className="selector-usuario__boton"
        aria-haspopup="menu"
        aria-expanded={abierto}
        aria-controls={abierto ? idMenu : undefined}
        title="Prototipo: elegir un usuario no es iniciar sesión; solo prueba los permisos de cada rol"
        onClick={() => setAbierto((a) => !a)}
      >
        <span className="avatar" aria-hidden="true">{iniciales(usuario.nombre)}</span>
        <span className="selector-usuario__texto">
          <span className="selector-usuario__nombre">{usuario.nombre}</span>
          <span className="texto-suave">{usuario.rol}</span>
        </span>
        <span className={`selector-usuario__flecha${abierto ? ' selector-usuario__flecha--abierta' : ''}`} aria-hidden="true">
          <Icono nombre="abajo" tamano={16} />
        </span>
      </button>

      {abierto && (
        <div className="selector-usuario__menu" id={idMenu} role="menu" aria-label="Menú de usuario y preferencias">
          <p className="selector-usuario__titulo">Probar la app como…</p>
          {usuarios.map((u) => {
            const activo = u.id === usuario.id;
            return (
              <button
                key={u.id}
                type="button"
                role="menuitemradio"
                aria-checked={activo}
                className={`selector-usuario__opcion${activo ? ' selector-usuario__opcion--activa' : ''}`}
                onClick={() => elegir(u.id)}
              >
                <span className="avatar" aria-hidden="true">{iniciales(u.nombre)}</span>
                <span className="selector-usuario__texto">
                  <span className="selector-usuario__nombre">{u.nombre}</span>
                  <span className="texto-suave">{u.rol}</span>
                </span>
                {activo && <span className="selector-usuario__marca" aria-hidden="true"><Icono nombre="check" tamano={16} /></span>}
              </button>
            );
          })}
          
          <div className="selector-usuario__seccion-tema">
            <span className="selector-usuario__titulo">Tema de apariencia</span>
            <SelectorTema />
          </div>

          <p className="selector-usuario__nota texto-suave">No es iniciar sesión: cada rol tiene permisos distintos.</p>
        </div>
      )}
    </div>
  );
}
