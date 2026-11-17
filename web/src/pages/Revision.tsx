import { useEffect, useMemo, useState, type KeyboardEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CifraAnimada } from '../components/CifraAnimada';
import { DialogoConfirmacion } from '../components/Dialogo';
import { DockAprobacion } from '../components/Dock';
import { EstadoVacio } from '../components/Estados';
import { DetalleCita } from '../components/Fuentes';
import { TablaPartidas } from '../components/Cotizacion';
import { Icono } from '../components/Iconos';
import { PasosEstado } from '../components/Pasos';
import { usePanel } from '../components/Panel';
import { ESCENARIOS, type IdEscenario } from '../data/tipos';
import { calcularCotizacion, formatoMargen, TASA_IVA_PORCIENTO } from '../lib/calculo';
import { formatoFecha, formatoFechaHora, formatoMXN, mesesDeAntiguedad, UMBRAL_ANTIGUEDAD_MESES } from '../lib/dinero';
import { useAlmacen } from '../state/Almacen';

type Dialogo = 'ninguno' | 'aprobar' | 'rechazar' | 'aprendizaje';

export default function Revision() {
  const { id } = useParams();
  const a = useAlmacen();
  const { abrir } = usePanel();
  const cot = a.cotizaciones.find((c) => c.id === id);

  const [escenario, setEscenario] = useState<IdEscenario>('recomendado');
  const [citaActiva, setCitaActiva] = useState<string | undefined>();
  const [dialogo, setDialogo] = useState<Dialogo>('ninguno');
  const [motivo, setMotivo] = useState('');

  // Si ya está aprobada, abre en el escenario aprobado.
  useEffect(() => {
    if (cot?.escenarioAprobado) setEscenario(cot.escenarioAprobado);
  }, [cot?.id, cot?.escenarioAprobado]);

  const verFuente = (citaId: string) => {
    setCitaActiva(citaId);
    abrir('Fuente', <DetalleCita citaId={citaId} />);
  };

  const resultados = useMemo(
    () =>
      cot
        ? (Object.fromEntries(
            ESCENARIOS.map((e) => [e.id, calcularCotizacion(cot.escenarios[e.id].partidas)]),
          ) as Record<IdEscenario, ReturnType<typeof calcularCotizacion>>)
        : null,
    [cot],
  );

  if (!cot || !resultados) {
    return (
      <div className="pagina">
        <EstadoVacio titulo="No encontramos esta cotización" texto="Puede que el folio no exista o que no tengas permiso para verla." accion={{ etiqueta: 'Ver cotizaciones', a: '/cotizaciones' }} />
      </div>
    );
  }

  const esc = cot.escenarios[escenario];
  const r = resultados[escenario];
  const etiquetaEscenario = ESCENARIOS.find((e) => e.id === escenario)?.etiqueta ?? '';
  const editable = cot.estado === 'Borrador' || cot.estado === 'En revisión';
  const antiguas = esc.partidas.filter((p) => {
    const cita = a.citaPorId(p.citaId);
    return cita && mesesDeAntiguedad(cita.fecha) > UMBRAL_ANTIGUEDAD_MESES;
  }).length;
  const ediciones = ESCENARIOS.reduce((n, e) => n + cot.escenarios[e.id].partidas.filter((p) => p.editadaPor).length, 0);

  const alTeclearPestana = (e: KeyboardEvent<HTMLButtonElement>) => {
    const i = ESCENARIOS.findIndex((x) => x.id === escenario);
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (d) {
      e.preventDefault();
      const sig = ESCENARIOS[(i + d + ESCENARIOS.length) % ESCENARIOS.length].id;
      setEscenario(sig);
      document.getElementById(`pestana-${sig}`)?.focus();
    }
  };

  const confirmarAprobacion = () => {
    a.aprobar(cot.id, escenario);
    setDialogo(ediciones > 0 ? 'aprendizaje' : 'ninguno');
    a.avisar(`Cotización ${cot.folio} aprobada. PDF disponible para descargar.`);
  };

  const guardarAprendizaje = () => {
    a.guardarAprendizaje(cot.id, `Ajuste en la Cot. ${cot.folio}: ${cot.cliente} requirió ediciones manuales antes de aprobar.`);
    setDialogo('ninguno');
    a.avisar('Guardado en Memoria como «Por confirmar».', 'info');
  };

  return (
    <div className={`pagina pagina--ancha revision revision--${cot.estado === 'Aprobada' ? 'aprobada' : cot.estado === 'Rechazada' ? 'rechazada' : 'abierta'}`}>
      <header className="revision__cabecera">
        <div>
          <p className="texto-suave migas"><Link to="/cotizaciones">Cotizaciones</Link> / {cot.folio}</p>
          <h1>Cotización {cot.folio}</h1>
          <p className="texto-suave">{cot.cliente} · {formatoFecha(cot.fecha)} · creada por {cot.creadaPor}</p>
        </div>
        <PasosEstado estado={cot.estado} />
      </header>

      {cot.estado === 'Aprobada' && cot.aprobadaPor && cot.fechaAprobacion && (
        <p className="aviso-parcial aviso-parcial--ok" role="note">
          <Icono nombre="check" tamano={16} />
          <span>Aprobada por <strong>{cot.aprobadaPor}</strong> el {formatoFechaHora(cot.fechaAprobacion)}, escenario {ESCENARIOS.find((e) => e.id === cot.escenarioAprobado)?.etiqueta}. Ya no se puede editar.</span>
        </p>
      )}
      {cot.estado === 'Rechazada' && (
        <p className="aviso-parcial aviso-parcial--error" role="note">
          <Icono nombre="error" tamano={16} />
          <span>Rechazada. Motivo: {cot.motivoRechazo}</span>
        </p>
      )}

      <div className="pestanas" role="tablist" aria-label="Escenarios">
        {ESCENARIOS.map((e) => (
          <button
            key={e.id}
            id={`pestana-${e.id}`}
            role="tab"
            aria-selected={escenario === e.id}
            aria-controls="panel-escenario"
            tabIndex={escenario === e.id ? 0 : -1}
            className={`pestana ${escenario === e.id ? 'activa' : ''}`}
            onClick={() => setEscenario(e.id)}
            onKeyDown={alTeclearPestana}
          >
            <span>{e.id === 'recomendado' && <Icono nombre="estrella" tamano={14} />} {e.etiqueta}</span>
            <span className="cifra texto-suave">{formatoMXN(resultados[e.id].total)}</span>
          </button>
        ))}
      </div>

      <section id="panel-escenario" role="tabpanel" aria-labelledby={`pestana-${escenario}`} className="revision__cuerpo">
        <h2>Partidas</h2>
        <TablaPartidas
          partidas={esc.partidas}
          importes={r.importes}
          editable={editable}
          citaActiva={citaActiva}
          onCambio={(pid, cambios) => a.actualizarPartida(cot.id, escenario, pid, cambios)}
          onVerFuente={verFuente}
        />
        <p className="texto-suave leyenda-traza">
          La barra de cada fuente va de 0 a 18 meses; la marca vertical señala el umbral de {UMBRAL_ANTIGUEDAD_MESES} meses.
        </p>

        <div className="totales">
          <dl>
            <div><dt>Subtotal</dt><dd className="cifra">{formatoMXN(r.subtotal)}</dd></div>
            <div><dt>IVA ({TASA_IVA_PORCIENTO} %)</dt><dd className="cifra">{formatoMXN(r.iva)}</dd></div>
            <div className="totales__total"><dt>Total</dt><dd><CifraAnimada centavos={r.total} /></dd></div>
          </dl>
          <div className="margen">
            <span className="texto-suave">Margen estimado</span>
            <strong className="cifra">{formatoMargen(r.margenPuntosBase)}</strong>
            <span className="texto-suave">Dato calculado con los costos de las fuentes; no predice si el cliente aceptará.</span>
          </div>
        </div>
        <p className="texto-suave nota-calculo">Los importes, el IVA y el total los calcula código determinista, no el modelo. Editar cantidad o precio los recalcula al instante.</p>

        <div className="dos-columnas">
          <div>
            <h2><label htmlFor="notas">Notas del agente</label> <span className="texto-suave subtitulo-chico">(editable)</span></h2>
            <textarea
              id="notas"
              className="entrada entrada--area"
              rows={5}
              value={esc.notas}
              disabled={!editable}
              onChange={(e) => a.actualizarNotas(cot.id, escenario, e.target.value)}
            />
          </div>
          <div>
            <h2>Alternativas y riesgos detectados</h2>
            <ul className="lista-simple">
              {antiguas > 0 && (
                <li className="riesgo">
                  <Icono nombre="alerta" tamano={14} /> {antiguas === 1 ? '1 partida usa' : `${antiguas} partidas usan`} un precio de más de {UMBRAL_ANTIGUEDAD_MESES} meses.
                </li>
              )}
              {esc.riesgos.map((t) => <li key={t}>{t}</li>)}
              {antiguas === 0 && esc.riesgos.length === 0 && <li className="texto-suave">No se detectaron riesgos.</li>}
            </ul>
          </div>
        </div>

        <h2>Historial de cambios</h2>
        <ol className="linea-tiempo">
          {[...cot.historial].reverse().map((h, i) => (
            <li key={i} className="linea-tiempo__item">
              <span className="linea-tiempo__fecha cifra">{formatoFechaHora(h.fecha)}</span>
              <span className="linea-tiempo__texto"><strong>{h.usuario}</strong> · {h.texto}</span>
            </li>
          ))}
        </ol>
      </section>

      <DockAprobacion
        estado={cot.estado}
        escenario={etiquetaEscenario}
        total={r.total}
        onAprobar={() => setDialogo('aprobar')}
        onRechazar={() => setDialogo('rechazar')}
        onDescargar={() => a.avisar('PDF simulado: el prototipo todavía no genera archivos.', 'info')}
      />

      <DialogoConfirmacion
        abierto={dialogo === 'aprobar'}
        titulo={`Aprobar la cotización ${cot.folio}`}
        textoConfirmar="Aprobar y generar PDF"
        onCancelar={() => setDialogo('ninguno')}
        onConfirmar={confirmarAprobacion}
      >
        <dl className="lista-datos">
          <dt>Escenario</dt><dd>{etiquetaEscenario}</dd>
          <dt>Partidas</dt><dd>{esc.partidas.length}</dd>
          <dt>Total</dt><dd className="cifra">{formatoMXN(r.total)}</dd>
          <dt>Avisos</dt><dd>{antiguas > 0 ? `${antiguas} con precio antiguo` : 'Sin avisos'}</dd>
        </dl>
        <p>Se registrará que <strong>{a.usuario.nombre}</strong> aprobó esta cotización, quedará como Aprobada y ya no se podrá editar. Después podrás descargar el PDF.</p>
      </DialogoConfirmacion>

      <DialogoConfirmacion
        abierto={dialogo === 'rechazar'}
        titulo={`Rechazar la cotización ${cot.folio}`}
        textoConfirmar="Rechazar"
        peligro
        onCancelar={() => setDialogo('ninguno')}
        onConfirmar={() => {
          a.rechazar(cot.id, motivo.trim());
          setMotivo('');
          setDialogo('ninguno');
          a.avisar(`Cotización ${cot.folio} rechazada.`, 'info');
        }}
      >
        <p>La cotización quedará como Rechazada y no se generará PDF. Puedes dejar el motivo para el historial.</p>
        <label htmlFor="motivo">Motivo (opcional)</label>
        <textarea id="motivo" className="entrada entrada--area" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </DialogoConfirmacion>

      <DialogoConfirmacion
        abierto={dialogo === 'aprendizaje'}
        titulo="¿Guardar este ajuste como aprendizaje?"
        textoConfirmar="Sí, guardar"
        textoCancelar="No, gracias"
        onCancelar={() => setDialogo('ninguno')}
        onConfirmar={guardarAprendizaje}
      >
        <p>Editaste partidas antes de aprobar. Si lo guardas, se agrega a Memoria como «Por confirmar» y no se usará hasta que alguien autorizado lo acepte. Podrás verlo, corregirlo o borrarlo.</p>
      </DialogoConfirmacion>
    </div>
  );
}
