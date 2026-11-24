import { useState, useRef, type FormEvent } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Icono } from './Iconos';
import { PanelDerecho, usePanel } from './Panel';
import { Toasts } from './Toasts';
import { escenarioVigente, useAlmacen } from '../state/Almacen';
import { EMPRESA } from '../data/constantes';
import { SelectorUsuario } from './SelectorUsuario';
import { InsigniaEstado } from './Insignia';
import { formatoFecha, formatoFechaCorta, formatoPesos } from '../lib/dinero';
import { atajoModificador, truncarNombreArchivo } from '../lib/texto';

function IndicadorSalud() {
  const { documentos, ajustes, errorCarga } = useAlmacen();
  const listos = documentos.filter((d) => d.estado === 'Listo').length;
  const saludable = listos > 0 && !errorCarga;
  const modelo = ajustes ? `${ajustes.modo_demo ? 'DEMO · ' : ''}${ajustes.proveedor}: ${ajustes.modelo}` : 'conectando…';
  const latencia = ajustes?.ultima_cotizacion_ms ? `${Math.round(ajustes.ultima_cotizacion_ms.total)} ms` : 'sin cotizar';

  return (
    <div
      className={`indicador-salud ${saludable ? 'indicador-salud--ok' : 'indicador-salud--warn'}`}
      title={`Estado del sistema:
• Fuentes listas: ${listos} de ${documentos.length} documentos
• Motor: ${modelo}
• Latencia de cálculo: ${latencia}`}
      role="status"
      aria-label={`Salud del sistema: ${listos} fuentes listas`}
    >
      <span className="indicador-salud__punto" aria-hidden="true" />
      <span className="indicador-salud__texto">Fuentes: {listos} {listos === 1 ? 'doc.' : 'docs.'}</span>
    </div>
  );
}

function MigasDePan() {
  const location = useLocation();
  const { cotizaciones } = useAlmacen();

  const path = location.pathname;
  let modulo = 'Cotizador';
  let detalle = 'Nueva solicitud';

  if (path === '/') {
    modulo = 'Cotizador';
    detalle = 'En vivo';
  } else if (path.startsWith('/cotizaciones/')) {
    const id = path.replace('/cotizaciones/', '');
    const c = cotizaciones.find((item) => item.id === id);
    modulo = 'Cotizaciones';
    detalle = c ? c.folio : 'Detalle';
  } else if (path === '/cotizaciones') {
    modulo = 'Cotizaciones';
    detalle = 'Emisiones';
  } else if (path === '/fuentes') {
    modulo = 'Fuentes';
    detalle = 'Bases verificadas';
  } else if (path === '/memoria') {
    modulo = 'Administración';
    detalle = 'Memoria de precios';
  } else if (path === '/bitacora') {
    modulo = 'Administración';
    detalle = 'Bitácora de auditoría';
  } else if (path === '/ajustes') {
    modulo = 'Administración';
    detalle = 'Ajustes';
  }

  return (
    <nav className="topbar__migas" aria-label="Ruta actual">
      <span className="topbar__miga-modulo">{modulo}</span>
      <span className="topbar__miga-separador" aria-hidden="true">/</span>
      <span className="topbar__miga-detalle">{detalle}</span>
    </nav>
  );
}

function Topbar() {
  const navegar = useNavigate();
  const [q, setQ] = useState('');
  const inputBusqueda = useRef<HTMLInputElement>(null);

  const buscar = (e: FormEvent) => {
    e.preventDefault();
    navegar(q.trim() ? `/cotizaciones?q=${encodeURIComponent(q.trim())}` : '/cotizaciones');
  };

  return (
    <header className="topbar">
      <div className="topbar__marca">
        <Link to="/" className="topbar__logo-enlace" title="Tessera — Inicio">
          <span className="logo" aria-hidden="true">T</span>
        </Link>
        <div className="topbar__titulos">
          <span className="topbar__nombre">Tessera</span>
          <span className="topbar__empresa texto-suave">{EMPRESA}</span>
        </div>
      </div>

      <MigasDePan />

      <form className="topbar__busqueda" role="search" onSubmit={buscar}>
        <Icono nombre="buscar" tamano={16} />
        <input
          ref={inputBusqueda}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar cotizaciones por folio o cliente…"
          aria-label="Búsqueda global"
        />
        <kbd className="topbar__atajo" title={`Atajo de búsqueda (${atajoModificador('K')})`}>
          {atajoModificador('K')}
        </kbd>
      </form>

      <div className="topbar__acciones">
        <IndicadorSalud />
        <SelectorUsuario />
      </div>
    </header>
  );
}

function Sidebar({ colapsada, onAlternar }: { colapsada: boolean; onAlternar: () => void }) {
  const navegar = useNavigate();
  const location = useLocation();
  const { cotizaciones, documentos, ajustes } = useAlmacen();
  const { abrir: abrirPanel } = usePanel();

  const cotizacionesRecientes = cotizaciones.slice(0, 5);
  const basesRecientes = documentos.slice(0, 4);

  const nuevaSolicitud = () => {
    window.dispatchEvent(new CustomEvent('tessera:nueva-conversacion'));
    if (location.pathname !== '/') {
      navegar('/?nueva=1');
    }
  };

  const verBase = (d: (typeof documentos)[0]) => {
    abrirPanel(
      `Fuente: ${d.nombre}`,
      <div className="detalle" role="region" aria-label={`Detalle de ${d.nombre}`}>
        <h3>{d.nombre}</h3>
        <dl className="lista-datos">
          <dt>Tipo</dt>
          <dd>{d.tipo}</dd>
          <dt>Estado</dt>
          <dd><span className="insignia insignia--ok">{d.estado}</span></dd>
          <dt>Actualizado</dt>
          <dd>{formatoFecha(d.actualizado)}</dd>
          <dt>Permisos</dt>
          <dd>{d.permisos}</dd>
        </dl>
        <div style={{ marginTop: 'var(--e-4)' }}>
          <Link to="/fuentes" className="boton boton--primario boton--chico">
            Gestionar en Fuentes
          </Link>
        </div>
      </div>,
    );
  };

  const motorTexto = ajustes
    ? `${ajustes.proveedor}: ${ajustes.modelo}`
    : 'Motor conectado';

  return (
    <aside className="sidebar" aria-label="Navegación principal">
      {/* Botón primario único: Nueva solicitud con atajo */}
      <div className="sidebar__accion-principal">
        <button
          type="button"
          className="boton boton--primario sidebar__btn-nueva"
          onClick={nuevaSolicitud}
          title={`Crear nueva solicitud de cotización (${atajoModificador('K')} o Alt+N)`}
          aria-label="Nueva solicitud de cotización"
        >
          <Icono nombre="mas" tamano={18} />
          <span className="sidebar__texto">Nueva solicitud</span>
          <kbd className="sidebar__atajo" aria-hidden="true">{atajoModificador('K')}</kbd>
        </button>
      </div>

      <div className="sidebar__grupos">
        {/* SECCIÓN OPERACIÓN */}
        <section className="sidebar__seccion" aria-label="Operación">
          {!colapsada && <h3 className="sidebar__titulo-seccion">Operación</h3>}
          <ul className="sidebar__lista">
            <li>
              <NavLink
                to="/"
                end
                className={({ isActive }) => `sidebar__enlace ${isActive ? 'activo' : ''}`}
                title={colapsada ? 'Cotizador en vivo' : undefined}
              >
                <div className="sidebar__icono-wrap">
                  <Icono nombre="chat" tamano={18} />
                  <span className="sidebar__punto-vivo" title="Cotizador activo" />
                </div>
                <span className="sidebar__texto">Cotizador en vivo</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/cotizaciones"
                className={({ isActive }) => `sidebar__enlace ${isActive ? 'activo' : ''}`}
                title={colapsada ? 'Cotizaciones' : undefined}
              >
                <Icono nombre="cotizaciones" tamano={18} />
                <span className="sidebar__texto">Cotizaciones</span>
                {!colapsada && (
                  <span className="sidebar__contador" title={`${cotizaciones.length} cotizaciones registradas`}>
                    {cotizaciones.length}
                  </span>
                )}
              </NavLink>
            </li>
          </ul>
        </section>

        {/* SECCIÓN RECIENTES */}
        {!colapsada && cotizacionesRecientes.length > 0 && (
          <section className="sidebar__seccion" aria-label="Cotizaciones recientes">
            <div className="sidebar__cabecera-subseccion">
              <h3 className="sidebar__titulo-seccion">Recientes</h3>
              <Link to="/cotizaciones" className="sidebar__enlace-ver-todas" title="Ver todas las cotizaciones">
                Ver todas
              </Link>
            </div>
            <ul className="sidebar__tarjetas-recientes">
              {cotizacionesRecientes.map((c) => {
                const escId = escenarioVigente(c);
                const esc = c.escenarios[escId];
                const totalMonto = esc ? esc.partidas.reduce((acc, p) => acc + p.cantidad * p.precioUnitario, 0) * 1.16 : 0;
                return (
                  <li key={c.id}>
                    <Link
                      to={`/cotizaciones/${c.id}`}
                      className="sidebar__tarjeta-reciente"
                      title={`${c.folio} · ${c.cliente}`}
                    >
                      <div className="sidebar__reciente-top">
                        <strong className="sidebar__reciente-folio codigo">{c.folio}</strong>
                        <InsigniaEstado estado={c.estado} />
                      </div>
                      <span
                        className={`sidebar__reciente-cliente ${c.cliente === 'Cliente por definir' ? 'sidebar__reciente-cliente--indefinido' : ''}`}
                        title={c.cliente}
                      >
                        {c.cliente}
                      </span>
                      <div className="sidebar__reciente-pie">
                        <span className="cifra sidebar__reciente-total">
                          {formatoPesos(totalMonto)} <span className="sufijo-moneda">MXN</span>
                        </span>
                        <time className="sidebar__reciente-fecha texto-suave" dateTime={c.fecha}>
                          {formatoFechaCorta(c.fecha)}
                        </time>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* SECCIÓN BASES VERIFICADAS (FUENTES) */}
        {!colapsada && (
          <section className="sidebar__seccion" aria-label="Bases verificadas">
            <div className="sidebar__cabecera-subseccion">
              <h3 className="sidebar__titulo-seccion">Bases verificadas</h3>
              <Link
                to="/fuentes"
                className="boton-icono sidebar__btn-mas-fuente"
                title="Cargar nuevo catálogo o tarifario"
                aria-label="Cargar nueva fuente en Fuentes"
              >
                <Icono nombre="mas" tamano={14} />
              </Link>
            </div>
            {basesRecientes.length === 0 ? (
              <p className="sidebar__bases-vacias texto-suave">
                Sin bases cargadas.{' '}
                <Link to="/fuentes" className="enlace">Cargar catálogo</Link>
              </p>
            ) : (
              <ul className="sidebar__lista-bases">
                {basesRecientes.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      className="sidebar__item-base"
                      onClick={() => verBase(d)}
                      title={`Abrir ${d.nombre} (${d.estado})`}
                    >
                      <span
                        className={`sidebar__base-punto ${d.estado === 'Listo' ? 'sidebar__base-punto--ok' : 'sidebar__base-punto--warn'}`}
                        aria-hidden="true"
                      />
                      <span className="sidebar__base-nombre" title={d.nombre}>
                        {truncarNombreArchivo(d.nombre, 18)}
                      </span>
                      <span className="sidebar__base-fecha texto-suave">
                        {formatoFechaCorta(d.actualizado)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* SECCIÓN ADMINISTRACIÓN */}
        <section className="sidebar__seccion" aria-label="Administración">
          {!colapsada && <h3 className="sidebar__titulo-seccion">Administración</h3>}
          <ul className="sidebar__lista">
            <li>
              <NavLink
                to="/memoria"
                className={({ isActive }) => `sidebar__enlace ${isActive ? 'activo' : ''}`}
                title={colapsada ? 'Memoria de precios' : undefined}
              >
                <Icono nombre="memoria" tamano={18} />
                <span className="sidebar__texto">Memoria de precios</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/bitacora"
                className={({ isActive }) => `sidebar__enlace ${isActive ? 'activo' : ''}`}
                title={colapsada ? 'Bitácora de auditoría' : undefined}
              >
                <Icono nombre="bitacora" tamano={18} />
                <span className="sidebar__texto">Bitácora de auditoría</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/ajustes"
                className={({ isActive }) => `sidebar__enlace ${isActive ? 'activo' : ''}`}
                title={colapsada ? 'Ajustes' : undefined}
              >
                <Icono nombre="ajustes" tamano={18} />
                <span className="sidebar__texto">Ajustes</span>
              </NavLink>
            </li>
          </ul>
        </section>
      </div>

      {/* PIE DEL SIDEBAR: Motor e Indicador de colapso */}
      <footer className="sidebar__pie">
        {!colapsada && (
          <div
            className="sidebar__motor-info"
            title="Motor de cálculo determinista e inferencia configurado en el sistema"
          >
            <span className="sidebar__motor-etiqueta">Motor</span>
            <span className="sidebar__motor-valor">{motorTexto}</span>
          </div>
        )}
        <button
          type="button"
          className="sidebar__colapsar"
          onClick={onAlternar}
          aria-label={colapsada ? 'Expandir barra lateral' : 'Colapsar barra lateral'}
          aria-expanded={!colapsada}
          title={colapsada ? 'Expandir barra lateral' : 'Colapsar barra lateral'}
        >
          <Icono nombre={colapsada ? 'derecha' : 'izquierda'} tamano={18} />
          {!colapsada && <span className="sidebar__texto">Colapsar</span>}
        </button>
      </footer>
    </aside>
  );
}

export function Layout() {
  const [colapsada, setColapsada] = useState(false);
  const { panel } = usePanel();
  return (
    <div className={`app ${colapsada ? 'app--colapsada' : ''} ${panel ? 'app--con-panel' : ''}`}>
      <a className="saltar" href="#principal">Saltar al contenido</a>
      <Topbar />
      <Sidebar colapsada={colapsada} onAlternar={() => setColapsada((c) => !c)} />
      <main id="principal" className="principal" tabIndex={-1}>
        <Outlet />
      </main>
      <PanelDerecho />
      <Toasts />
    </div>
  );
}
