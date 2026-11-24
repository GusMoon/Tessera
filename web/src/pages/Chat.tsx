import { Fragment, useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Icono, type NombreIcono } from '../components/Iconos';
import { LiveQuoteDrawer } from '../components/LiveQuoteDrawer';
import { QuoteCard } from '../components/QuoteCard';
import { SelectorCliente } from '../components/SelectorCliente';
import { obtenerConfigChat, type ConfigChat } from '../lib/api';
import { tamanoLegible, tramosConNegrita } from '../lib/texto';
import { useAlmacen } from '../state/Almacen';
import { MAX_ARCHIVOS, useChat } from '../state/Conversaciones';

interface SugerenciaCard {
  id: string;
  categoria: string;
  icono: NombreIcono;
  texto: string;
}

const SUGERENCIAS_CARDS: SugerenciaCard[] = [
  {
    id: 'sug-1',
    categoria: 'Cotización nueva',
    icono: 'cotizaciones',
    texto: 'Cotiza 20 gabinetes NEMA 4X 40x30x20 con instalación y flete a Mérida',
  },
  {
    id: 'sug-2',
    categoria: 'Entrega foránea',
    icono: 'fuentes',
    texto: '15 tramos de tubo conduit pared delgada 3/4 y 30 coples con entrega en Umán',
  },
  {
    id: 'sug-3',
    categoria: 'Eléctrico',
    icono: 'check',
    texto: '5 interruptores termomagnéticos 1P 20A y 2 centros de carga 4 polos bifásico',
  },
  {
    id: 'sug-4',
    categoria: 'Reutilizar',
    icono: 'reloj',
    texto: 'Reutiliza la cotización del cliente Grupo Peninsular con flete a Cancún',
  },
];

const CLIENTES_PREDETERMINADOS = [
  'Grupo Inmobiliario Peninsular S.A. de C.V.',
  'Constructora Maya del Sureste',
  'Desarrollos Residenciales del Norte',
  'Instalaciones Industriales Mérida',
  'Comercializadora Eléctrica Peninsular',
];

const ACEPTA = '.txt,.md,.json,.log,.xml,.yaml,.yml,.csv,.tsv,.xlsx,.xlsm,.pdf,.png,.jpg,.jpeg,.webp,.gif';

/** Texto del modelo: respeta saltos de línea e interpreta negrita en tipografía Sans accesible. */
function TextoModelo({ texto }: { texto: string }) {
  return (
    <div className="mensaje__texto">
      {tramosConNegrita(texto).map((t, i) =>
        t.negrita ? <strong key={i}>{t.texto}</strong> : <Fragment key={i}>{t.texto}</Fragment>,
      )}
    </div>
  );
}

export default function Chat() {
  const { usuario, cotizaciones, documentos, cargando: cargandoAlmacen, ajustes } = useAlmacen();
  const {
    activa, mensajes, enviando, enviandoAqui,
    texto, setTexto, archivos, agregarArchivos, quitarArchivo, enviar, cancelar, nueva,
  } = useChat();

  const [searchParams, setSearchParams] = useSearchParams();
  const [arrastrando, setArrastrando] = useState(false);
  const [clienteSeleccionado, setClienteSeleccionado] = useState('');
  const [proyectoSeleccionado, setProyectoSeleccionado] = useState('');

  // Panel derecho colapsado por defecto si no hay cotización activa
  const [panelLiveAbierto, setPanelLiveAbierto] = useState(false);
  const [config, setConfig] = useState<ConfigChat | null>(null);
  const [errorConfig, setErrorConfig] = useState<string | null>(null);

  const finRef = useRef<HTMLDivElement>(null);
  const selector = useRef<HTMLInputElement>(null);
  const areaTexto = useRef<HTMLTextAreaElement>(null);

  // Escuchar evento o URL param para nueva cotización desde el sidebar
  useEffect(() => {
    const alNuevaEvent = () => {
      nueva();
      setClienteSeleccionado('');
      setProyectoSeleccionado('');
      areaTexto.current?.focus();
    };

    window.addEventListener('tessera:nueva-conversacion', alNuevaEvent);

    if (searchParams.get('nueva')) {
      nueva();
      setClienteSeleccionado('');
      setProyectoSeleccionado('');
      setSearchParams({}, { replace: true });
      areaTexto.current?.focus();
    }

    return () => window.removeEventListener('tessera:nueva-conversacion', alNuevaEvent);
  }, [nueva, searchParams, setSearchParams]);

  // Detección de fuentes cargadas en el sistema
  const fuentesListas = useMemo(() => documentos.filter((d) => d.estado === 'Listo'), [documentos]);
  const hayFuentes = fuentesListas.length > 0;

  // Clientes combinados
  const clientesDisponibles = useMemo(() => {
    const set = new Set([...CLIENTES_PREDETERMINADOS, ...cotizaciones.map((c) => c.cliente)]);
    return Array.from(set).filter(Boolean).sort();
  }, [cotizaciones]);

  // Cotización activa en la conversación actual
  const ultimaCotizacionId = useMemo(() => {
    for (let i = mensajes.length - 1; i >= 0; i--) {
      if (mensajes[i].cotizacionId) return mensajes[i].cotizacionId;
    }
    return null;
  }, [mensajes]);

  const cotizacionActiva = useMemo(() => {
    if (ultimaCotizacionId) {
      return cotizaciones.find((c) => c.id === ultimaCotizacionId) ?? null;
    }
    return null;
  }, [ultimaCotizacionId, cotizaciones]);

  // Abrir automáticamente el panel lateral cuando aparezca la primera cotización
  useEffect(() => {
    if (cotizacionActiva) {
      setPanelLiveAbierto(true);
    }
  }, [cotizacionActiva]);

  useEffect(() => {
    obtenerConfigChat().then(setConfig).catch((e: Error) => setErrorConfig(e.message));
  }, []);

  useEffect(() => {
    finRef.current?.scrollIntoView({ block: 'end' });
  }, [mensajes, enviandoAqui, activa?.id]);

  // Altura automática de textarea
  useEffect(() => {
    const el = areaTexto.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [texto]);

  // Atajos globales (Ctrl+K para nueva, Alt+P para panel)
  useEffect(() => {
    const alTeclearGlobal = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        nueva();
        areaTexto.current?.focus();
      } else if (e.altKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        setPanelLiveAbierto((a) => !a);
      }
    };
    window.addEventListener('keydown', alTeclearGlobal);
    return () => window.removeEventListener('keydown', alTeclearGlobal);
  }, [nueva]);

  const alElegir = (e: ChangeEvent<HTMLInputElement>) => {
    agregarArchivos(Array.from(e.target.files ?? []));
    e.target.value = '';
  };

  const alSoltar = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    if (!hayFuentes) return;
    agregarArchivos(Array.from(e.dataTransfer.files));
  };

  const manejarEnvio = () => {
    if (!hayFuentes || enviando) return;
    let prefijoContexto = '';
    if (clienteSeleccionado) {
      prefijoContexto += `[Cliente: ${clienteSeleccionado}] `;
    }
    if (proyectoSeleccionado.trim()) {
      prefijoContexto += `[Proyecto: ${proyectoSeleccionado.trim()}] `;
    }
    const cuerpo = texto.trim();
    if (!cuerpo && archivos.length === 0) return;

    const textoFinal = prefijoContexto ? `${prefijoContexto}${cuerpo}` : cuerpo;
    void enviar(textoFinal);
  };

  const alTeclear = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      manejarEnvio();
    }
  };

  const reintentarUltimoMensaje = () => {
    const ultimoUsuario = [...mensajes].reverse().find((m) => m.rol === 'usuario');
    if (ultimoUsuario) {
      void enviar(ultimoUsuario.texto);
    }
  };

  const usarSugerencia = (sug: string) => {
    setTexto(sug);
    areaTexto.current?.focus();
  };

  const primerNombre = usuario.nombre.split(' ')[0] || 'Laura';
  const puedeEnviar = hayFuentes && !enviando && (texto.trim().length > 0 || archivos.length > 0);
  const esVacio = mensajes.length === 0;

  // COMPOSER UNIFICADO (En centro cuando esVacio, fijo al fondo cuando hay mensajes)
  const renderComposer = (enCentro: boolean) => (
    <div
      className={`chat-composer ${enCentro ? 'chat-composer--centro' : 'chat-composer--fijo'}`}
      role="region"
      aria-label="Formulario de solicitud de cotización"
    >
      {/* Archivos adjuntos pendientes */}
      {archivos.length > 0 && (
        <div className="chat__pendientes" aria-label="Archivos adjuntos para enviar">
          {archivos.map((a, i) => (
            <span key={i} className="chip chip--activo">
              <Icono nombre="archivo" tamano={12} />
              <span>{a.name} ({tamanoLegible(a.size)})</span>
              <button
                type="button"
                className="chat__quitar"
                onClick={() => quitarArchivo(a)}
                aria-label={`Quitar archivo ${a.name}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="chat-composer__tarjeta">
        {/* Barra superior del composer: Selectores de contexto (Cliente y Proyecto) */}
        <div className="chat-composer__chips-barra">
          <SelectorCliente
            id={`cliente-sel-${enCentro ? 'c' : 'f'}`}
            cliente={clienteSeleccionado}
            alCambiar={setClienteSeleccionado}
            clientes={clientesDisponibles}
            deshabilitado={!hayFuentes}
            haciaArriba={!enCentro}
          />

          <div className="chat-composer__chip chat-composer__chip--input">
            <Icono nombre="editar" tamano={13} />
            <input
              type="text"
              className="chat-composer__input-texto"
              placeholder="Proyecto / Obra (opcional)"
              value={proyectoSeleccionado}
              onChange={(e) => setProyectoSeleccionado(e.target.value)}
              disabled={!hayFuentes}
              aria-label="Proyecto u obra asociada"
            />
          </div>
        </div>

        {/* Fila de input con textarea y botones ergonómicos */}
        <div className="chat-composer__fila-input">
          <label className="solo-lectores" htmlFor={`solicitud-${enCentro ? 'c' : 'f'}`}>
            Solicitud de cotización
          </label>
          <input ref={selector} type="file" multiple accept={ACEPTA} onChange={alElegir} hidden />

          <button
            type="button"
            className="boton-icono chat-composer__btn-adjuntar"
            onClick={() => selector.current?.click()}
            disabled={!hayFuentes || archivos.length >= MAX_ARCHIVOS}
            aria-label="Adjuntar archivos"
            title={`Adjuntar archivos (hasta ${MAX_ARCHIVOS}): PDF, Excel, CSV, planos o imágenes`}
          >
            <Icono nombre="clip" tamano={20} />
          </button>

          <textarea
            id={`solicitud-${enCentro ? 'c' : 'f'}`}
            ref={areaTexto}
            rows={1}
            value={texto}
            disabled={!hayFuentes}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={alTeclear}
            placeholder={
              !hayFuentes
                ? 'Carga un catálogo o tarifario en Fuentes para comenzar a cotizar…'
                : archivos.length > 0
                ? 'Instrucciones adicionales para los archivos adjuntos (opcional)…'
                : 'Escribe los materiales y cantidades, ej. 20 gabinetes NEMA 4X con flete'
            }
          />

          <button
            className="boton boton--primario chat-composer__btn-enviar"
            type="button"
            onClick={manejarEnvio}
            disabled={!puedeEnviar}
            title={!hayFuentes ? 'Primero debes cargar fuentes en la sección Fuentes' : 'Enviar solicitud (Enter)'}
          >
            {enviando ? (
              <span className="girando" aria-hidden="true" />
            ) : (
              <>
                <Icono nombre="enviar" tamano={16} />
                <span className="chat-composer__enviar-label">Cotizar</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Pie informativo en una sola línea con tooltip accesible */}
      <footer className="chat-composer__pie-info">
        <span className="chat-composer__info-linea">
          {errorConfig ? (
            <span style={{ color: 'var(--error)' }}>{errorConfig}</span>
          ) : config ? (
            <span>Motor: {config.proveedor} · {config.modelo}</span>
          ) : (
            <span>Conectando con la API…</span>
          )}
          <span className="chat-composer__separador">·</span>
          <span>Enter envía, Mayús+Enter nueva línea</span>
        </span>
        <span
          className="chat-composer__tooltip-trigger"
          title="Cálculo determinista: los precios, márgenes, impuestos y totales se calculan con código determinista y fuentes vigentes; el modelo de lenguaje no altera cifras."
          aria-label="Información sobre cálculo determinista"
        >
          <Icono nombre="info" tamano={15} />
        </span>
      </footer>
    </div>
  );

  return (
    <div className={`chat-layout ${panelLiveAbierto ? 'chat-layout--con-live' : ''}`}>
      {/* Columna central principal del Chat */}
      <div
        className={`chat${arrastrando ? ' chat--arrastrando' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (hayFuentes) setArrastrando(true);
        }}
        onDragLeave={(e) => {
          if (e.currentTarget === e.target) setArrastrando(false);
        }}
        onDrop={alSoltar}
      >
        {/* Barra superior del chat: Título y Banner determinista discreto (cero botones redundantes) */}
        <header className="chat__barra">
          <div className="chat__titulo-wrapper" title={activa?.titulo || 'Nueva solicitud de cotización'}>
            <strong className="chat__titulo">
              {activa ? activa.titulo : 'Nueva solicitud de cotización'}
            </strong>
          </div>

          <div
            className="chat__banner-determinista"
            role="status"
            title={`Motor: ${config?.proveedor || 'Local'} (${config?.modelo || 'Determinista'}) · Latencia de cálculo: ${ajustes?.ultima_cotizacion_ms ? Math.round(ajustes.ultima_cotizacion_ms.total) : 0} ms`}
          >
            <Icono nombre="candado" tamano={13} />
            <span>Cálculo 100% determinista</span>
            <span className="chat__banner-determinista-info" aria-hidden="true">ⓘ</span>
          </div>
        </header>

        {/* Banner preventivo si no hay fuentes cargadas */}
        {!hayFuentes && !cargandoAlmacen && (
          <div className="chat__banner-sin-fuentes" role="alert">
            <div className="chat__banner-alerta-icono">
              <Icono nombre="alerta" tamano={18} />
            </div>
            <div className="chat__banner-alerta-texto">
              <strong>Catálogo y fuentes vacías:</strong> El sistema requiere fuentes de precios registradas antes de cotizar.
            </div>
            <Link to="/fuentes" className="boton boton--primario boton--chico">
              <Icono nombre="fuentes" tamano={14} /> Cargar catálogo en Fuentes
            </Link>
          </div>
        )}

        {/* Cuerpo de mensajes / Estado vacío */}
        <div className="chat__mensajes" role="log" aria-live="polite" aria-label="Mensajes de la conversación">
          {esVacio ? (
            /* ───────── ESTADO VACÍO CENTRADO CON RESPLANDOR Y COMPOSER AL MEDIO ───────── */
            <div className="chat__hero-vacio">
              {!hayFuentes && !cargandoAlmacen ? (
                /* Estado sin fuentes */
                <div className="chat__vacio-sin-fuentes" role="region" aria-label="Sin fuentes cargadas">
                  <div className="chat__vacio-icono-circulo" aria-hidden="true">
                    <Icono nombre="fuentes" tamano={44} />
                  </div>
                  <h2 className="chat__hero-titulo">Aún no hay fuentes cargadas</h2>
                  <p className="chat__hero-subtitulo texto-suave">
                    Carga un catálogo CSV o tarifario en Fuentes para cotizar con precisión histórica.
                  </p>
                  <Link to="/fuentes" className="boton boton--primario boton--pildora" style={{ marginTop: 'var(--e-4)' }}>
                    <Icono nombre="mas" tamano={18} /> Cargar catálogo
                  </Link>
                </div>
              ) : (
                /* Estado con fuentes: Saludo personalizado + Composer centrado + Grid 2x2 */
                <div className="chat__hero-contenido">
                  <div className="chat__hero-resplandor" aria-hidden="true" />
                  <header className="chat__hero-header">
                    <h1 className="chat__hero-titulo">Hola, {primerNombre}. ¿Qué cotización necesitas?</h1>
                    <p className="chat__hero-subtitulo texto-suave">
                      Describe los materiales o adjunta una solicitud; los precios se calculan con tus fuentes.
                    </p>
                  </header>

                  {/* Composer integrado en el centro */}
                  {renderComposer(true)}

                  {/* Sugerencias en cuadrícula 2x2 */}
                  <div className="chat-sugerencias-grid" role="region" aria-label="Sugerencias rápidas">
                    {SUGERENCIAS_CARDS.map((card) => (
                      <button
                        key={card.id}
                        type="button"
                        className="chat-sugerencia-card"
                        onClick={() => usarSugerencia(card.texto)}
                        disabled={enviando || !hayFuentes}
                      >
                        <div className="chat-sugerencia-card__top">
                          <span className="chat-sugerencia-card__badge">
                            <Icono nombre={card.icono} tamano={13} />
                            <span>{card.categoria}</span>
                          </span>
                          <span className="chat-sugerencia-card__flecha" aria-hidden="true">→</span>
                        </div>
                        <p className="chat-sugerencia-card__texto">{card.texto}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ───────── CONVERSACIÓN EN CURSO ───────── */
            <div className="chat__columna">
              {mensajes.map((m) => (
                <div
                  key={m.id}
                  className={`mensaje mensaje--${m.rol}${m.error ? ' mensaje--error' : ''}`}
                >
                  {m.rol === 'tessera' && (
                    <span className="avatar avatar--asistente" aria-hidden="true">T</span>
                  )}

                  <div className="mensaje__cuerpo">
                    {m.rol === 'tessera' && (
                      <span className="mensaje__autor">Tessera</span>
                    )}

                    {/* Tarjeta de error estructurada */}
                    {m.error ? (
                      <div className="tarjeta-aviso-error" role="alert">
                        <div className="tarjeta-aviso-error__icono">
                          <Icono nombre="error" tamano={20} />
                        </div>
                        <div className="tarjeta-aviso-error__contenido">
                          <strong className="tarjeta-aviso-error__titulo">No se pudo procesar la solicitud</strong>
                          <p className="tarjeta-aviso-error__mensaje">{m.texto}</p>
                          <div className="tarjeta-aviso-error__acciones">
                            <button
                              type="button"
                              className="boton boton--chico"
                              onClick={reintentarUltimoMensaje}
                            >
                              <Icono nombre="reintentar" tamano={14} /> Reintentar
                            </button>
                            {!hayFuentes && (
                              <Link to="/fuentes" className="boton boton--chico boton--primario">
                                <Icono nombre="fuentes" tamano={14} /> Ir a Fuentes
                              </Link>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : m.rol === 'tessera' ? (
                      <TextoModelo texto={m.texto} />
                    ) : (
                      /* Mensaje del usuario en tarjeta estructurada */
                      <div className="mensaje-usuario-card">
                        <div className="mensaje-usuario-card__cabecera">
                          <div className="mensaje-usuario-card__identidad">
                            <span className="avatar avatar--usuario" aria-hidden="true">
                              {usuario.nombre.split(' ').map((p) => p[0]).join('').slice(0, 2)}
                            </span>
                            <strong className="mensaje-usuario-card__nombre">{usuario.nombre}</strong>
                            {clienteSeleccionado && (
                              <span className="mensaje-usuario-card__cliente" title="Cliente activo">
                                · {clienteSeleccionado}
                              </span>
                            )}
                          </div>
                          <span className="mensaje-usuario-card__hora texto-suave">
                            {m.meta ? m.meta.split('·')[0].trim() : 'Reciente'}
                          </span>
                        </div>
                        <div className="mensaje-usuario-card__texto">{m.texto}</div>
                      </div>
                    )}

                    {/* Archivos adjuntos */}
                    {m.archivos && m.archivos.length > 0 && (
                      <div className="chat__adjuntos" aria-label="Archivos adjuntos en el mensaje">
                        {m.archivos.map((n) => (
                          <span key={n} className="etiqueta">
                            <Icono nombre="archivo" tamano={12} /> {n}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Avisos contextuales */}
                    {m.avisos?.map((a) => (
                      <p key={a} className="chat__aviso">
                        <Icono nombre="alerta" tamano={14} /> {a}
                      </p>
                    ))}

                    {/* Tarjeta oficial QuoteCard */}
                    {m.cotizacionId && (() => {
                      const cot = cotizaciones.find((c) => c.id === m.cotizacionId);
                      return cot ? (
                        <div className="chat__tarjeta-contenedor">
                          <QuoteCard cotizacion={cot} />
                        </div>
                      ) : null;
                    })()}

                    {m.meta && m.rol === 'tessera' && (
                      <span className="chat__meta texto-suave">{m.meta}</span>
                    )}
                  </div>
                </div>
              ))}

              {/* Indicador de cálculo discreto con skeleton */}
              {enviandoAqui && (
                <div className="herramientas-calculando" role="status" aria-live="assertive">
                  <div className="herramientas-calculando__header">
                    <span className="girando" aria-hidden="true" />
                    <span>Recuperando fuentes y calculando escenarios deterministas…</span>
                    <button className="boton boton--chico boton--fantasma" onClick={cancelar}>
                      Cancelar
                    </button>
                  </div>
                  <div className="esqueleto esqueleto--calculo" aria-hidden="true">
                    <div className="esqueleto__fila esqueleto__fila--encabezado" />
                    <div className="esqueleto__fila" style={{ width: '80%' }} />
                  </div>
                </div>
              )}

              <div ref={finRef} />
            </div>
          )}
        </div>

        {/* Composer fijo al fondo cuando la conversación está activa */}
        {!esVacio && renderComposer(false)}
      </div>

      {/* Columna lateral derecha: Panel de Resumen ejecutivo */}
      <LiveQuoteDrawer
        cotizacion={cotizacionActiva}
        abierto={panelLiveAbierto}
        onAlternar={() => setPanelLiveAbierto((a) => !a)}
      />

      {/* Botón flotante móvil para abrir el borrador */}
      {cotizacionActiva && !panelLiveAbierto && (
        <button
          type="button"
          className="chat__flotante-movil-btn boton boton--primario boton--pildora"
          onClick={() => setPanelLiveAbierto(true)}
          aria-label={`Ver resumen de ${cotizacionActiva.folio}`}
        >
          <Icono nombre="cotizaciones" tamano={16} />
          <span>Resumen {cotizacionActiva.folio}</span>
        </button>
      )}
    </div>
  );
}
