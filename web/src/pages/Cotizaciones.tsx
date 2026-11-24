import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { totalDe } from '../components/Cotizacion';
import { ContenidoConEstados, EncabezadoPagina, EstadoVacio } from '../components/Estados';
import { InsigniaEstado } from '../components/Insignia';
import { usePanel } from '../components/Panel';
import { ChipFecha } from '../components/Traza';
import { escenarioVigente, useAlmacen } from '../state/Almacen';
import type { Cotizacion, EstadoCotizacion } from '../data/tipos';
import { ESCENARIOS } from '../data/tipos';
import { formatoFecha, formatoMXN } from '../lib/dinero';
import { useEstadoPantalla } from '../lib/useEstadoPantalla';

const ESTADOS: EstadoCotizacion[] = ['Borrador', 'En revisión', 'Aprobada', 'Rechazada'];

function VistaRapida({ c }: { c: Cotizacion }) {
  const id = escenarioVigente(c);
  return (
    <div className="detalle">
      <h3>{c.folio} · {c.cliente}</h3>
      <dl className="lista-datos">
        <dt>Estado</dt><dd><InsigniaEstado estado={c.estado} /></dd>
        <dt>Fecha</dt><dd>{formatoFecha(c.fecha)}</dd>
        <dt>Creada por</dt><dd>{c.creadaPor}</dd>
        <dt>Escenario</dt><dd>{ESCENARIOS.find((e) => e.id === id)?.etiqueta}</dd>
        <dt>Partidas</dt><dd>{c.escenarios[id].partidas.length}</dd>
        <dt>Total</dt><dd className="cifra">{formatoMXN(totalDe(c))}</dd>
      </dl>
      <Link className="boton boton--primario" to={`/cotizaciones/${c.id}`}>Abrir revisión</Link>
    </div>
  );
}

export default function Cotizaciones() {
  const { cotizaciones } = useAlmacen();
  const { abrir } = usePanel();
  const { estado, reintentar, error } = useEstadoPantalla();
  const [params] = useSearchParams();
  const [texto, setTexto] = useState(params.get('q') ?? '');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [cliente, setCliente] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [seleccion, setSeleccion] = useState<string | undefined>();

  const clientes = useMemo(() => [...new Set(cotizaciones.map((c) => c.cliente))].sort(), [cotizaciones]);

  const filtradas = useMemo(() => {
    const t = texto.trim().toLowerCase();
    return cotizaciones
      .filter((c) => !t || c.folio.toLowerCase().includes(t) || c.cliente.toLowerCase().includes(t))
      .filter((c) => !filtroEstado || c.estado === filtroEstado)
      .filter((c) => !cliente || c.cliente === cliente)
      .filter((c) => !desde || c.fecha >= desde)
      .filter((c) => !hasta || c.fecha <= hasta)
      .sort((x, y) => (x.fecha < y.fecha ? 1 : x.fecha > y.fecha ? -1 : y.id.localeCompare(x.id)));
  }, [cotizaciones, texto, filtroEstado, cliente, desde, hasta]);

  const limpiar = () => { setTexto(''); setFiltroEstado(''); setCliente(''); setDesde(''); setHasta(''); };
  const hayFiltros = texto || filtroEstado || cliente || desde || hasta;

  const seleccionar = (c: Cotizacion) => {
    setSeleccion(c.id);
    abrir('Vista rápida', <VistaRapida c={c} />);
  };

  return (
    <div className="pagina">
      <EncabezadoPagina titulo="Cotizaciones" descripcion="Historial de cotizaciones, de la más reciente a la más antigua." />
      <ContenidoConEstados
        estado={estado}
        reintentar={reintentar}
        mensajeError={error}
        vacio={{ titulo: 'Aún no hay cotizaciones', texto: 'Pide la primera en el chat.', accion: { etiqueta: 'Ir al chat', a: '/' } }}
      >
        <form onSubmit={(e) => e.preventDefault()} role="search" aria-label="Filtros de cotizaciones">
          <div className="filtros">
            <label className="filtros__principal">Buscar<input className="entrada" type="search" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Folio o cliente" /></label>
            <label>Estado
              <select className="entrada" value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
                <option value="">Todos</option>
                {ESTADOS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
            {hayFiltros && <button type="button" className="boton" onClick={limpiar}>Limpiar filtros</button>}
          </div>
          <details className="mas-filtros" open={Boolean(cliente || desde || hasta)}>
            <summary>Más filtros: cliente y fechas</summary>
            <div className="filtros">
              <label>Cliente
                <select className="entrada" value={cliente} onChange={(e) => setCliente(e.target.value)}>
                  <option value="">Todos</option>
                  {clientes.map((c) => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label>Desde<input className="entrada" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
              <label>Hasta<input className="entrada" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
            </div>
          </details>
        </form>

        {filtradas.length === 0 ? (
          <EstadoVacio titulo="Ningún resultado" texto="Ninguna cotización coincide con los filtros." accion={undefined} />
        ) : (
          <div className="tabla-contenedor">
            <table className="tabla tabla--filas">
              <caption className="solo-lectores">Lista de cotizaciones. Totales en pesos mexicanos.</caption>
              <thead>
                <tr>
                  <th scope="col">Folio</th><th scope="col">Cliente</th><th scope="col">Fecha</th>
                  <th scope="col" className="derecha">Total (MXN)</th><th scope="col">Estado</th><th scope="col">Creada por</th>
                </tr>
              </thead>
              <tbody>
                {filtradas.map((c) => (
                  <tr key={c.id} className={seleccion === c.id ? 'fila-activa' : ''} onClick={() => seleccionar(c)}>
                    <td><Link to={`/cotizaciones/${c.id}`} onClick={(e) => e.stopPropagation()}>{c.folio}</Link></td>
                    <td>
                      <button className="enlace-boton" onClick={(e) => { e.stopPropagation(); seleccionar(c); }}>{c.cliente}</button>
                    </td>
                    <td><ChipFecha fecha={c.fecha} /></td>
                    <td className="derecha cifra">{formatoMXN(totalDe(c))}</td>
                    <td><InsigniaEstado estado={c.estado} /></td>
                    <td className="nowrap">{c.creadaPor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="texto-suave nota-calculo">El total mostrado es el del escenario aprobado o, si aún no hay, el Recomendado.</p>
      </ContenidoConEstados>
    </div>
  );
}
