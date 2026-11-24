import { useState, useEffect, useRef } from 'react';
import { EncabezadoPagina } from '../components/Estados';
import { InsigniaEstado } from '../components/Insignia';
import { usePanel } from '../components/Panel';
import { useAlmacen } from '../state/Almacen';
import { Icono } from '../components/Iconos';
import { fetchApi } from '../lib/api';

interface FuenteAPI {
  id: number;
  nombre: string;
  tipo: string;
  estado: 'Listo' | 'Procesando' | 'Error' | 'Omitido';
  leidas: number;
  guardadas: number;
  rechazadas: number;
  omitidas: number;
  motivo?: string | null;
  fecha_carga: string;
}

interface RechazoAPI {
  id: number;
  fuente_id?: number;
  archivo: string;
  fila_numero?: number;
  campo?: string;
  valor_crudo?: string;
  motivo: string;
  fecha: string;
}

const EXTENSIONES = /\.(csv|xlsx|xls|pdf)$/i;

export default function Fuentes() {
  const { avisar, esAdministrador } = useAlmacen();
  const soloAdmin = 'Solo un Administrador puede cambiar las fuentes (cambia de usuario arriba para probarlo).';
  const { abrir } = usePanel();
  const [fuentes, setFuentes] = useState<FuenteAPI[]>([]);
  const [rechazos, setRechazos] = useState<RechazoAPI[]>([]);
  const [cargando, setCargando] = useState<boolean>(true);
  const [procesandoAccion, setProcesandoAccion] = useState<boolean>(false);
  const [filtroArchivo, setFiltroArchivo] = useState<string>('todos');
  const [seleccionId, setSeleccionId] = useState<number | undefined>();
  const [arrastrando, setArrastrando] = useState(false);
  const [progreso, setProgreso] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Carga inicial y actualización desde la API
  const cargarDatos = async () => {
    try {
      setCargando(true);
      const [resFuentes, resRechazos] = await Promise.all([
        fetchApi('/api/fuentes'),
        fetchApi('/api/fuentes/rechazos'),
      ]);

      if (resFuentes.ok) {
        const dataFuentes: FuenteAPI[] = await resFuentes.json();
        setFuentes(dataFuentes);
      }
      if (resRechazos.ok) {
        const dataRechazos: RechazoAPI[] = await resRechazos.json();
        setRechazos(dataRechazos);
      }
    } catch {
      avisar('No se pudo conectar con el backend local (http://127.0.0.1:8000).', 'error');
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarDatos();
  }, []);

  // Sube uno o varios archivos (CSV, XLSX, PDF), de uno en uno; vale tanto para el botón como para arrastrar y soltar
  const subirArchivos = async (lista: File[]) => {
    if (lista.length === 0 || procesandoAccion) return;
    if (!esAdministrador) {
      avisar(soloAdmin, 'error');
      return;
    }
    const validos = lista.filter((f) => EXTENSIONES.test(f.name));
    const ignorados = lista.filter((f) => !EXTENSIONES.test(f.name));
    if (ignorados.length > 0) {
      avisar(`Se omitió ${ignorados.map((f) => f.name).join(', ')}: solo se admiten CSV, XLSX y PDF.`, 'error');
    }
    if (validos.length === 0) return;

    setProcesandoAccion(true);
    let exitoTotal = 0;

    for (let i = 0; i < validos.length; i++) {
      const archivo = validos[i];
      setProgreso(`Procesando ${i + 1} de ${validos.length}: ${archivo.name}`);

      try {
        const formData = new FormData();
        formData.append('file', archivo);

        const res = await fetchApi('/api/fuentes/subir', { method: 'POST', body: formData });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Error al procesar ${archivo.name}`);
        }

        exitoTotal++;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : `Error al subir ${archivo.name}`;
        avisar(msg, 'error');
      }
    }

    setProgreso(null);
    if (exitoTotal > 0) {
      avisar(`Ingesta completada: ${exitoTotal} de ${validos.length} archivo(s) procesados.`, exitoTotal === validos.length ? 'ok' : 'info');
      await cargarDatos();
    }

    setProcesandoAccion(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const manejarSubida = (e: React.ChangeEvent<HTMLInputElement>) => {
    const lista = Array.from(e.target.files ?? []);
    e.target.value = ''; // permite volver a elegir los mismos archivos
    void subirArchivos(lista);
  };

  const alSoltar = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    void subirArchivos(Array.from(e.dataTransfer.files));
  };

  const puedeSubir = esAdministrador && !procesandoAccion;

  // Vaciar la base de datos de ingesta para iniciar la demostración en limpio
  const vaciarBase = async () => {
    if (!window.confirm('¿Deseas vaciar todas las fuentes de la base de datos para iniciar la demostración en limpio?')) return;
    setProcesandoAccion(true);
    try {
      const res = await fetchApi('/api/fuentes/limpiar', { method: 'POST' });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Error al vaciar la base de datos');
      const data = await res.json();
      avisar(data.mensaje, 'ok');
      await cargarDatos();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al vaciar la base de datos';
      avisar(msg, 'error');
    } finally {
      setProcesandoAccion(false);
    }
  };

  // Carga del dataset sintético completo (12 archivos) para demostración del Hito 1
  const cargarDatasetCompleto = async () => {
    setProcesandoAccion(true);
    avisar('Cargando dataset sintético completo (CSV, XLSX y 10 PDFs)...', 'info');
    try {
      const res = await fetchApi('/api/fuentes/cargar-dataset-sintetico', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al cargar dataset');
      }
      const data = await res.json();
      avisar(data.mensaje, 'ok');
      await cargarDatos();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al conectar con la API';
      avisar(msg, 'error');
    } finally {
      setProcesandoAccion(false);
    }
  };

  // Inspección de detalles en el panel lateral
  const verDetalleFuente = (f: FuenteAPI) => {
    setSeleccionId(f.id);
    const rechazosDeEstaFuente = rechazos.filter((r) => r.archivo === f.nombre);
    abrir(
      `Fuente: ${f.nombre}`,
      <div className="detalle">
        <h3>{f.nombre}</h3>
        <dl className="lista-datos">
          <dt>Tipo</dt>
          <dd>{f.tipo}</dd>
          <dt>Estado</dt>
          <dd><InsigniaEstado estado={f.estado} /></dd>
          <dt>Fecha de carga</dt>
          <dd>{f.fecha_carga}</dd>
          <dt>Filas leídas</dt>
          <dd><strong>{f.leidas}</strong></dd>
          <dt>Filas guardadas en SQLite</dt>
          <dd><span style={{ color: 'var(--ok)', fontWeight: 600 }}>{f.guardadas}</span></dd>
          <dt>Filas rechazadas</dt>
          <dd><span style={{ color: f.rechazadas > 0 ? 'var(--error)' : 'inherit', fontWeight: 600 }}>{f.rechazadas}</span></dd>
        </dl>

        {f.motivo && (
          <div className="aviso-parcial aviso-parcial--error" role="note" style={{ marginTop: 'var(--e-3)' }}>
            <Icono nombre="alerta" tamano={16} />
            <div>
              <strong>Diagnóstico</strong>
              <p>{f.motivo}</p>
            </div>
          </div>
        )}

        <h4 style={{ marginTop: 'var(--e-4)' }}>Inconsistencias detectadas ({rechazosDeEstaFuente.length})</h4>
        {rechazosDeEstaFuente.length === 0 ? (
          <p className="texto-suave">No se registraron rechazos para este archivo.</p>
        ) : (
          <ul className="lista-simple">
            {rechazosDeEstaFuente.map((r) => (
              <li key={r.id}>
                <strong>Fila {r.fila_numero ?? 'N/D'} · Campo: {r.campo ?? 'General'}</strong>
                <br />
                <span style={{ color: 'var(--error)' }}>Motivo: {r.motivo}</span>
                {r.valor_crudo && (
                  <div className="texto-suave" style={{ fontSize: 'var(--t-12)', fontFamily: 'monospace' }}>
                    Valor recibido: "{r.valor_crudo}"
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  // Cálculo de totales agregados
  const totalLeidas = fuentes.reduce((acc, f) => acc + f.leidas, 0);
  const totalGuardadas = fuentes.reduce((acc, f) => acc + f.guardadas, 0);
  const totalRechazadas = fuentes.reduce((acc, f) => acc + f.rechazadas, 0);

  const rechazosFiltrados = filtroArchivo === 'todos'
    ? rechazos
    : rechazos.filter((r) => r.archivo === filtroArchivo);

  const archivosUnicos = Array.from(new Set(rechazos.map((r) => r.archivo)));

  return (
    // soltar un archivo fuera de la zona no debe hacer que el navegador lo abra y se pierda la pantalla
    <div className="pagina" onDragOver={(e) => e.preventDefault()} onDrop={(e) => e.preventDefault()}>
      <input
        type="file"
        ref={fileInputRef}
        onChange={manejarSubida}
        accept=".csv,.xlsx,.xls,.pdf"
        multiple
        style={{ display: 'none' }}
      />

      <EncabezadoPagina
        titulo="Fuentes"
        descripcion="Lo que el sistema conoce: ingesta estructurada de catálogo CSV, historial XLSX y fichas técnicas PDF en SQLite local."
        acciones={
          <div style={{ display: 'flex', gap: 'var(--e-2)', flexWrap: 'wrap' }}>
            <button
              className="boton boton--primario"
              onClick={() => fileInputRef.current?.click()}
              disabled={procesandoAccion || !esAdministrador}
              title={esAdministrador ? undefined : soloAdmin}
            >
              <Icono nombre="check" tamano={14} /> Subir archivo (CSV, XLSX, PDF)
            </button>
            <button
              className="boton"
              onClick={cargarDatasetCompleto}
              disabled={procesandoAccion || !esAdministrador}
              title={esAdministrador ? 'Carga en lote el dataset sintético (catálogo, tarifario de servicios, historial y 10 PDFs)' : soloAdmin}
            >
              Cargar dataset sintético
            </button>
            <button
              className="boton boton--peligro-suave"
              onClick={vaciarBase}
              disabled={procesandoAccion || !esAdministrador}
              title={esAdministrador ? 'Vacía todas las fuentes y rechazos para reiniciar la demostración en limpio' : soloAdmin}
            >
              Vaciar base
            </button>
            <button
              className="boton boton--chico"
              onClick={cargarDatos}
              disabled={cargando || procesandoAccion}
              title="Actualizar datos desde SQLite"
            >
              Actualizar
            </button>
          </div>
        }
      />

      {!esAdministrador && (
        <p className="resumen" role="note">
          Los botones de carga están desactivados: solo el Administrador puede cambiar las fuentes. Elige a <strong>Laura Canché</strong> en el selector de usuario de la barra superior.
        </p>
      )}

      <div
        className={`zona-carga${arrastrando && puedeSubir ? ' zona-carga--activa' : ''}${esAdministrador ? '' : ' zona-carga--bloqueada'}`}
        role="button"
        tabIndex={puedeSubir ? 0 : -1}
        aria-disabled={!puedeSubir}
        aria-label="Zona de carga: arrastra archivos aquí o pulsa para elegirlos"
        onClick={() => puedeSubir && fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (puedeSubir && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastrando(false);
        }}
        onDrop={alSoltar}
      >
        {progreso ? (
          <span className="zona-carga__progreso" role="status">{progreso}</span>
        ) : (
          <>
            <strong>{arrastrando && puedeSubir ? 'Suéltalos para subirlos' : 'Arrastra aquí uno o varios archivos'}</strong>
            <span>o pulsa para elegirlos · CSV, XLSX o PDF · se procesan de uno en uno</span>
          </>
        )}
      </div>

      {/* Resumen estadístico */}
      <p className="resumen" role="status">
        <strong>{fuentes.length} fuentes cargadas</strong> · {totalLeidas} filas leídas en total ·{' '}
        <span style={{ color: 'var(--ok)', fontWeight: 600 }}>{totalGuardadas} guardadas en SQLite</span> ·{' '}
        <span style={{ color: totalRechazadas > 0 ? 'var(--error)' : 'inherit', fontWeight: 600 }}>
          {totalRechazadas} rechazadas con motivo
        </span>
      </p>

      {/* Tabla de archivos / fuentes */}
      <div className="tabla-contenedor">
        <table className="tabla tabla--filas">
          <caption className="solo-lectores">Documentos y su estado de ingesta.</caption>
          <thead>
            <tr>
              <th scope="col">Archivo</th>
              <th scope="col">Tipo</th>
              <th scope="col" style={{ textAlign: 'right' }}>Leídas</th>
              <th scope="col" style={{ textAlign: 'right' }}>Guardadas</th>
              <th scope="col" style={{ textAlign: 'right' }}>Rechazadas</th>
              <th scope="col">Estado</th>
              <th scope="col">Fecha de carga</th>
              <th scope="col">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {fuentes.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: 'var(--e-5)', color: 'var(--muted)' }}>
                  {cargando ? 'Consultando SQLite...' : 'Aún no se han cargado fuentes. Haz clic en "Subir archivo" o "Cargar dataset sintético".'}
                </td>
              </tr>
            ) : (
              fuentes.map((f) => (
                <tr
                  key={f.id}
                  className={seleccionId === f.id ? 'fila-activa' : ''}
                  onClick={() => verDetalleFuente(f)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <button
                      className="enlace-boton"
                      onClick={(e) => {
                        e.stopPropagation();
                        verDetalleFuente(f);
                      }}
                    >
                      {f.nombre}
                    </button>
                  </td>
                  <td><span className="etiqueta">{f.tipo}</span></td>
                  <td style={{ textAlign: 'right' }}>{f.leidas}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--ok)' }}>{f.guardadas}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600, color: f.rechazadas > 0 ? 'var(--error)' : 'inherit' }}>
                    {f.rechazadas}
                  </td>
                  <td><InsigniaEstado estado={f.estado} /></td>
                  <td style={{ fontSize: 'var(--t-12)', color: 'var(--muted)' }}>{f.fecha_carga}</td>
                  <td>
                    <button
                      className="boton boton--chico"
                      onClick={(e) => {
                        e.stopPropagation();
                        verDetalleFuente(f);
                      }}
                    >
                      {f.rechazadas > 0 ? 'Ver rechazos' : 'Ver detalle'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Sección de Rechazos por Inconsistencias */}
      {rechazos.length > 0 && (
        <div style={{ marginTop: 'var(--e-5)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--e-2)' }}>
            <div>
              <h3 style={{ margin: 0 }}>Rechazos por Inconsistencias ({rechazosFiltrados.length})</h3>
              <p className="texto-suave" style={{ margin: 'var(--e-1) 0 0' }}>
                Filas defectuosas detectadas automáticamente y descartadas de SQLite con motivo legible.
              </p>
            </div>
            {archivosUnicos.length > 1 && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--e-2)', fontSize: 'var(--t-12)' }}>
                <span>Filtrar por archivo:</span>
                <select
                  value={filtroArchivo}
                  onChange={(e) => setFiltroArchivo(e.target.value)}
                  className="entrada"
                  style={{ minHeight: '30px', padding: '2px 8px' }}
                >
                  <option value="todos">Todos los archivos ({rechazos.length})</option>
                  {archivosUnicos.map((arch) => (
                    <option key={arch} value={arch}>{arch}</option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div className="tabla-contenedor">
            <table className="tabla tabla--filas">
              <thead>
                <tr>
                  <th scope="col">Archivo</th>
                  <th scope="col" style={{ width: '80px' }}>Fila</th>
                  <th scope="col">Campo</th>
                  <th scope="col">Valor Detectado</th>
                  <th scope="col">Motivo del Rechazo</th>
                  <th scope="col">Fecha Detección</th>
                </tr>
              </thead>
              <tbody>
                {rechazosFiltrados.map((r) => (
                  <tr key={r.id}>
                    <td><strong>{r.archivo}</strong></td>
                    <td>{r.fila_numero ?? 'N/D'}</td>
                    <td><code>{r.campo ?? 'General'}</code></td>
                    <td>
                      <code style={{ color: 'var(--muted)', background: 'var(--surface-2)', padding: '2px 6px', borderRadius: '4px' }}>
                        {r.valor_crudo === '' ? '(vacío)' : r.valor_crudo}
                      </code>
                    </td>
                    <td>
                      <span className="insignia insignia--error" style={{ fontSize: 'var(--t-12)' }}>
                        <Icono nombre="alerta" tamano={12} /> {r.motivo}
                      </span>
                    </td>
                    <td style={{ fontSize: 'var(--t-12)', color: 'var(--muted)' }}>{r.fecha}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
