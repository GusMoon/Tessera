import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { calcularCotizacion } from '../lib/calculo';
import { formatoPesos } from '../lib/dinero';
import type { Cotizacion } from '../data/tipos';
import { ESCENARIOS } from '../data/tipos';
import { escenarioVigente, useAlmacen } from '../state/Almacen';
import { Icono } from './Iconos';
import { InsigniaEstado } from './Insignia';

export interface LiveQuoteDrawerProps {
  cotizacion: Cotizacion | null;
  abierto: boolean;
  onAlternar: () => void;
}

export function LiveQuoteDrawer({ cotizacion, abierto, onAlternar }: LiveQuoteDrawerProps) {
  const { descargarPdf, aprobar, puedeAprobar, avisar } = useAlmacen();
  const [menuMasAbierto, setMenuMasAbierto] = useState(false);
  const [aprobando, setAprobando] = useState(false);
  const refMenu = useRef<HTMLDivElement>(null);

  const c = cotizacion;
  const escId = c ? escenarioVigente(c) : 'recomendado';
  const esc = c ? c.escenarios[escId] : null;
  const partidas = esc?.partidas ?? [];
  const calculo = esc ? calcularCotizacion(partidas) : null;
  const escenarioInfo = ESCENARIOS.find((e) => e.id === escId) ?? ESCENARIOS[0];

  useEffect(() => {
    const clickAfuera = (e: MouseEvent) => {
      if (refMenu.current && !refMenu.current.contains(e.target as Node)) {
        setMenuMasAbierto(false);
      }
    };
    if (menuMasAbierto) {
      document.addEventListener('mousedown', clickAfuera);
    }
    return () => document.removeEventListener('mousedown', clickAfuera);
  }, [menuMasAbierto]);

  const descargar = async () => {
    if (!c) return;
    try {
      await descargarPdf(c.id);
      avisar(`Descargando PDF de ${c.folio}…`, 'ok');
    } catch {
      avisar('No se pudo generar el PDF de la cotización.', 'error');
    }
  };

  const manejarAprobar = async () => {
    if (!c) return;
    if (!puedeAprobar) {
      avisar('Tu rol actual no tiene permisos para aprobar cotizaciones.', 'info');
      return;
    }
    setAprobando(true);
    setMenuMasAbierto(false);
    try {
      const ok = await aprobar(c.id, escId);
      if (ok) avisar(`Cotización ${c.folio} aprobada con éxito.`, 'ok');
    } catch {
      avisar('Error al aprobar la cotización.', 'error');
    } finally {
      setAprobando(false);
    }
  };

  const hacerScrollATarjeta = () => {
    const el = document.querySelector('.quote-card');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  // Tab colapsado vertical delgado cuando el panel está cerrado
  if (!abierto) {
    return (
      <aside className="live-quote-tab" aria-label="Borrador en vivo colapsado">
        <button
          type="button"
          className="live-quote-tab__boton"
          onClick={onAlternar}
          title={c ? `Ver resumen de ${c.folio} (Alt+P)` : 'Ver resumen de cotización (Alt+P)'}
          aria-label="Abrir panel de resumen"
        >
          <div className="live-quote-tab__icono-wrap">
            <Icono nombre="cotizaciones" tamano={18} />
            {c && <span className="live-quote-tab__indicador" aria-hidden="true" />}
          </div>
          <span className="live-quote-tab__texto">
            {c ? c.folio : 'Resumen'}
          </span>
        </button>
      </aside>
    );
  }

  // Panel expandido de RESUMEN (no duplica tabla ni tarjetas de variantes)
  return (
    <aside className="live-quote-panel" aria-label="Panel resumen de cotización">
      <header className="live-quote-panel__cabecera">
        <div className="live-quote-panel__titulo-grupo">
          <Icono nombre="cotizaciones" tamano={20} />
          <h2 className="live-quote-panel__titulo">
            {c ? `Resumen: ${c.folio}` : 'Resumen de cotización'}
          </h2>
        </div>
        <button
          type="button"
          className="boton-icono"
          onClick={onAlternar}
          aria-label="Colapsar panel de resumen"
          title="Colapsar panel (Alt+P)"
        >
          <Icono nombre="derecha" tamano={18} />
        </button>
      </header>

      <div className="live-quote-panel__contenido">
        {!c ? (
          <div className="live-quote-panel__vacio">
            <div className="live-quote-panel__vacio-icono">
              <Icono nombre="chat" tamano={40} />
            </div>
            <div className="live-quote-panel__vacio-texto">
              <strong className="live-quote-panel__vacio-titulo">Sin cotización activa</strong>
              <p className="texto-suave">
                Describe los materiales en el chat para generar una cotización determinista. El resumen ejecutivo y las acciones de emisión aparecerán aquí.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Metadatos: Cliente y Estado */}
            <div className="live-quote-resumen__tarjeta-meta">
              <div className="live-quote-resumen__cliente-bloque">
                <span className="live-quote-resumen__etiqueta">Cliente asignado</span>
                <strong className="live-quote-resumen__cliente-nombre">{c.cliente}</strong>
              </div>
              <InsigniaEstado estado={c.estado} />
            </div>

            {/* Escenario activo: SOLO LECTURA (la selección interactiva vive en la tarjeta del chat) */}
            <div className="live-quote-resumen__escenario-card">
              <div className="live-quote-resumen__escenario-info">
                <span className="live-quote-resumen__etiqueta">Escenario activo</span>
                <strong className="live-quote-resumen__escenario-titulo">
                  {escenarioInfo.etiqueta}
                </strong>
              </div>
              <span className="insignia insignia--neutro">Cálculo vigente</span>
            </div>

            {/* Conteo de partidas con enlace al chat (NO repite la tabla de partidas) */}
            <div className="live-quote-resumen__partidas-resumen">
              <div className="live-quote-resumen__conteo-linea">
                <Icono nombre="cotizaciones" tamano={18} />
                <span className="live-quote-resumen__conteo-texto">
                  <strong>{partidas.length} partidas</strong> en este escenario
                </span>
              </div>
              <button
                type="button"
                className="enlace live-quote-resumen__enlace-detalle"
                onClick={hacerScrollATarjeta}
                title="Desplazarse a la tabla de partidas en el chat"
              >
                Ver detalle en el chat ↓
              </button>
            </div>

            {/* Datos de validación, auditoría y total final */}
            {calculo && (
              <div className="live-quote-resumen__auditoria-card">
                <h3 className="live-quote-resumen__seccion-titulo">Validación determinista</h3>
                <dl className="live-quote-resumen__datos-lista">
                  <div>
                    <dt>Motor</dt>
                    <dd>Regla determinista (LIFO)</dd>
                  </div>
                  <div>
                    <dt>Validación</dt>
                    <dd className="codigo">SHA-256 verificado</dd>
                  </div>
                  <div>
                    <dt>Subtotal neto</dt>
                    <dd className="cifra">{formatoPesos(calculo.subtotal)} <span className="sufijo-moneda">MXN</span></dd>
                  </div>
                  <div>
                    <dt>IVA (16%)</dt>
                    <dd className="cifra">{formatoPesos(calculo.iva)} <span className="sufijo-moneda">MXN</span></dd>
                  </div>
                </dl>
                <div className="live-quote-resumen__gran-total">
                  <span className="live-quote-resumen__gran-total-label">Total a facturar</span>
                  <strong className="cifra live-quote-resumen__gran-total-monto">
                    {formatoPesos(calculo.total)} <span className="sufijo-moneda">MXN</span>
                  </strong>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ACCIONES DE LA COTIZACIÓN: Un solo grupo fijo al pie */}
      {c && (
        <footer className="live-quote-panel__pie-acciones">
          <div className="live-quote-resumen__acciones-grupo">
            {/* Acción Primaria: Abrir revisión completa */}
            <Link
              to={`/cotizaciones/${c.id}`}
              className="boton boton--primario live-quote-resumen__btn-principal"
            >
              <Icono nombre="editar" tamano={16} />
              <span>Abrir revisión completa</span>
            </Link>

            {/* Acción Secundaria: Descargar PDF */}
            <button
              type="button"
              className="boton boton--secundario live-quote-resumen__btn-secundario"
              onClick={descargar}
              title="Descargar cotización en formato PDF formal"
            >
              <Icono nombre="descargar" tamano={16} />
              <span>Descargar PDF</span>
            </button>

            {/* Menú de más acciones '⋯' */}
            <div className="live-quote-resumen__menu-envoltorio" ref={refMenu}>
              <button
                type="button"
                className="boton-icono live-quote-resumen__btn-mas"
                onClick={() => setMenuMasAbierto((m) => !m)}
                aria-expanded={menuMasAbierto}
                aria-haspopup="true"
                title="Más acciones de cotización"
                aria-label="Más acciones de cotización"
              >
                <Icono nombre="puntos" tamano={18} />
              </button>

              {menuMasAbierto && (
                <div className="live-quote-resumen__menu-desplegable" role="menu">
                  {puedeAprobar && c.estado !== 'Aprobada' && (
                    <button
                      type="button"
                      className="live-quote-resumen__menu-item live-quote-resumen__menu-item--aprobar"
                      role="menuitem"
                      onClick={manejarAprobar}
                      disabled={aprobando}
                    >
                      <Icono nombre="check" tamano={16} />
                      <span>{aprobando ? 'Aprobando…' : 'Aprobar cotización'}</span>
                    </button>
                  )}
                  <Link
                    to="/cotizaciones"
                    className="live-quote-resumen__menu-item"
                    role="menuitem"
                    onClick={() => setMenuMasAbierto(false)}
                  >
                    <Icono nombre="cotizaciones" tamano={16} />
                    <span>Ver catálogo de cotizaciones</span>
                  </Link>
                </div>
              )}
            </div>
          </div>
        </footer>
      )}
    </aside>
  );
}
