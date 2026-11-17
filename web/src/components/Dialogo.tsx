import { useEffect, useRef, type ReactNode } from 'react';

interface Props {
  abierto: boolean;
  titulo: string;
  children: ReactNode;
  textoConfirmar: string;
  textoCancelar?: string;
  peligro?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}

/** Diálogo de confirmación sobre <dialog> nativo: atrapa el foco y cierra con Esc. Siempre dice qué pasará. */
export function DialogoConfirmacion({
  abierto,
  titulo,
  children,
  textoConfirmar,
  textoCancelar = 'Cancelar',
  peligro,
  onConfirmar,
  onCancelar,
}: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  return (
    <dialog ref={ref} className="dialogo" aria-labelledby="dialogo-titulo" onCancel={(e) => { e.preventDefault(); onCancelar(); }}>
      {abierto && (
        <div className="dialogo__cuerpo">
          <h2 id="dialogo-titulo">{titulo}</h2>
          <div className="dialogo__contenido">{children}</div>
          <div className="dialogo__acciones">
            <button className="boton" onClick={onCancelar} autoFocus={peligro}>
              {textoCancelar}
            </button>
            <button className={`boton ${peligro ? 'boton--peligro' : 'boton--primario'}`} onClick={onConfirmar} autoFocus={!peligro}>
              {textoConfirmar}
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}
