import { Icono, type NombreIcono } from './Iconos';
import { mesesDeAntiguedad, textoMeses, UMBRAL_ANTIGUEDAD_MESES } from '../lib/dinero';

type Tono = 'ok' | 'warn' | 'error' | 'acento' | 'neutro';

const MAPA: Record<string, { icono: NombreIcono; tono: Tono }> = {
  Borrador: { icono: 'editar', tono: 'neutro' },
  'En revisión': { icono: 'reloj', tono: 'warn' },
  Aprobada: { icono: 'check', tono: 'ok' },
  Rechazada: { icono: 'error', tono: 'error' },
  Listo: { icono: 'check', tono: 'ok' },
  Procesando: { icono: 'reloj', tono: 'acento' },
  Error: { icono: 'error', tono: 'error' },
  Omitido: { icono: 'omitir', tono: 'neutro' },
  Activa: { icono: 'check', tono: 'ok' },
  Pausada: { icono: 'pausa', tono: 'neutro' },
  'Por confirmar': { icono: 'alerta', tono: 'warn' },
};

/** Estado siempre con icono + texto, nunca solo color (doc UI §9). */
export function InsigniaEstado({ estado }: { estado: string }) {
  const m = MAPA[estado] ?? { icono: 'omitir' as NombreIcono, tono: 'neutro' as Tono };
  return (
    <span className={`insignia insignia--${m.tono}`}>
      <Icono nombre={m.icono} tamano={14} />
      {estado}
    </span>
  );
}

export function EtiquetaPermiso({ permiso }: { permiso: string }) {
  return (
    <span className="etiqueta">
      <Icono nombre="candado" tamano={12} />
      {permiso}
    </span>
  );
}

/** Aviso de antigüedad del precio: icono + texto con los meses (doc UI §6). */
export function AvisoAntiguedad({ fecha }: { fecha: string }) {
  const meses = mesesDeAntiguedad(fecha);
  if (meses > UMBRAL_ANTIGUEDAD_MESES) {
    return (
      <span className="aviso-antiguedad" title={`Precio con más de ${UMBRAL_ANTIGUEDAD_MESES} meses de antigüedad`}>
        <Icono nombre="alerta" tamano={14} />
        {textoMeses(meses)}
      </span>
    );
  }
  return <span className="texto-suave">{textoMeses(meses)}</span>;
}
