import { useState } from 'react';
import { DialogoConfirmacion } from '../components/Dialogo';
import { ContenidoConEstados, EncabezadoPagina, EstadoVacio } from '../components/Estados';
import { Icono } from '../components/Iconos';
import { InsigniaEstado } from '../components/Insignia';
import { useAlmacen } from '../state/Almacen';
import type { HechoMemoria } from '../data/tipos';
import { ChipFecha } from '../components/Traza';
import { useEstadoPantalla } from '../lib/useEstadoPantalla';

export default function Memoria() {
  const { memoria, editarHecho, alternarPausa, confirmarHecho, borrarHecho, avisar, puedeAprobar } = useAlmacen();
  const { estado, reintentar, error } = useEstadoPantalla();
  const [editando, setEditando] = useState<string | null>(null);
  const [borrador, setBorrador] = useState('');
  const [porBorrar, setPorBorrar] = useState<HechoMemoria | null>(null);
  const puedeGestionar = puedeAprobar; // el servidor también lo exige: solo quien aprueba edita, pausa, confirma y borra

  const guardar = (id: string) => {
    if (borrador.trim()) {
      void editarHecho(id, borrador.trim()).then(() => avisar('Hecho actualizado. Vuelve a quedar «Por confirmar».', 'info'));
    }
    setEditando(null);
  };

  return (
    <div className="pagina">
      <EncabezadoPagina
        titulo="Memoria"
        descripcion="Lo que el sistema recuerda. Cada hecho tiene origen y fecha; puedes corregirlo, pausarlo o borrarlo."
      />
      <ContenidoConEstados
        estado={estado}
        reintentar={reintentar}
        mensajeError={error}
        vacio={{ titulo: 'Aún no hay hechos guardados', texto: 'Cuando apruebes o edites una cotización, podrás guardar el ajuste como aprendizaje.' }}
      >
        {memoria.length === 0 ? (
          <EstadoVacio titulo="No hay hechos guardados" texto="Borraste todo lo que el sistema recordaba. Se irá llenando con tus aprobaciones y ediciones." />
        ) : (
          <>
            <p className="aviso-parcial" role="note">
              <Icono nombre="alerta" tamano={16} />
              <span>Los hechos nuevos quedan «Por confirmar» y el agente no los usa hasta que una persona autorizada los acepte. Así una cotización mal hecha no contamina las siguientes.</span>
            </p>
            <ol className="linea-tiempo hechos-tiempo" aria-label="Hechos recordados, del más reciente al más antiguo">
              {[...memoria].sort((x, y) => (x.fecha < y.fecha ? 1 : x.fecha > y.fecha ? -1 : 0)).map((h) => (
                <li key={h.id} className="linea-tiempo__item">
                  <span className="linea-tiempo__fecha"><ChipFecha fecha={h.fecha} /></span>
                  <div className={`hecho ${h.estado === 'Pausada' ? 'hecho--pausado' : ''}`}>
                  <div className="hecho__texto">
                    {editando === h.id ? (
                      <>
                        <label className="solo-lectores" htmlFor={`hecho-${h.id}`}>Texto del hecho</label>
                        <textarea id={`hecho-${h.id}`} className="entrada entrada--area" rows={2} value={borrador} onChange={(e) => setBorrador(e.target.value)} autoFocus />
                      </>
                    ) : (
                      <p>{h.texto}</p>
                    )}
                    <p className="texto-suave">Origen: {h.origen}</p>
                  </div>
                  <div className="hecho__estado">
                    <InsigniaEstado estado={h.estado} />
                    {h.porConfirmar && <InsigniaEstado estado="Por confirmar" />}
                  </div>
                  <div className="acciones">
                    {editando === h.id ? (
                      <>
                        <button className="boton boton--chico boton--primario" onClick={() => guardar(h.id)}>Guardar</button>
                        <button className="boton boton--chico" onClick={() => setEditando(null)}>Cancelar</button>
                      </>
                    ) : (
                      <>
                        {!puedeGestionar && <span className="texto-suave">Solo quien aprueba puede gestionarla</span>}
                        {puedeGestionar && h.porConfirmar && (
                          <button className="boton boton--chico boton--primario" onClick={() => { void confirmarHecho(h.id); avisar('Hecho confirmado.'); }}>Confirmar</button>
                        )}
                        {puedeGestionar && (
                          <>
                            <button className="boton boton--chico" onClick={() => { setEditando(h.id); setBorrador(h.texto); }}>Editar</button>
                            <button className="boton boton--chico" onClick={() => void alternarPausa(h.id)}>{h.estado === 'Activa' ? 'Pausar' : 'Reanudar'}</button>
                            <button className="boton boton--chico boton--peligro-suave" onClick={() => setPorBorrar(h)}>Borrar</button>
                          </>
                        )}
                      </>
                    )}
                  </div>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </ContenidoConEstados>

      <DialogoConfirmacion
        abierto={porBorrar !== null}
        titulo="Borrar este hecho"
        textoConfirmar="Borrar"
        peligro
        onCancelar={() => setPorBorrar(null)}
        onConfirmar={() => {
          if (porBorrar) void borrarHecho(porBorrar.id);
          setPorBorrar(null);
          avisar('Hecho borrado de la memoria.', 'info');
        }}
      >
        <p>«{porBorrar?.texto}»</p>
        <p>El sistema dejará de recordarlo y no podrá usarlo en futuras cotizaciones. Esta acción no se puede deshacer.</p>
      </DialogoConfirmacion>
    </div>
  );
}
