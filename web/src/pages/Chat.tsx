import { Fragment, useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react';
import { TarjetaCotizacion } from '../components/Cotizacion';
import { Icono } from '../components/Iconos';
import { MedidorUso } from '../components/MedidorUso';
import { obtenerConfigChat, obtenerUsoChat, type ConfigChat, type UsoChat } from '../lib/api';
import { fechaCorta } from '../lib/conversaciones';
import { tamanoLegible, tramosConNegrita } from '../lib/texto';
import { useAlmacen } from '../state/Almacen';
import { MAX_ARCHIVOS, useChat } from '../state/Conversaciones';

const SUGERENCIAS = [
  'Cotiza 20 gabinetes NEMA 4X 40x30x20 con instalación y flete a Mérida',
  'Necesito 15 tramos de tubo conduit pared delgada 3/4 y 30 coples de 3/4. Instalación incluida, entrega en Umán',
  '5 interruptores termomagnéticos 1P 20A y 2 centros de carga 4 polos bifásico',
];

const ACEPTA = '.txt,.md,.json,.log,.xml,.yaml,.yml,.csv,.tsv,.xlsx,.xlsm,.pdf,.png,.jpg,.jpeg,.webp,.gif';

/** Texto del modelo: respeta saltos de línea e interpreta solo la **negrita**. */
function TextoModelo({ texto }: { texto: string }) {
  return (
    <p className="mensaje__texto">
      {tramosConNegrita(texto).map((t, i) => (t.negrita ? <strong key={i}>{t.texto}</strong> : <Fragment key={i}>{t.texto}</Fragment>))}
    </p>
  );
}

export default function Chat() {
  const { usuario, cotizaciones } = useAlmacen();
  const {
    conversaciones, activa, mensajes, enviando, enviandoAqui, terminadas, guardado,
    texto, setTexto, archivos, agregarArchivos, quitarArchivo, enviar, cancelar, nueva, abrir, borrar,
  } = useChat();
  const [arrastrando, setArrastrando] = useState(false);
  const [historialAbierto, setHistorialAbierto] = useState(false);
  const [config, setConfig] = useState<ConfigChat | null>(null);
  const [errorConfig, setErrorConfig] = useState<string | null>(null);
  const [uso, setUso] = useState<UsoChat | null>(null);
  const [errorUso, setErrorUso] = useState<string | null>(null);
  const refrescoTardio = useRef<number | undefined>(undefined);
  const finRef = useRef<HTMLDivElement>(null);
  const selector = useRef<HTMLInputElement>(null);
  const areaTexto = useRef<HTMLTextAreaElement>(null);
  const envoltorioHistorial = useRef<HTMLDivElement>(null);

  const refrescarUso = useCallback(() => {
    obtenerUsoChat()
      .then((u) => {
        setUso(u);
        setErrorUso(null);
      })
      .catch((e: Error) => setErrorUso(e.message));
  }, []);

  useEffect(() => {
    obtenerConfigChat().then(setConfig).catch((e: Error) => setErrorConfig(e.message));
    refrescarUso();
    const cada = window.setInterval(refrescarUso, 60_000); // mantiene al día la cuenta regresiva del reinicio
    return () => {
      window.clearInterval(cada);
      window.clearTimeout(refrescoTardio.current);
    };
  }, [refrescarUso]);

  // Cada mensaje (incluso uno que falló con 429) cambia lo que queda de la cuota. OpenRouter refleja el contador diario con
  // ~30 s de retraso [Certeza: medido el 23/11/2026]: se vuelve a leer.
  useEffect(() => {
    if (terminadas === 0) return;
    refrescarUso();
    window.clearTimeout(refrescoTardio.current);
    refrescoTardio.current = window.setTimeout(refrescarUso, 35_000);
  }, [terminadas, refrescarUso]);

  useEffect(() => {
    finRef.current?.scrollIntoView({ block: 'end' });
  }, [mensajes, enviandoAqui, activa?.id]);
  // La caja de texto crece con lo que se escribe (hasta un máximo en CSS) y vuelve a una línea al enviar.
  useEffect(() => {
    const el = areaTexto.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [texto]);

  // El historial se cierra al pulsar fuera o con Escape.
  useEffect(() => {
    if (!historialAbierto) return;
    const fuera = (e: MouseEvent) => {
      if (envoltorioHistorial.current && !envoltorioHistorial.current.contains(e.target as Node)) setHistorialAbierto(false);
    };
    const escape = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setHistorialAbierto(false);
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', fuera);
      document.removeEventListener('keydown', escape);
    };
  }, [historialAbierto]);

  const alElegir = (e: ChangeEvent<HTMLInputElement>) => {
    agregarArchivos(Array.from(e.target.files ?? []));
    e.target.value = ''; // permite volver a elegir el mismo archivo
  };

  const alSoltar = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    agregarArchivos(Array.from(e.dataTransfer.files));
  };

  const alTeclear = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void enviar();
    }
  };

  const borrarConversacion = (id: string, titulo: string) => {
    if (window.confirm(`¿Borrar la conversación «${titulo}» del historial? Las cotizaciones que creó no se borran.`)) borrar(id);
  };

  const puedeEnviar = (texto.trim() !== '' || archivos.length > 0) && !enviando;

  return (
    <div
      className={`chat${arrastrando ? ' chat--arrastrando' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        setArrastrando(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setArrastrando(false);
      }}
      onDrop={alSoltar}
    >
      <div className="chat__barra">
        <strong className="chat__titulo" title={activa?.titulo}>{activa ? activa.titulo : 'Nueva conversación'}</strong>
        <div className="chat__acciones">
          <MedidorUso uso={uso} error={errorUso} modeloVision={config?.modelo_vision} />
          <div className="chat__historial-envoltorio" ref={envoltorioHistorial}>
            <button
              className="boton"
              aria-expanded={historialAbierto}
              aria-controls="historial-chat"
              onClick={() => setHistorialAbierto((a) => !a)}
            >
              <Icono nombre="reloj" tamano={16} /> Historial{conversaciones.length > 0 ? ` (${conversaciones.length})` : ''}
            </button>
            {historialAbierto && (
              <div className="chat__historial" id="historial-chat" role="region" aria-label={`Historial de conversaciones de ${usuario.nombre}`}>
                <p className="selector-usuario__titulo">Conversaciones de {usuario.nombre}</p>
                {conversaciones.length === 0 ? (
                  <p className="texto-suave chat__historial-vacio">Aún no hay conversaciones guardadas. Se guardan solas al enviar el primer mensaje.</p>
                ) : (
                  <ul>
                    {conversaciones.map((c) => (
                      <li key={c.id} className={c.id === activa?.id ? 'chat__historial-fila chat__historial-fila--activa' : 'chat__historial-fila'}>
                        <button
                          className="chat__historial-item"
                          aria-current={c.id === activa?.id ? 'true' : undefined}
                          onClick={() => {
                            abrir(c.id);
                            setHistorialAbierto(false);
                          }}
                        >
                          <span className="chat__historial-titulo">{c.titulo}</span>
                          <span className="texto-suave">{fechaCorta(c.actualizada)} · {c.mensajes.length} mensajes</span>
                        </button>
                        <button className="boton-icono" aria-label={`Borrar la conversación ${c.titulo}`} onClick={() => borrarConversacion(c.id, c.titulo)}>
                          <Icono nombre="borrar" tamano={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="selector-usuario__nota texto-suave">
                  {guardado
                    ? 'Se guardan en este navegador (solo textos y nombres de archivo), una lista por usuario.'
                    : 'Este navegador no dejó guardar el historial (espacio lleno o modo privado): se perderá al cerrar la pestaña.'}
                </p>
              </div>
            )}
          </div>
          <button className="boton" onClick={nueva}>
            <Icono nombre="mas" tamano={16} /> Nueva
          </button>
        </div>
      </div>

      <div className="chat__mensajes" role="log" aria-live="polite" aria-label="Conversación">
        <div className="chat__columna">
          {mensajes.length === 0 && (
            <div className="chat__vacio">
              <h1>¿Qué cotización necesitas?</h1>
              <p className="texto-suave">
                Descríbela con tus palabras, o adjunta la solicitud del cliente (PDF, Excel, CSV o texto de chat) con el clip o arrastrándola aquí: la leo y calculo los tres escenarios con tus fuentes.
              </p>
              <div className="sugerencias">
                {SUGERENCIAS.map((s) => (
                  <button key={s} className="sugerencia" onClick={() => void enviar(s)} disabled={enviando}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {mensajes.map((m) => (
            <div key={m.id} className={`mensaje mensaje--${m.rol}${m.error ? ' mensaje--error' : ''}`}>
              <span className="avatar" aria-hidden="true">{m.rol === 'usuario' ? usuario.nombre.split(' ').map((p) => p[0]).join('') : 'T'}</span>
              <div className="mensaje__cuerpo">
                <span className="mensaje__autor">{m.rol === 'usuario' ? 'Tú' : 'Tessera'}</span>
                {m.rol === 'tessera' && !m.error ? <TextoModelo texto={m.texto} /> : <p className="mensaje__texto">{m.texto}</p>}
                {m.archivos && m.archivos.length > 0 && (
                  <div className="chat__adjuntos">
                    {m.archivos.map((n) => (
                      <span key={n} className="etiqueta"><Icono nombre="archivo" tamano={12} /> {n}</span>
                    ))}
                  </div>
                )}
                {m.avisos?.map((a) => (
                  <p key={a} className="chat__aviso"><Icono nombre="alerta" tamano={14} /> {a}</p>
                ))}
                {m.cotizacionId && (() => {
                  const cot = cotizaciones.find((c) => c.id === m.cotizacionId);
                  return cot ? <TarjetaCotizacion cotizacion={cot} /> : null;
                })()}
                {m.meta && <span className="chat__meta">{m.meta}</span>}
              </div>
            </div>
          ))}

          {enviandoAqui && (
            <div className="herramientas" role="status">
              <span className="girando" aria-hidden="true" />
              <span>Leyendo tu solicitud, buscando precios y calculando…</span>
              <button className="boton boton--chico" onClick={cancelar}>Cancelar</button>
            </div>
          )}
          <div ref={finRef} />
        </div>
      </div>

      {archivos.length > 0 && (
        <div className="chat__pendientes" aria-label="Archivos adjuntos">
          {archivos.map((a) => (
            <span key={a.name + a.size} className="etiqueta">
              <Icono nombre="archivo" tamano={12} /> {a.name} · {tamanoLegible(a.size)}
              <button type="button" className="chat__quitar" aria-label={`Quitar ${a.name}`} onClick={() => quitarArchivo(a)}>
                <Icono nombre="cerrar" tamano={12} />
              </button>
            </span>
          ))}
          <span className="texto-suave chat__pista">Si traen materiales con cantidades, se cotizan solos; si no, los lee el modelo. Se quitan al crear la cotización.</span>
        </div>
      )}

      <form className="chat__entrada" onSubmit={(e) => { e.preventDefault(); void enviar(); }}>
        <label className="solo-lectores" htmlFor="solicitud">Solicitud de cotización</label>
        <input ref={selector} type="file" multiple accept={ACEPTA} onChange={alElegir} hidden />
        <button
          type="button"
          className="boton-icono"
          onClick={() => selector.current?.click()}
          disabled={archivos.length >= MAX_ARCHIVOS}
          aria-label="Adjuntar archivos"
          title={`Adjuntar archivos (hasta ${MAX_ARCHIVOS}): txt, csv, xlsx, pdf o imágenes`}
        >
          <Icono nombre="clip" tamano={20} />
        </button>
        <textarea
          id="solicitud"
          ref={areaTexto}
          rows={1}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={alTeclear}
          placeholder={archivos.length > 0 ? 'Opcional: añade una indicación o pulsa Enviar para cotizar los archivos…' : 'Escribe tu solicitud…'}
        />
        <button className="boton boton--primario chat__enviar" type="submit" disabled={!puedeEnviar}>
          <Icono nombre="enviar" tamano={16} /> Enviar
        </button>
      </form>
      <p className="texto-suave chat__nota">
        {errorConfig
          ? errorConfig
          : config
            ? `Conversación: ${config.proveedor} · ${config.modelo}. `
            : 'Conectando con la API… '}
        Enter envía, Mayús+Enter salta de línea. Las cotizaciones usan tus fuentes y las calcula código; las respuestas de conversación del modelo no son fuente de precios.
      </p>
    </div>
  );
}
