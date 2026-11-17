import { EncabezadoPagina } from '../components/Estados';
import { useAlmacen } from '../state/Almacen';
import { USUARIOS } from '../data/ejemplo';
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
  const { avisar } = useAlmacen();
  const [tema, fijarTema] = useTema();

  return (
    <div className="pagina">
      <EncabezadoPagina titulo="Ajustes" />

      <section className="seccion" aria-labelledby="aj-usuarios">
        <h2 id="aj-usuarios">Usuarios y roles</h2>
        <p className="aviso-parcial" role="note">
          <span><strong>Pendiente.</strong> Los roles finales los define la Persona E en la matriz de permisos (semana 2). Hasta entonces la interfaz asume estos tres.</span>
        </p>
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead><tr><th scope="col">Nombre</th><th scope="col">Rol</th></tr></thead>
            <tbody>{USUARIOS.map((u) => <tr key={u.id}><td>{u.nombre}</td><td>{u.rol}</td></tr>)}</tbody>
          </table>
        </div>
      </section>

      <section className="seccion" aria-labelledby="aj-modelo">
        <h2 id="aj-modelo">Modelo activo</h2>
        <p className="texto-suave">Solo lectura en el MVP.</p>
        <dl className="lista-datos">
          <dt>Modelo</dt><dd>Sin conectar (el prototipo no usa ningún modelo)</dd>
          <dt>Latencia medida</dt><dd>Sin medir; se fija después de la semana 1</dd>
        </dl>
      </section>

      <section className="seccion" aria-labelledby="aj-datos">
        <h2 id="aj-datos">Datos y privacidad</h2>
        <p>En este prototipo todo es sintético y vive en la memoria del navegador; al recargar se reinicia.</p>
        <button className="boton boton--peligro-suave" onClick={() => avisar('Borrar todo no está disponible en el prototipo.', 'info')}>Borrar todos mis datos</button>
      </section>

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
          <dt>Fecha</dt><dd className="cifra">{formatoFecha('2026-11-11')} (dd/mm/aaaa)</dd>
          <dt>Idioma</dt><dd>Español (México)</dd>
        </dl>
      </section>
    </div>
  );
}
