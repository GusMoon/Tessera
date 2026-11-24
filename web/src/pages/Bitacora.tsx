import { useEffect, useMemo, useState } from 'react';
import { ContenidoConEstados, EncabezadoPagina, EstadoVacio } from '../components/Estados';
import { Icono } from '../components/Iconos';
import { MedidorUso } from '../components/MedidorUso';
import { obtenerUsoChat, type UsoChat } from '../lib/api';
import { useAlmacen } from '../state/Almacen';
import type { EntradaBitacora } from '../data/tipos';
import { formatoFecha, formatoFechaHora, textoRelativo } from '../lib/dinero';
import { useEstadoPantalla } from '../lib/useEstadoPantalla';

const duracion = (ms: number) => (ms === 0 ? '—' : `${(ms / 1000).toFixed(1)} s`);

function aCSV(filas: EntradaBitacora[]): string {
  const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const cab = ['Fecha', 'Usuario', 'Pregunta', 'Documentos', 'Herramientas', 'Duración (s)', 'Cotización', 'Aprobó'];
  const cuerpo = filas.map((f) =>
    [formatoFechaHora(f.fecha), f.usuario, f.pregunta, f.documentos.join('; '), f.herramientas.join('; '), (f.duracionMs / 1000).toFixed(1), f.cotizacion ?? '', f.aprobadoPor ?? ''].map(esc).join(','),
  );
  return '﻿' + [cab.map(esc).join(','), ...cuerpo].join('\r\n');
}

export default function Bitacora() {
  const { bitacora, avisar, usuario: usuarioActivo } = useAlmacen();
  const { estado, reintentar, error } = useEstadoPantalla();
  const [usuario, setUsuario] = useState('');
  const [cotizacion, setCotizacion] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [uso, setUso] = useState<UsoChat | null>(null);
  const [errorUso, setErrorUso] = useState<string | null>(null);

  useEffect(() => {
    obtenerUsoChat().then(setUso).catch((e: Error) => setErrorUso(e.message));
  }, []);

  const usuarios = useMemo(() => [...new Set(bitacora.map((b) => b.usuario))], [bitacora]);
  const filtradas = bitacora
    .filter((b) => !usuario || b.usuario === usuario)
    .filter((b) => !cotizacion || (b.cotizacion ?? '').toLowerCase().includes(cotizacion.trim().toLowerCase()))
    .filter((b) => !desde || b.fecha.slice(0, 10) >= desde)
    .filter((b) => !hasta || b.fecha.slice(0, 10) <= hasta)
    .sort((x, y) => (x.fecha < y.fecha ? 1 : -1));

  // Agrupa por día para leer la bitácora como una línea de tiempo
  const dias = useMemo(() => {
    const mapa = new Map<string, EntradaBitacora[]>();
    for (const f of filtradas) {
      const dia = f.fecha.slice(0, 10);
      mapa.set(dia, [...(mapa.get(dia) ?? []), f]);
    }
    return [...mapa.entries()];
  }, [filtradas]);

  const exportar = () => {
    const url = URL.createObjectURL(new Blob([aCSV(filtradas)], { type: 'text/csv;charset=utf-8' }));
    const enlace = Object.assign(document.createElement('a'), { href: url, download: 'bitacora-tessera.csv' });
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    URL.revokeObjectURL(url);
    avisar(`Exportadas ${filtradas.length} entradas a CSV.`);
  };

  return (
    <div className="pagina">
      <EncabezadoPagina
        titulo="Bitácora"
        descripcion={usuarioActivo.rol === 'Vendedor' ? 'Registro de solo lectura de tus consultas: qué se preguntó, qué se recuperó y qué herramientas se usaron. Como Vendedor solo ves lo tuyo.' : 'Registro de solo lectura: qué se preguntó, qué se recuperó, qué herramientas se usaron y quién aprobó.'}
        acciones={
          <div className="acciones">
            <MedidorUso uso={uso} error={errorUso} />
            <button className="boton" onClick={exportar} disabled={filtradas.length === 0}>
              <Icono nombre="descargar" tamano={16} /> Exportar CSV
            </button>
          </div>
        }
      />
      <ContenidoConEstados
        estado={estado}
        reintentar={reintentar}
        mensajeError={error}
        vacio={{ titulo: 'La bitácora está vacía', texto: 'Cada consulta y aprobación quedará registrada aquí.' }}
      >
        <form className="filtros" onSubmit={(e) => e.preventDefault()} aria-label="Filtros de la bitácora">
          <label>Usuario
            <select className="entrada" value={usuario} onChange={(e) => setUsuario(e.target.value)}>
              <option value="">Todos</option>
              {usuarios.map((u) => <option key={u}>{u}</option>)}
            </select>
          </label>
          <label>Cotización<input className="entrada" value={cotizacion} onChange={(e) => setCotizacion(e.target.value)} placeholder="#0123" /></label>
          <label>Desde<input className="entrada" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
          <label>Hasta<input className="entrada" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        </form>
        {filtradas.length === 0 ? (
          <EstadoVacio titulo="Ningún resultado" texto="Ninguna entrada coincide con los filtros." />
        ) : (
          <div className="hechos-tiempo">
            {dias.map(([dia, entradas]) => (
              <section key={dia} className="dia" aria-label={`Actividad del ${formatoFecha(dia)}`}>
                <h2>
                  <span className="cifra">{formatoFecha(dia)}</span>
                  <span className="texto-suave subtitulo-chico">{textoRelativo(dia)}</span>
                </h2>
                <ol className="linea-tiempo">
                  {entradas.map((b) => (
                    <li key={b.id} className="linea-tiempo__item">
                      <span className="linea-tiempo__fecha cifra">{b.fecha.slice(11, 16)} · {b.usuario}</span>
                      <div className="registro">
                        <p className="registro__pregunta">{b.pregunta}</p>
                        <div className="registro__meta">
                          <span>Documentos: {b.documentos.length ? b.documentos.join(', ') : 'ninguno'}</span>
                          <span>{b.herramientas.map((h) => <code key={h} className="codigo">{h}</code>)}</span>
                          <span className="cifra">Duración: {duracion(b.duracionMs)}</span>
                          {b.cotizacion && <span>Cotización {b.cotizacion}</span>}
                          {b.aprobadoPor && <span>Aprobó {b.aprobadoPor}</span>}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            ))}
          </div>
        )}
        <p className="texto-suave nota-calculo">La duración es lo que midió el servidor al recuperar y calcular; las aprobaciones y descargas de PDF no miden tiempo (—). La latencia con 50 casos se mide con eval/evaluar.py.</p>
      </ContenidoConEstados>
    </div>
  );
}
