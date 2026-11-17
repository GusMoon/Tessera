import { Icono } from './Iconos';
import { AvisoAntiguedad, EtiquetaPermiso, InsigniaEstado } from './Insignia';
import { useAlmacen } from '../state/Almacen';
import { formatoFecha } from '../lib/dinero';
import type { Documento } from '../data/tipos';

/** Chip de cita: abre la fuente en el panel derecho (doc UI §6). */
export function ChipFuente({
  citaId,
  numero,
  activo,
  onAbrir,
}: {
  citaId: string;
  numero?: number;
  activo?: boolean;
  onAbrir: (citaId: string) => void;
}) {
  const { citaPorId } = useAlmacen();
  const cita = citaPorId(citaId);
  if (!cita) return <span className="texto-suave">Sin fuente</span>;
  return (
    <button
      className={`chip ${activo ? 'chip--activo' : ''}`}
      onClick={() => onAbrir(citaId)}
      aria-label={`Abrir fuente ${cita.etiqueta}`}
    >
      {numero !== undefined && <span className="chip__numero">{numero}</span>}
      {cita.etiqueta}
    </button>
  );
}

/** ¿Puede el usuario actual abrir el documento? (regla 6: permisos antes de recuperar). */
export function useAccesoDocumento() {
  const { usuario } = useAlmacen();
  return (d: Documento) => d.permisos !== 'Administración' || usuario.rol === 'Administrador';
}

function AvisoRestringido({ permiso }: { permiso: string }) {
  return (
    <div className="aviso-parcial" role="note">
      <Icono nombre="candado" tamano={16} />
      <div>
        <strong>Sin permiso para abrir este documento.</strong>
        <p>Requiere acceso de {permiso}. Se muestra solo lo disponible y el agente no lo usa en tus respuestas.</p>
      </div>
    </div>
  );
}

export function DetalleCita({ citaId }: { citaId: string }) {
  const { citaPorId, documentoPorId } = useAlmacen();
  const puede = useAccesoDocumento();
  const cita = citaPorId(citaId);
  const doc = cita ? documentoPorId(cita.documentoId) : undefined;
  if (!cita || !doc) return <p>Fuente no encontrada.</p>;
  return (
    <div className="detalle">
      <h3>{cita.etiqueta}</h3>
      <dl className="lista-datos">
        <dt>Documento</dt>
        <dd>{doc.nombre}</dd>
        <dt>Ubicación</dt>
        <dd>{cita.ubicacion}</dd>
        <dt>Fecha del dato</dt>
        <dd>
          {formatoFecha(cita.fecha)} · <AvisoAntiguedad fecha={cita.fecha} />
        </dd>
        <dt>Estado</dt>
        <dd>
          <InsigniaEstado estado={doc.estado} />
        </dd>
        <dt>Permisos</dt>
        <dd>
          <EtiquetaPermiso permiso={doc.permisos} />
        </dd>
      </dl>
      {puede(doc) ? (
        <blockquote className="extracto">{cita.extracto}</blockquote>
      ) : (
        <AvisoRestringido permiso={doc.permisos} />
      )}
    </div>
  );
}

export function DetalleDocumento({ documento }: { documento: Documento }) {
  const { citas } = useAlmacen();
  const puede = useAccesoDocumento();
  const fragmentos = citas.filter((c) => c.documentoId === documento.id);
  return (
    <div className="detalle">
      <h3>{documento.nombre}</h3>
      <dl className="lista-datos">
        <dt>Tipo</dt>
        <dd>{documento.tipo}</dd>
        <dt>Actualizado</dt>
        <dd>{formatoFecha(documento.actualizado)}</dd>
        <dt>Estado</dt>
        <dd>
          <InsigniaEstado estado={documento.estado} />
        </dd>
        <dt>Permisos</dt>
        <dd>
          <EtiquetaPermiso permiso={documento.permisos} />
        </dd>
      </dl>
      {documento.motivo && (
        <div className="aviso-parcial aviso-parcial--error" role="note">
          <Icono nombre="alerta" tamano={16} />
          <div>
            <strong>Motivo</strong>
            <p>{documento.motivo}</p>
          </div>
        </div>
      )}
      {!puede(documento) ? (
        <AvisoRestringido permiso={documento.permisos} />
      ) : (
        <>
          <h4>Fragmentos citados</h4>
          {fragmentos.length === 0 ? (
            <p className="texto-suave">Aún no hay fragmentos de este documento en cotizaciones.</p>
          ) : (
            <ul className="lista-simple">
              {fragmentos.map((f) => (
                <li key={f.id}>
                  <strong>{f.etiqueta}</strong> · {f.ubicacion}
                  <br />
                  <span className="texto-suave">{f.extracto}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
