import { useState } from 'react';
import { DialogoConfirmacion } from '../components/Dialogo';
import { EncabezadoPagina } from '../components/Estados';
import { useAlmacen } from '../state/Almacen';
import { formatoFecha, formatoMXN } from '../lib/dinero';
import { useTema, type Tema } from '../lib/tema';

// Vistas previas con colores fijos de cada modo (no dependen del tema activo)
const PREVIAS: Record<Exclude<Tema, 'sistema'>, { fondo: string; lado: string; texto: string }> = {
  claro: { fondo: '#edf0f1', lado: '#fbfcfc', texto: '#1a6f81' },
  oscuro: { fondo: '#0e1520', lado: '#151e2b', texto: '#5cc0d4' },
};

const TEMAS: { id: Tema; etiqueta: string; ayuda: string }[] = [
  { id: 'claro', etiqueta: 'Claro', ayuda: 'Fondo cal, ideal con luz de día.' },
  { id: 'sistema', etiqueta: 'Seguir al sistema', ayuda: 'Cambia solo según tu equipo.' },
  { id: 'oscuro', etiqueta: 'Oscuro', ayuda: 'Menos brillo en ambientes con poca luz.' },
];

function Vista({ id }: { id: Tema }) {
  if (id === 'sistema') {
    return (
      <span
        className="tarjeta-tema__vista"
        aria-hidden="true"
        style={{ background: `linear-gradient(115deg, ${PREVIAS.claro.fondo} 50%, ${PREVIAS.oscuro.fondo} 50%)` }}
      >
        <i style={{ background: PREVIAS.claro.lado }} />
        <i style={{ background: PREVIAS.oscuro.lado }} />
      </span>
    );
  }
  const p = PREVIAS[id];
  return (
    <span className="tarjeta-tema__vista" aria-hidden="true" style={{ background: p.fondo }}>
      <i style={{ background: p.lado }} />
      <i style={{ background: p.lado, borderTop: `3px solid ${p.texto}` }} />
    </span>
  );
}

export default function Ajustes() {
  const { usuarios, usuario, ajustes, esAdministrador, borrarDatos } = useAlmacen();
  const [tema, fijarTema] = useTema();
  const [confirmando, setConfirmando] = useState(false);
  const ev = ajustes?.evaluacion;

  return (
    <div className="pagina">
      <EncabezadoPagina titulo="Ajustes" />

      <section className="seccion" aria-labelledby="aj-usuarios">
        <h2 id="aj-usuarios">Usuarios y roles</h2>
        <p className="aviso-parcial" role="note">
          <span>
            <strong>Prototipo.</strong> Elegir un usuario arriba no es iniciar sesión: no hay contraseñas, solo prueba los permisos. La matriz de roles es una propuesta que debe validar la Persona E.
          </span>
        </p>
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead><tr><th scope="col">Nombre</th><th scope="col">Rol</th><th scope="col">Puede</th></tr></thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id} className={u.id === usuario.id ? 'fila-activa' : ''}>
                  <td>{u.nombre}{u.id === usuario.id && <span className="texto-suave"> (activo)</span>}</td>
                  <td>{u.rol}</td>
                  <td>
                    {u.rol === 'Vendedor' && 'Crear y editar cotizaciones, proponer hechos de memoria, ver su bitácora.'}
                    {u.rol === 'Responsable comercial' && 'Lo del Vendedor, además de aprobar, rechazar y gestionar la memoria; ve toda la bitácora.'}
                    {u.rol === 'Administrador' && 'Lo del Responsable comercial, además de cargar o vaciar fuentes y borrar los datos de trabajo.'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="seccion" aria-labelledby="aj-modelo">
        <h2 id="aj-modelo">Modelo activo</h2>
        <p className="texto-suave">Solo lectura en el MVP. Las cifras salen de la última corrida; no son una promesa.</p>
        {ajustes ? (
          <dl className="lista-datos">
            <dt>Modelo de conversación</dt><dd>{ajustes.proveedor} · {ajustes.modelo}</dd>
            <dt>Modo demostración</dt><dd>{ajustes.modo_demo ? 'Activo: las notas de las cotizaciones son respuestas precargadas' : 'Apagado'}</dd>
            <dt>Búsqueda</dt><dd>{ajustes.embedder === 'hash' ? 'Embedder de respaldo (hash)' : 'multilingual-e5-small'} · {ajustes.fragmentos_indexados} fragmentos indexados</dd>
            <dt>Última cotización</dt>
            <dd>{ajustes.ultima_cotizacion_ms ? <span className="cifra">{Math.round(ajustes.ultima_cotizacion_ms.total)} ms (interpretar {Math.round(ajustes.ultima_cotizacion_ms.interpretar)} · historial {Math.round(ajustes.ultima_cotizacion_ms.historial)} · cálculo {Math.round(ajustes.ultima_cotizacion_ms.calculo)})</span> : 'Aún no se ha cotizado desde que arrancó el servidor'}</dd>
            <dt>Evaluación de 50 casos</dt>
            <dd>
              {ev
                ? <span className="cifra">{ev.fecha}: mediana {Math.round(ev.mediana_ms)} ms, p95 {Math.round(ev.p95_ms)} ms, totales exactos {ev.exactitud} de {ev.casos} ({ev.aprobado ? 'aprobada' : 'no aprobada'}; {ev.embedder})</span>
                : 'Sin evaluación guardada (python eval/evaluar.py)'}
            </dd>
          </dl>
        ) : (
          <p className="texto-suave">No se pudo leer la configuración de la API.</p>
        )}
      </section>

      <section className="seccion" aria-labelledby="aj-datos">
        <h2 id="aj-datos">Datos y privacidad</h2>
        <p>Todo es sintético y vive en la base SQLite local del servidor. Borrar los datos de trabajo elimina cotizaciones, aprobaciones, memoria y bitácora; las fuentes cargadas y los usuarios se conservan.</p>
        <button className="boton boton--peligro-suave" disabled={!esAdministrador} title={esAdministrador ? undefined : 'Solo un Administrador puede borrar los datos de trabajo.'} onClick={() => setConfirmando(true)}>
          Borrar todos mis datos
        </button>
        {!esAdministrador && <p className="texto-suave">Solo un Administrador puede hacerlo.</p>}
      </section>

      <DialogoConfirmacion
        abierto={confirmando}
        titulo="Borrar los datos de trabajo"
        textoConfirmar="Borrar todo"
        peligro
        onCancelar={() => setConfirmando(false)}
        onConfirmar={() => {
          setConfirmando(false);
          void borrarDatos();
        }}
      >
        <p>Se borrarán {ajustes?.cotizaciones ?? 0} cotizaciones con sus aprobaciones, {ajustes?.hechos_memoria ?? 0} hechos de memoria y toda la bitácora. Las fuentes cargadas y los usuarios se conservan.</p>
        <p>Esta acción no se puede deshacer.</p>
      </DialogoConfirmacion>

      <section className="seccion" aria-labelledby="aj-formato">
        <h2 id="aj-formato">Preferencias de formato</h2>
        <div className="tarjetas-tema" role="radiogroup" aria-label="Tema de color">
          {TEMAS.map((t) => (
            <button
              key={t.id}
              role="radio"
              aria-checked={tema === t.id}
              className="tarjeta-tema"
              onClick={() => fijarTema(t.id)}
            >
              <Vista id={t.id} />
              <span>{t.etiqueta}</span>
              <span className="texto-suave subtitulo-chico">{t.ayuda}</span>
            </button>
          ))}
        </div>
        <dl className="lista-datos">
          <dt>Moneda</dt><dd className="cifra">{formatoMXN(1240000)}</dd>
          <dt>Fecha</dt><dd className="cifra">{formatoFecha('2026-11-21')} (dd/mm/aaaa)</dd>
          <dt>Idioma</dt><dd>Español (México)</dd>
        </dl>
      </section>
    </div>
  );
}
