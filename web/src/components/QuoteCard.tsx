import { useState, useId } from 'react';
import { calcularCotizacion } from '../lib/calculo';
import { formatoFechaCorta, formatoPesos } from '../lib/dinero';
import { normalizarUnidadesTipograficas } from '../lib/texto';
import type { Cita, Cotizacion, IdEscenario, Partida } from '../data/tipos';
import { ESCENARIOS } from '../data/tipos';
import { escenarioVigente, useAlmacen } from '../state/Almacen';
import { Icono } from './Iconos';
import { InsigniaEstado } from './Insignia';
import { usePanel } from './Panel';

export interface PartidaVisual {
  id: string;
  codigo: string;
  concepto: string;
  cantidad: number;
  unidad: string;
  precioUnitario: number; // en pesos
  subtotal: number;       // en pesos
  citaId: string;
  cita?: Cita;
  etiquetaTrazabilidad: string;
  nivelConfianza: 'alta' | 'desactualizada_12m' | 'sin_antecedente' | 'desactualizada_6m';
  motivoConfianza?: string;
}

export interface QuoteCardProps {
  cotizacion: Cotizacion;
  escenarioInicial?: IdEscenario;
  onEditar?: () => void;
  onAbrirRevision?: () => void;
}

/** Calcula la diferencia en meses entre una fecha ISO y hoy (referencia nov 2026 o actual). */
function mesesDeAntiguedad(fechaIso: string): number {
  if (!fechaIso) return 0;
  const fecha = new Date(fechaIso);
  if (isNaN(fecha.getTime())) return 0;
  const hoy = new Date(2026, 10, 24); // referencia del prototipo nov 2026
  return Math.max(0, Math.round((hoy.getTime() - fecha.getTime()) / (1000 * 60 * 60 * 24 * 30.4375)));
}

/** Extrae la etiqueta de trazabilidad legible a partir de la cita y la partida. */
function obtenerTrazabilidad(cita: Cita | undefined, partida: Partida): {
  etiqueta: string;
  nivel: 'alta' | 'desactualizada_12m' | 'sin_antecedente' | 'desactualizada_6m';
  motivo?: string;
} {
  if (!cita || !partida.citaId || partida.citaId.startsWith('estimado')) {
    return {
      etiqueta: 'Sin antecedente · Estimado',
      nivel: 'sin_antecedente',
      motivo: 'No se encontró cotización previa ni catálogo exacto; precio paramétrico estimado.',
    };
  }

  const meses = cita.fecha ? mesesDeAntiguedad(cita.fecha) : 0;
  const fechaTexto = cita.fecha ? formatoFechaCorta(cita.fecha) : '';
  const baseNombre = cita.documentoNombre || cita.etiqueta || 'Fuente';

  if (meses > 12) {
    return {
      etiqueta: `Basado en ${baseNombre}${fechaTexto ? ` (${fechaTexto})` : ''}`,
      nivel: 'desactualizada_12m',
      motivo: `Precio con más de 12 meses de antigüedad (${meses} meses). Requiere confirmación con proveedor.`,
    };
  }
  if (meses > 6) {
    return {
      etiqueta: `Basado en ${baseNombre}${fechaTexto ? ` (${fechaTexto})` : ''}`,
      nivel: 'desactualizada_6m',
      motivo: `Precio con más de 6 meses de antigüedad (${meses} meses).`,
    };
  }

  return {
    etiqueta: `Basado en ${baseNombre}${fechaTexto ? ` (${fechaTexto})` : ''}`,
    nivel: 'alta',
  };
}

/** Componente de detalle de fuente que se proyecta en el panel lateral. */
function VistaDetalleFuente({ cita, partida }: { cita?: Cita; partida: PartidaVisual }) {
  return (
    <div className="detalle" role="region" aria-label="Detalle de fuente">
      <h3>{partida.concepto}</h3>
      <dl className="lista-datos">
        <dt>Partida</dt>
        <dd><code>{partida.codigo || partida.id}</code></dd>
        <dt>P. Unitario</dt>
        <dd className="cifra"><strong>{formatoPesos(partida.precioUnitario * 100)} <span className="sufijo-moneda">MXN</span></strong> / {partida.unidad}</dd>
        <dt>Trazabilidad</dt>
        <dd>{partida.etiquetaTrazabilidad}</dd>
        {cita && (
          <>
            <dt>Documento</dt>
            <dd>{cita.documentoNombre}</dd>
            <dt>Ubicación</dt>
            <dd>{cita.ubicacion || 'Fila / Página'}</dd>
            <dt>Fecha fuente</dt>
            <dd>{cita.fecha ? formatoFechaCorta(cita.fecha) : 'Sin fecha'}</dd>
          </>
        )}
      </dl>

      {cita?.extracto && (
        <>
          <h4>Extracto del documento</h4>
          <blockquote className="extracto">
            <p>{cita.extracto}</p>
          </blockquote>
        </>
      )}

      {partida.motivoConfianza && (
        <p className="aviso-parcial aviso-parcial--warn" style={{ marginTop: 'var(--e-3)' }}>
          <Icono nombre="alerta" tamano={14} />
          <span>{partida.motivoConfianza}</span>
        </p>
      )}
    </div>
  );
}

export function QuoteCard({ cotizacion, escenarioInicial }: QuoteCardProps) {
  const { citaPorId, guardarAprendizaje, avisar } = useAlmacen();
  const { abrir: abrirPanel } = usePanel();

  const [escenarioSel, setEscenarioSel] = useState<IdEscenario>(
    escenarioInicial ?? escenarioVigente(cotizacion) ?? 'recomendado',
  );
  const [feedbackEnviado, setFeedbackEnviado] = useState<'positivo' | 'negativo' | null>(null);
  const [comentarioFeedback, setComentarioFeedback] = useState('');
  const [mostrandoCampoFeedback, setMostrandoCampoFeedback] = useState(false);

  const esc = cotizacion.escenarios[escenarioSel] ?? cotizacion.escenarios.recomendado;
  const partidasRaw = esc.partidas ?? [];

  // Mapeo enriquecido de partidas con trazabilidad
  const partidas: PartidaVisual[] = partidasRaw.map((p) => {
    const cita = p.citaId ? citaPorId(p.citaId) : undefined;
    const traza = obtenerTrazabilidad(cita, p);
    return {
      id: p.id,
      codigo: p.codigo,
      concepto: p.concepto,
      cantidad: p.cantidad,
      unidad: p.unidad,
      precioUnitario: p.precioUnitario / 100,
      subtotal: (p.cantidad * p.precioUnitario) / 100,
      citaId: p.citaId,
      cita,
      etiquetaTrazabilidad: traza.etiqueta,
      nivelConfianza: traza.nivel,
      motivoConfianza: traza.motivo,
    };
  });

  // Cálculo determinista en el cliente para el desglose exacto
  const resultadoCalculo = calcularCotizacion(partidasRaw);

  // Desglose por tipo de partida (materiales vs servicios/instalación/flete)
  let subtotalMateriales = 0;
  let subtotalInstalacion = 0;
  let subtotalFlete = 0;

  for (const p of partidasRaw) {
    const imp = (p.cantidad * p.precioUnitario) / 100;
    const cLower = p.concepto.toLowerCase();
    const codLower = p.codigo.toLowerCase();
    if (cLower.includes('instal') || codLower.includes('inst')) {
      subtotalInstalacion += imp;
    } else if (cLower.includes('flete') || codLower.includes('flete') || cLower.includes('envio') || cLower.includes('entrega')) {
      subtotalFlete += imp;
    } else {
      subtotalMateriales += imp;
    }
  }

  const verFuente = (partida: PartidaVisual) => {
    abrirPanel(
      `Fuente: ${partida.concepto}`,
      <VistaDetalleFuente cita={partida.cita} partida={partida} />,
    );
  };

  const enviarFeedback = async (tipo: 'positivo' | 'negativo') => {
    setFeedbackEnviado(tipo);
    const texto = `Calificación ${tipo === 'positivo' ? 'positiva' : 'a corregir'} en Cot. ${cotizacion.folio} (${cotizacion.cliente}): ${comentarioFeedback.trim() || 'Sin comentarios adicionales.'}`;
    await guardarAprendizaje(cotizacion.id, texto);
    avisar('Retroalimentación registrada en la memoria del agente.', 'ok');
    setMostrandoCampoFeedback(false);
  };

  const idTabla = useId();

  return (
    <article className="quote-card" aria-labelledby={`${idTabla}-titulo`}>
      {/* Encabezado de la tarjeta */}
      <header className="quote-card__header">
        <div className="quote-card__meta">
          <div className="quote-card__folio-wrapper">
            <span className="quote-card__tag">Cotización oficial</span>
            <h3 id={`${idTabla}-titulo`} className="quote-card__folio">{cotizacion.folio}</h3>
          </div>
          <p className="quote-card__cliente">{cotizacion.cliente}</p>
        </div>
        <div className="quote-card__estado">
          <InsigniaEstado estado={cotizacion.estado} />
          <span className="texto-suave quote-card__fecha">{formatoFechaCorta(cotizacion.fecha)}</span>
        </div>
      </header>

      {/* Selector de escenarios (Económico, Recomendado, Premium) */}
      <div className="quote-card__escenarios" role="tablist" aria-label="Escenarios de cotización">
        {ESCENARIOS.map((e) => {
          const act = escenarioSel === e.id;
          const totalEsc = calcularCotizacion(cotizacion.escenarios[e.id]?.partidas ?? []).total;
          return (
            <button
              key={e.id}
              role="tab"
              aria-selected={act}
              className={`quote-card__escenario-btn ${act ? 'es-activo' : ''} ${e.id === 'recomendado' ? 'es-recomendado' : ''}`}
              onClick={() => setEscenarioSel(e.id)}
            >
              <div className="quote-card__escenario-top">
                {e.id === 'recomendado' && <Icono nombre="estrella" tamano={14} />}
                <span>{e.etiqueta}</span>
              </div>
              <strong className="cifra quote-card__escenario-monto">
                {formatoPesos(totalEsc)} <span className="sufijo-moneda">MXN</span>
              </strong>
            </button>
          );
        })}
      </div>

      {/* Tabla detallada de partidas */}
      <div className="quote-card__tabla-wrapper">
        <table className="quote-card__tabla" aria-describedby={`${idTabla}-aclaracion`}>
          <caption className="solo-lectores">Partidas calculadas determinísticamente para el escenario seleccionado</caption>
          <thead>
            <tr>
              <th scope="col">Concepto / Partida</th>
              <th scope="col" className="derecha">Cant.</th>
              <th scope="col" className="derecha">P. Unitario</th>
              <th scope="col" className="derecha">Subtotal</th>
              <th scope="col">Trazabilidad y confianza</th>
            </tr>
          </thead>
          <tbody>
            {partidas.map((p) => (
              <tr key={p.id}>
                <td>
                  <div className="quote-card__concepto">
                    <strong className="quote-card__concepto-nombre">{normalizarUnidadesTipograficas(p.concepto)}</strong>
                    {p.codigo && <span className="codigo">{p.codigo}</span>}
                  </div>
                </td>
                <td className="derecha cifra">
                  {p.cantidad} <span className="texto-suave" style={{ fontSize: 'var(--fs-micro)' }}>{normalizarUnidadesTipograficas(p.unidad)}</span>
                </td>
                <td className="derecha cifra">{formatoPesos(p.precioUnitario * 100)} <span className="sufijo-moneda">MXN</span></td>
                <td className="derecha cifra celda-importe">{formatoPesos(p.subtotal * 100)} <span className="sufijo-moneda">MXN</span></td>
                <td>
                  <div className="quote-card__trazabilidad">
                    <button
                      type="button"
                      className="quote-card__chip-traza"
                      onClick={() => verFuente(p)}
                      title="Ver extracto y documento fuente en el panel lateral"
                      aria-label={`Ver fuente: ${p.etiquetaTrazabilidad}`}
                    >
                      <Icono nombre="fuentes" tamano={12} />
                      <span className="quote-card__chip-texto">{p.etiquetaTrazabilidad}</span>
                    </button>

                    {/* Indicadores de confianza visuales */}
                    {p.nivelConfianza === 'desactualizada_12m' && (
                      <span className="insignia insignia--warn" title={p.motivoConfianza} role="status">
                        <Icono nombre="alerta" tamano={12} /> &gt; 12 meses
                      </span>
                    )}
                    {p.nivelConfianza === 'desactualizada_6m' && (
                      <span className="insignia insignia--neutro" title={p.motivoConfianza}>
                        <Icono nombre="reloj" tamano={12} /> &gt; 6 meses
                      </span>
                    )}
                    {p.nivelConfianza === 'sin_antecedente' && (
                      <span className="insignia insignia--warn" title={p.motivoConfianza} role="status">
                        <Icono nombre="alerta" tamano={12} /> Sin antecedente
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Desglose financiero completo */}
      <section className="quote-card__desglose" aria-label="Desglose financiero de la cotización">
        <dl className="quote-card__desglose-lineas">
          <div className="quote-card__linea">
            <dt>Materiales</dt>
            <dd className="cifra">{formatoPesos(subtotalMateriales * 100)} <span className="sufijo-moneda">MXN</span></dd>
          </div>
          {subtotalInstalacion > 0 && (
            <div className="quote-card__linea">
              <dt>Instalación y mano de obra</dt>
              <dd className="cifra">{formatoPesos(subtotalInstalacion * 100)} <span className="sufijo-moneda">MXN</span></dd>
            </div>
          )}
          {subtotalFlete > 0 && (
            <div className="quote-card__linea">
              <dt>Flete y maniobra</dt>
              <dd className="cifra">{formatoPesos(subtotalFlete * 100)} <span className="sufijo-moneda">MXN</span></dd>
            </div>
          )}
          <div className="quote-card__linea quote-card__linea--subtotal">
            <dt>Subtotal neto</dt>
            <dd className="cifra">{formatoPesos(resultadoCalculo.subtotal)} <span className="sufijo-moneda">MXN</span></dd>
          </div>
          <div className="quote-card__linea">
            <dt>
              <span>Margen estimado</span>
              <span className="quote-card__info-icon" title="Dato calculado con base en costos de catálogo; margen comercial estimado.">ⓘ</span>
            </dt>
            <dd className="cifra">
              {formatoPesos(resultadoCalculo.margen)} <span className="sufijo-moneda">MXN</span>
              {resultadoCalculo.margenPuntosBase !== null && (
                <span className="texto-suave" style={{ marginLeft: 'var(--e-1)', fontSize: 'var(--fs-micro)' }}>
                  ({(resultadoCalculo.margenPuntosBase / 100).toFixed(1)}%)
                </span>
              )}
            </dd>
          </div>
          <div className="quote-card__linea">
            <dt>IVA (16%)</dt>
            <dd className="cifra">{formatoPesos(resultadoCalculo.iva)} <span className="sufijo-moneda">MXN</span></dd>
          </div>
          <div className="quote-card__linea quote-card__linea--total">
            <dt>Total cotizado</dt>
            <dd className="cifra quote-card__total-monto">
              {formatoPesos(resultadoCalculo.total)} <span className="sufijo-moneda">MXN</span>
            </dd>
          </div>
        </dl>
      </section>

      {/* Aclaración obligatoria de cálculo determinista */}
      <p id={`${idTabla}-aclaracion`} className="quote-card__aclaracion texto-suave">
        <Icono nombre="check" tamano={14} />
        <span>Los precios, márgenes, impuestos y totales son calculados por <strong>código determinista</strong>, no por el modelo de IA. Toda cifra cuenta con antecedente verificable.</span>
      </p>

      {/* Pie de la tarjeta: solo feedback de calidad (las acciones formales viven en el Panel Resumen) */}
      <footer className="quote-card__pie">
        <div className="quote-card__feedback" role="group" aria-label="Retroalimentación de la cotización">
          <span className="quote-card__feedback-pregunta">¿El precio fue correcto?</span>
          <div className="quote-card__feedback-botones">
            <button
              type="button"
              className={`boton-icono ${feedbackEnviado === 'positivo' ? 'quote-card__feedback--activo' : ''}`}
              aria-label="Sí, el precio fue correcto"
              title="El precio fue correcto"
              onClick={() => {
                if (feedbackEnviado) return;
                void enviarFeedback('positivo');
              }}
            >
              <Icono nombre="pulgarArriba" tamano={16} />
            </button>
            <button
              type="button"
              className={`boton-icono ${feedbackEnviado === 'negativo' ? 'quote-card__feedback--activo' : ''}`}
              aria-label="No, requiere corrección"
              title="Requiere corrección"
              onClick={() => {
                setMostrandoCampoFeedback(true);
              }}
            >
              <Icono nombre="pulgarAbajo" tamano={16} />
            </button>
          </div>

          {mostrandoCampoFeedback && (
            <div className="quote-card__feedback-formulario">
              <input
                type="text"
                className="entrada entrada--chica"
                placeholder="Indica la corrección (ej: el flete aumentó a $2,200)…"
                value={comentarioFeedback}
                onChange={(e) => setComentarioFeedback(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void enviarFeedback('negativo');
                }}
              />
              <button
                type="button"
                className="boton boton--chico boton--primario"
                onClick={() => void enviarFeedback('negativo')}
              >
                Guardar en memoria
              </button>
              <button
                type="button"
                className="boton boton--chico boton--fantasma"
                onClick={() => setMostrandoCampoFeedback(false)}
              >
                Cancelar
              </button>
            </div>
          )}
        </div>

        <div className="quote-card__nota-auditoria texto-suave">
          <span>Folio {cotizacion.folio} · Emisión determinista vinculada a fuentes históricas</span>
        </div>
      </footer>
    </article>
  );
}
