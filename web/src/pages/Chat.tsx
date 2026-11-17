import { Fragment, useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { ChipFuente, DetalleCita } from '../components/Fuentes';
import { TarjetaCotizacion } from '../components/Cotizacion';
import { Icono } from '../components/Iconos';
import { usePanel } from '../components/Panel';
import { useAlmacen } from '../state/Almacen';

interface Mensaje {
  id: number;
  rol: 'usuario' | 'tessera';
  texto: string;
  citas?: string[]; // ids de cita, en el orden de [1], [2]…
  cotizacionId?: string;
  memoria?: string[];
}

const SUGERENCIAS = [
  'Cotiza 20 gabinetes metálicos con instalación y transporte a Mérida',
  '¿Cuánto cobramos de flete a Progreso la última vez?',
  'Prepara una cotización para 8 gabinetes GM-200 instalados',
];

const PASOS = ['Buscando cotizaciones parecidas…', 'Leyendo fichas técnicas…', 'Calculando totales…'];

/** Convierte «[1]» en chips de fuente que abren el panel derecho. */
function TextoConCitas({ texto, citas, activa, onAbrir }: { texto: string; citas: string[]; activa?: string; onAbrir: (id: string) => void }) {
  const partes: ReactNode[] = texto.split(/(\[\d+\])/g).map((parte, i) => {
    const m = /^\[(\d+)\]$/.exec(parte);
    if (!m) return <Fragment key={i}>{parte}</Fragment>;
    const id = citas[Number(m[1]) - 1];
    return id ? <ChipFuente key={i} citaId={id} numero={Number(m[1])} activo={activa === id} onAbrir={onAbrir} /> : <Fragment key={i}>{parte}</Fragment>;
  });
  return <p>{partes}</p>;
}

export default function Chat() {
  const { cotizaciones, citaPorId, memoria, usuario } = useAlmacen();
  const { abrir, cerrar } = usePanel();
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [texto, setTexto] = useState('');
  const [paso, setPaso] = useState<number | null>(null);
  const [citaActiva, setCitaActiva] = useState<string | undefined>();
  const [citasPanel, setCitasPanel] = useState<string[]>([]);
  const temporizador = useRef<number | undefined>();
  const finRef = useRef<HTMLDivElement>(null);
  const siguiente = useRef(1);

  const cotizacion = cotizaciones.find((c) => c.id === '0123');
  const memoriaAplicada = memoria.filter((m) => m.estado === 'Activa' && m.texto.includes('Constructora Peninsular')).map((m) => m.texto);

  // Panel «Fuentes usadas» + «Memoria aplicada» del último mensaje del agente.
  useEffect(() => {
    if (citasPanel.length === 0) return;
    abrir(
      'Fuentes usadas',
      <div className="detalle">
        <ul className="lista-simple lista-fuentes">
          {citasPanel.map((id, i) => {
            const c = citaPorId(id);
            return (
              <li key={id}>
                <ChipFuente citaId={id} numero={i + 1} activo={citaActiva === id} onAbrir={setCitaActiva} />
                <span className="texto-suave">{c?.ubicacion}</span>
              </li>
            );
          })}
        </ul>
        {citaActiva && <DetalleCita citaId={citaActiva} />}
        {memoriaAplicada.length > 0 && (
          <>
            <h3>Memoria aplicada</h3>
            <ul className="lista-simple">
              {memoriaAplicada.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </>
        )}
      </div>,
    );
  }, [citasPanel, citaActiva, abrir, citaPorId, memoria]);

  useEffect(() => {
    return () => {
      window.clearTimeout(temporizador.current);
    };
  }, []);
  useEffect(() => {
    finRef.current?.scrollIntoView({ block: 'end' });
  }, [mensajes, paso]);

  const abrirCita = useCallback((id: string) => setCitaActiva(id), []);

  const correrPaso = (n: number) => {
    if (n < PASOS.length) {
      setPaso(n);
      temporizador.current = window.setTimeout(() => correrPaso(n + 1), 900);
      return;
    }
    setPaso(null);
    const citas = ['c1', 'c2', 'c3', 'c4'];
    setMensajes((m) => [
      ...m,
      {
        id: siguiente.current++,
        rol: 'tessera',
        texto: `Encontré 4 fuentes parecidas: la cotización más cercana [1] y la de instalación [2], la ficha del gabinete [3] y el flete a Mérida [4]. Preparé tres escenarios. El precio del flete tiene 14 meses; confírmalo antes de aprobar.`,
        citas,
        cotizacionId: '0123',
        memoria: memoriaAplicada,
      },
    ]);
    setCitasPanel(citas);
    setCitaActiva(undefined);
  };

  const enviar = (t: string) => {
    const limpio = t.trim();
    if (!limpio || paso !== null) return;
    setMensajes((m) => [...m, { id: siguiente.current++, rol: 'usuario', texto: limpio }]);
    setTexto('');
    correrPaso(0);
  };

  const cancelar = () => {
    window.clearTimeout(temporizador.current);
    setPaso(null);
    setMensajes((m) => [...m, { id: siguiente.current++, rol: 'tessera', texto: 'Cancelaste la búsqueda. No se generó ninguna cotización.' }]);
  };

  const alTeclear = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviar(texto);
    }
  };

  const nueva = () => {
    window.clearTimeout(temporizador.current);
    setMensajes([]);
    setPaso(null);
    setCitasPanel([]);
    setCitaActiva(undefined);
    cerrar();
  };

  return (
    <div className="chat">
      <div className="chat__barra">
        <strong>{mensajes.length === 0 ? 'Nueva conversación' : 'Conversación'}</strong>
        <button className="boton" onClick={nueva}>
          <Icono nombre="mas" tamano={16} /> Nueva
        </button>
      </div>

      <div className="chat__mensajes" role="log" aria-live="polite" aria-label="Conversación">
        <div className="chat__columna">
          {mensajes.length === 0 && (
            <div className="chat__vacio">
              <h1>¿Qué cotización necesitas?</h1>
              <p className="texto-suave">Descríbela con tus palabras. Tessera busca historial parecido, propone tres escenarios y tú los revisas antes de aprobar.</p>
              <div className="sugerencias">
                {SUGERENCIAS.map((s) => (
                  <button key={s} className="sugerencia" onClick={() => enviar(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {mensajes.map((m) => (
            <div key={m.id} className={`mensaje mensaje--${m.rol}`}>
              <span className="avatar" aria-hidden="true">{m.rol === 'usuario' ? usuario.nombre.split(' ').map((p) => p[0]).join('') : 'T'}</span>
              <div className="mensaje__cuerpo">
                <span className="mensaje__autor">{m.rol === 'usuario' ? 'Tú' : 'Tessera'}</span>
                {m.citas ? <TextoConCitas texto={m.texto} citas={m.citas} activa={citaActiva} onAbrir={abrirCita} /> : <p>{m.texto}</p>}
                {m.cotizacionId && cotizacion && <TarjetaCotizacion cotizacion={cotizacion} />}
              </div>
            </div>
          ))}

          {paso !== null && (
            <div className="herramientas" role="status">
              <span className="girando" aria-hidden="true" />
              <span>{PASOS[paso]}</span>
              <button className="boton boton--chico" onClick={cancelar}>Cancelar</button>
            </div>
          )}
          <div ref={finRef} />
        </div>
      </div>

      <form className="chat__entrada" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
        <label className="solo-lectores" htmlFor="solicitud">Solicitud de cotización</label>
        <textarea
          id="solicitud"
          rows={2}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={alTeclear}
          placeholder="Escribe tu solicitud… (Enter envía, Mayús+Enter salta de línea)"
        />
        <button className="boton boton--primario" type="submit" disabled={!texto.trim() || paso !== null}>
          <Icono nombre="enviar" tamano={16} /> Enviar
        </button>
      </form>
      <p className="texto-suave chat__nota">Prototipo: las respuestas son simuladas y no usan ningún modelo.</p>
    </div>
  );
}
