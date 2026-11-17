import { useState, type FormEvent } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Icono, type NombreIcono } from './Iconos';
import { PanelDerecho, usePanel } from './Panel';
import { Toasts } from './Toasts';
import { useAlmacen } from '../state/Almacen';
import { EMPRESA } from '../data/ejemplo';
import { SelectorTema } from './SelectorTema';

const NAV: { a: string; etiqueta: string; icono: NombreIcono; fin?: boolean }[] = [
  { a: '/', etiqueta: 'Chat', icono: 'chat', fin: true },
  { a: '/cotizaciones', etiqueta: 'Cotizaciones', icono: 'cotizaciones' },
  { a: '/fuentes', etiqueta: 'Fuentes', icono: 'fuentes' },
  { a: '/memoria', etiqueta: 'Memoria', icono: 'memoria' },
  { a: '/bitacora', etiqueta: 'Bitácora', icono: 'bitacora' },
  { a: '/ajustes', etiqueta: 'Ajustes', icono: 'ajustes' },
];

function Topbar() {
  const navegar = useNavigate();
  const { usuario } = useAlmacen();
  const [q, setQ] = useState('');

  const buscar = (e: FormEvent) => {
    e.preventDefault();
    navegar(q.trim() ? `/cotizaciones?q=${encodeURIComponent(q.trim())}` : '/cotizaciones');
  };

  return (
    <header className="topbar">
      <div className="topbar__marca">
        <span className="logo" aria-hidden="true">T</span>
        <span className="topbar__nombre">Tessera</span>
        <span className="topbar__empresa texto-suave">{EMPRESA}</span>
      </div>
      <form className="topbar__busqueda" role="search" onSubmit={buscar}>
        <Icono nombre="buscar" tamano={16} />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar cotizaciones por folio o cliente…"
          aria-label="Búsqueda global"
        />
      </form>
      <div className="topbar__acciones">
        <SelectorTema />
        <div className="usuario" title={usuario.rol}>
          <span className="avatar" aria-hidden="true">{usuario.nombre.split(' ').map((p) => p[0]).join('')}</span>
          <span className="usuario__texto">
            <strong>{usuario.nombre}</strong>
            <span className="texto-suave">{usuario.rol}</span>
          </span>
        </div>
      </div>
    </header>
  );
}

function Sidebar({ colapsada, onAlternar }: { colapsada: boolean; onAlternar: () => void }) {
  return (
    <nav className="sidebar" aria-label="Navegación principal">
      <ul>
        {NAV.map((n) => (
          <li key={n.a}>
            <NavLink to={n.a} end={n.fin} className={({ isActive }) => `sidebar__enlace ${isActive ? 'activo' : ''}`} title={colapsada ? n.etiqueta : undefined}>
              <Icono nombre={n.icono} tamano={20} />
              <span className="sidebar__texto">{n.etiqueta}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <button className="sidebar__colapsar" onClick={onAlternar} aria-label={colapsada ? 'Expandir barra lateral' : 'Colapsar barra lateral'} aria-expanded={!colapsada}>
        <Icono nombre={colapsada ? 'derecha' : 'izquierda'} tamano={18} />
        <span className="sidebar__texto">Colapsar</span>
      </button>
    </nav>
  );
}

function BarraEstado() {
  const { documentos } = useAlmacen();
  const listos = documentos.filter((d) => d.estado === 'Listo').length;
  return (
    <footer className="statusbar">
      <span>Modelo: sin conectar (prototipo)</span>
      <span>Ingesta: {listos} de {documentos.length} documentos listos</span>
      <span>Última latencia: sin medir</span>
    </footer>
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
      <BarraEstado />
      <Toasts />
    </div>
  );
}
