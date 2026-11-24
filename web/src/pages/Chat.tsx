import { Fragment, useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react';
import { Icono } from '../components/Iconos';
import { MedidorUso } from '../components/MedidorUso';
import { enviarChat, obtenerConfigChat, obtenerUsoChat, type ConfigChat, type RespuestaChat, type UsoChat } from '../lib/api';
import { tamanoLegible, tramosConNegrita } from '../lib/texto';
import { useAlmacen } from '../state/Almacen';

interface Mensaje {
  id: number;
  rol: 'usuario' | 'tessera';
  texto: string;
  archivos?: string[]; // nombres de los archivos que viajaron con este mensaje
  meta?: string; // modelo · latencia · tokens
  avisos?: string[];
  error?: boolean;
}

const SUGERENCIAS = [
  'Cotiza 20 gabinetes metálicos con instalación y transporte a Mérida',
  '¿Cuánto cobramos de flete a Progreso la última vez?',
  'Prepara una cotización para 8 gabinetes GM-200 instalados',
];

const ACEPTA = '.txt,.md,.json,.log,.xml,.yaml,.yml,.csv,.tsv,.xlsx,.xlsm,.pdf,.png,.jpg,.jpeg,.webp,.gif';
const MAX_ARCHIVOS = 5; // igual que api/chat.py

/** Línea discreta bajo cada respuesta: qué modelo respondió y cuánto tardó. Los tokens van en la esquina (MedidorUso). */
function metaDe(r: RespuestaChat): string {
  return `${r.modelo} · ${r.latencia_s.toFixed(1)} s`;
}

/** Texto del modelo: respeta saltos de línea e interpreta solo la **negrita**. */
function TextoModelo({ texto }: { texto: string }) {
  return (
    <p className="mensaje__texto">
      {tramosConNegrita(texto).map((t, i) => (t.negrita ? <strong key={i}>{t.texto}</strong> : <Fragment key={i}>{t.texto}</Fragment>))}
    </p>
  );
}

export default function Chat() {
  const { usuario } = useAlmacen();
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [texto, setTexto] = useState('');
  const [archivos, setArchivos] = useState<File[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [config, setConfig] = useState<ConfigChat | null>(null);
  const [errorConfig, setErrorConfig] = useState<string | null>(null);
  const [uso, setUso] = useState<UsoChat | null>(null);
  const [errorUso, setErrorUso] = useState<string | null>(null);
  const control = useRef<AbortController | null>(null);
  const refrescoTardio = useRef<number | undefined>(undefined);
  const finRef = useRef<HTMLDivElement>(null);
  const selector = useRef<HTMLInputElement>(null);
  const areaTexto = useRef<HTMLTextAreaElement>(null);
  const siguiente = useRef(1);

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
      control.current?.abort();
    };
  }, [refrescarUso]);
  useEffect(() => {
    finRef.current?.scrollIntoView({ block: 'end' });
  }, [mensajes, enviando]);
  // La caja de texto crece con lo que se escribe (hasta un máximo en CSS) y vuelve a una línea al enviar.
  useEffect(() => {
    const el = areaTexto.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [texto]);

  const agregarArchivos = (nuevos: File[]) => {
    if (nuevos.length === 0) return;
    setArchivos((actuales) => {
      const unicos = nuevos.filter((n) => !actuales.some((a) => a.name === n.name && a.size === n.size));
      return [...actuales, ...unicos].slice(0, MAX_ARCHIVOS);
    });
  };

  const alElegir = (e: ChangeEvent<HTMLInputElement>) => {
    agregarArchivos(Array.from(e.target.files ?? []));
    e.target.value = ''; // permite volver a elegir el mismo archivo
  };

  const alSoltar = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    agregarArchivos(Array.from(e.dataTransfer.files));
  };

  const agregarMensaje = (m: Omit<Mensaje, 'id'>) => setMensajes((ms) => [...ms, { ...m, id: siguiente.current++ }]);

  const enviar = async (t: string) => {
    const limpio = t.trim();
    if (!limpio || enviando) return;
    const historial = mensajes.filter((m) => !m.error).map((m) => ({ rol: m.rol, texto: m.texto }));
    const adjuntos = archivos;
    agregarMensaje({ rol: 'usuario', texto: limpio, archivos: adjuntos.map((a) => a.name) });
    setTexto('');
    setEnviando(true);
    const controlador = new AbortController();
    control.current = controlador;
    try {
      const r = await enviarChat({ mensaje: limpio, historial, archivos: adjuntos, signal: controlador.signal });
      agregarMensaje({
        rol: 'tessera',
        texto: r.texto || '(sin respuesta)',
        meta: metaDe(r),
        avisos: r.avisos,
        error: !r.texto,
      });
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        agregarMensaje({ rol: 'tessera', texto: 'Cancelaste la consulta. No se generó ninguna respuesta.', error: true });
      } else {
        agregarMensaje({ rol: 'tessera', texto: e instanceof Error ? e.message : 'Error inesperado.', error: true });
      }
    } finally {
      setEnviando(false);
      control.current = null;
      refrescarUso(); // cada mensaje (incluso uno que falló con 429) cambia lo que queda
      // OpenRouter refleja el contador diario con ~30 s de retraso [Certeza: medido el 23/11/2026]: se vuelve a leer.
      window.clearTimeout(refrescoTardio.current);
      refrescoTardio.current = window.setTimeout(refrescarUso, 35_000);
    }
  };

  const alTeclear = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void enviar(texto);
    }
  };

  const nueva = () => {
    control.current?.abort();
    setMensajes([]);
    setArchivos([]);
    setEnviando(false);
  };

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
        <strong>{mensajes.length === 0 ? 'Nueva conversación' : 'Conversación'}</strong>
        <div className="chat__acciones">
          <MedidorUso uso={uso} error={errorUso} modeloVision={config?.modelo_vision} />
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
                Descríbela con tus palabras. Para probar la lectura de archivos, adjunta un PDF, Excel, CSV o una imagen (con el clip de la barra de mensajes o arrastrándolos aquí).
              </p>
              <div className="sugerencias">
                {SUGERENCIAS.map((s) => (
                  <button key={s} className="sugerencia" onClick={() => void enviar(s)}>
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
                {m.meta && <span className="chat__meta">{m.meta}</span>}
              </div>
            </div>
          ))}

          {enviando && (
            <div className="herramientas" role="status">
              <span className="girando" aria-hidden="true" />
              <span>Esperando al modelo…</span>
              <button className="boton boton--chico" onClick={() => control.current?.abort()}>Cancelar</button>
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
              <button
                type="button"
                className="chat__quitar"
                aria-label={`Quitar ${a.name}`}
                onClick={() => setArchivos((as) => as.filter((x) => x !== a))}
              >
                <Icono nombre="cerrar" tamano={12} />
              </button>
            </span>
          ))}
          <span className="texto-suave chat__pista">Se reenvían con cada mensaje hasta que los quites.</span>
        </div>
      )}

      <form className="chat__entrada" onSubmit={(e) => { e.preventDefault(); void enviar(texto); }}>
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
          placeholder="Escribe tu solicitud…"
        />
        <button className="boton boton--primario chat__enviar" type="submit" disabled={!texto.trim() || enviando}>
          <Icono nombre="enviar" tamano={16} /> Enviar
        </button>
      </form>
      <p className="texto-suave chat__nota">
        {errorConfig
          ? errorConfig
          : config
            ? `Modo prueba · ${config.proveedor}: ${config.modelo}. `
            : 'Conectando con la API… '}
        Enter envía, Mayús+Enter salta de línea. Aún no consulta la base de datos ni calcula cotizaciones: no uses sus cifras como precios.
      </p>
    </div>
  );
}
